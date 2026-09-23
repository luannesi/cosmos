"""
Worker local (`order-worker`) — Implementação §8.1.

É o executor de retomada e o único caminho para `privacy: local_only` e modelos
locais. O laço é deliberadamente simples e o que importa nele são as recusas:

- respeita `PAUSED` antes de qualquer coisa;
- nunca reclama tarefa de outra classe de privacidade;
- ao perder o claim, descarta o próprio commit — nunca rebase, nunca merge;
- checkpointa antes de qualquer espera, para que outro executor possa retomar;
- passa TODA chamada de ferramenta pelo mesmo `guard` que o hook usa.

Cada volta é curta e o estado vive em arquivo: matar o processo a qualquer
momento não perde trabalho além do passo corrente.
"""
from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from pathlib import Path

from tools.chaos import entidades, gitops, ids, ledger, yamlio
from tools.chaos.repo import Identidade, achar_repo

_parar = False


def _sinal(_s, _f):
    global _parar
    _parar = True


class Worker:
    def __init__(self, repo: Path, ident: Identidade, order_bin: Path):
        self.repo = repo
        self.ident = ident
        self.order = order_bin
        cfg = yamlio.ler_yaml(repo / "order" / "policies" / "worker.yaml") or {}
        self.intervalo = int(cfg.get("loop_interval_s", 30))
        self.lease_min = int(cfg.get("lease_duration_min", 20))
        self.net_timeout = int(cfg.get("net_timeout_s", 30))

    # ------------------------------------------------------------------ #
    def _order(self, *args: str) -> tuple[int, dict | str]:
        p = subprocess.run([sys.executable, str(self.order), *args],
                           cwd=self.repo, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=self.net_timeout * 4)
        try:
            return p.returncode, json.loads(p.stdout)
        except Exception:
            return p.returncode, (p.stderr or p.stdout).strip()

    def pausado(self) -> bool:
        return (self.repo / "order" / "PAUSED").exists()

    def elegiveis(self) -> list[dict]:
        """
        Tarefas que ESTE worker pode reclamar.

        `execution: cloud` nunca entra; `local_only` só entra aqui — é a razão
        de o worker existir. Tarefa bloqueada por falta de capacidade também
        não entra: o bloqueio é sinalização para o humano, não fila de espera.
        """
        saida = []
        for p in entidades.todas(self.repo):
            fm, _ = yamlio.ler(p)
            if fm.get("type") != "task" or fm.get("status") not in ("todo", "in_progress"):
                continue
            if fm.get("execution") == "cloud":
                continue
            if fm.get("blocked_reason"):
                continue
            lease = str(fm.get("lease_until") or "")
            if fm.get("claimed_by") and lease > ids.agora():
                continue            # lease vivo de outro executor
            saida.append(fm)
        return saida

    def uma_volta(self) -> dict:
        if self.pausado():
            return {"skipped": "PAUSED"}

        gitops.git(self.repo, "fetch", "-q", "origin")
        rc, _ = self._order("trigger", "scan", "--local")

        feitas = []
        for tarefa in self.elegiveis():
            rc, resposta = self._order("task", "claim", tarefa["id"])
            if rc != 0:
                # perdeu a corrida, ou a tarefa não é para este executor:
                # não insiste, não faz rebase, apenas segue para a próxima
                continue
            run_id = resposta.get("run_id") if isinstance(resposta, dict) else None
            if not run_id:
                continue

            self._order("run", "checkpoint", run_id,
                        "--step", "1/1", "--last-action", "reclamada pelo worker",
                        "--resume-hint", "executar o passo declarado")
            resultado = self.executar(tarefa, run_id)
            feitas.append({"task": tarefa["id"], "run": run_id, **resultado})
            if _parar:
                break
        return {"claimed": feitas, "paused": False}

    def executar(self, tarefa: dict, run_id: str) -> dict:
        """
        Execução de uma tarefa.

        Hoje o worker roteia o modelo e registra a decisão, mas **não chama
        modelo**: as credenciais e as fontes de orçamento vêm do Onboarding
        (§3.4), e chamar sem elas seria inventar configuração do usuário. O
        caminho está pronto — `order model route` decide, `gateway.chamar`
        executa — e liga quando o registry tiver um modelo com `endpoint` ou
        um runner local instalado.
        """
        rc, rota = self._order("model", "route", "--task", tarefa["id"],
                               "--dry-run")
        if rc != 0:
            self._order("run", "abandon", run_id, "--reason", "sem rota de modelo")
            return {"status": "no_route", "detail": rota}

        ledger.append(self.repo, actor=self.ident.ator, surface="local:worker",
                      action="worker.execute", entity_id=tarefa["id"],
                      risk_class="A1",
                      summary=f"rota {rota.get('model_id')} tier {rota.get('tier')}"
                      if isinstance(rota, dict) else "")
        self._order("run", "checkpoint", run_id, "--step", "1/1",
                    "--last-action", "rota resolvida; execução de modelo pendente "
                                     "de credencial do Onboarding",
                    "--resume-hint", "retomar quando o registry tiver provedor")
        return {"status": "routed",
                "model": rota.get("model_id") if isinstance(rota, dict) else None}

    def rodar(self, uma_vez: bool = False) -> None:
        signal.signal(signal.SIGINT, _sinal)
        signal.signal(signal.SIGTERM, _sinal)
        while not _parar:
            inicio = time.time()
            try:
                relatorio = self.uma_volta()
                print(json.dumps(relatorio, ensure_ascii=False), flush=True)
            except Exception as exc:
                # Uma volta que falha não derruba o worker: o estado está em
                # arquivo e a próxima volta reavalia.
                print(json.dumps({"error": str(exc)[:300]}, ensure_ascii=False),
                      file=sys.stderr, flush=True)
            if uma_vez:
                return
            espera = max(1.0, self.intervalo - (time.time() - inicio))
            for _ in range(int(espera * 2)):
                if _parar:
                    break
                time.sleep(0.5)
        print(json.dumps({"stopped": True}), flush=True)


def main(argv: list[str]) -> int:
    uma_vez = "--once" in argv
    repo = achar_repo()
    ident = Identidade(repo)
    order_bin = repo / "bin" / "order"
    if not order_bin.exists():
        order_bin = Path(__file__).resolve().parents[2] / "bin" / "order"
    Worker(repo, ident, order_bin).rodar(uma_vez=uma_vez)
    return 0
