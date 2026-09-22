"""
Workflow Engine (ORDER §12).

Um workflow é uma sequência declarada de passos em `workflows/<nome>.yaml` —
**protected path**, porque é o corpo do que uma automação executa: quem controla
o workflow controla o que roda sozinho.

Três propriedades que o motor garante, e que são o motivo de ele existir em vez
de "o agente faz os passos":

1. **Todo passo passa pelos motores antes do efeito.** Risco, permissão e
   aprovação são avaliados por passo, não por workflow — um workflow de cinco
   passos A1 e um A3 para no A3, e os quatro primeiros já aconteceram.
2. **Idempotência por passo.** O resultado de cada passo entra em
   `checkpoint.artifacts_committed`; retomar não reexecuta o que já terminou.
3. **Determinismo.** O motor não consulta modelo para decidir o próximo passo:
   a ordem é a declarada. LLM entra dentro de um passo, nunca no controle.
"""
from __future__ import annotations

from pathlib import Path

from tools.chaos import ids, yamlio
from tools.chaos.repo import ErroChaos
from tools.order import risco

CAMPOS_PASSO = ("id", "tool")


def caminho(repo: Path, nome: str) -> Path:
    return repo / "workflows" / f"{nome}.yaml"


def listar(repo: Path) -> list[str]:
    base = repo / "workflows"
    return sorted(p.stem for p in base.glob("*.yaml")) if base.is_dir() else []


def carregar(repo: Path, nome: str) -> dict:
    p = caminho(repo, nome)
    if not p.exists():
        raise ErroChaos(f"workflow `{nome}` não existe em workflows/", "reference")
    wf = yamlio.ler_yaml(p) or {}
    passos = wf.get("steps") or []
    if not passos:
        raise ErroChaos(f"workflow `{nome}` não declara `steps`", "schema")
    vistos = set()
    for i, passo in enumerate(passos):
        for campo in CAMPOS_PASSO:
            if not passo.get(campo):
                raise ErroChaos(
                    f"passo {i} de `{nome}` sem `{campo}` — um passo sem "
                    "ferramenta declarada não tem classe de risco, e sem `id` "
                    "não é idempotente", "schema")
        if passo["id"] in vistos:
            raise ErroChaos(f"passo `{passo['id']}` duplicado em `{nome}` — os "
                            "ids são a chave de idempotência", "schema")
        vistos.add(passo["id"])
    return wf


def avaliar(repo: Path, nome: str) -> dict:
    """
    Classe de risco do workflow = a MAIOR dos seus passos.

    É o que permite a uma automação declarar `max_risk` e o motor recusar antes
    de começar, em vez de parar no meio com metade dos efeitos aplicados.
    """
    wf = carregar(repo, nome)
    classes = []
    for passo in wf["steps"]:
        r = risco.avaliar(tool=passo["tool"], resource=passo.get("resource", ""),
                          action=passo.get("action", ""))
        classes.append(r["risk_class"])
    return {"workflow": nome, "steps": len(wf["steps"]),
            "risk_class": risco.maior(*classes) if classes else "A0",
            "per_step": dict(zip((p["id"] for p in wf["steps"]), classes))}


def executar(repo: Path, nome: str, *, executor, run_id: str = "",
             concluidos: list[str] | None = None, dry_run: bool = False) -> dict:
    """
    `executor` é uma função (passo, risco) -> dict, injetada pelo chamador.

    A injeção existe para que o motor não conheça o guard, o ledger nem o
    gateway: ele ordena e decide o que pular, e quem aplica efeito é quem o
    chamou. Testar o motor não exige repositório nem modelo.
    """
    wf = carregar(repo, nome)
    feitos = set(concluidos or [])
    resultados, pulados = [], []

    for passo in wf["steps"]:
        if passo["id"] in feitos:
            pulados.append(passo["id"])          # idempotência: não reexecuta
            continue
        r = risco.avaliar(tool=passo["tool"], resource=passo.get("resource", ""),
                          action=passo.get("action", ""))
        if dry_run:
            resultados.append({"step": passo["id"], "risk_class": r["risk_class"],
                               "status": "dry-run"})
            continue
        saida = executor(passo, r)
        resultados.append({"step": passo["id"], "risk_class": r["risk_class"],
                           **(saida or {})})
        if (saida or {}).get("status") in ("awaiting_approval", "denied", "failed"):
            # Para no passo, preservando o que já foi feito: retomar continua
            # daqui, não do começo.
            break

    return {"workflow": nome, "run_id": run_id, "results": resultados,
            "skipped": pulados, "completed_at": ids.agora()}
