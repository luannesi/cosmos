"""
Harness da suíte de Acceptance Tests (AT) de CHAOS v2.5 / ORDER v2.5.

A superfície de contrato é a CLI (Command Line Interface): CHAOS §21 e ORDER §38
são os contratos completos; a Implementação §11 os referencia sem duplicar.
Os testes nunca tocam arquivos internos da implementação — só invocam `chaos` e
`order` e inspecionam o repositório resultante, que é o artefato canônico.

Sem implementação apontada (--chaos-bin / --order-bin), a suíte pula com motivo
explícito em vez de passar em verde: uma suíte de conformidade que passa sem
implementação é pior que nenhuma.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class CLIUnavailable(RuntimeError):
    """A implementação não foi apontada para a suíte."""


@dataclass
class Result:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def denied(self) -> bool:
        """Recusa esperada: código != 0. O motivo é verificado separadamente."""
        return self.returncode != 0

    def json(self):
        return json.loads(self.stdout)

    def mentions(self, *needles: str) -> bool:
        blob = (self.stdout + self.stderr).lower()
        return any(n.lower() in blob for n in needles)


def _invocacao(binario: str) -> list[str]:
    """
    Como invocar a CLI neste sistema operacional.

    `bin/chaos` é um script Python com shebang. O POSIX honra shebang; o
    Windows não. Apontar a suíte para o arquivo sem extensão funciona no Linux
    e falha no Windows com um erro de formato que não sugere a causa — e o
    Windows é justamente a plataforma-alvo deste sistema.

    Duas saídas, e as duas valem: existe um invólucro `.cmd` ao lado para o uso
    interativo, e aqui a suíte resolve sozinha, para não depender de o usuário
    ter apontado o caminho certo.
    """
    p = Path(binario)
    if os.name == "nt" and p.suffix == "":
        irmao = p.with_suffix(".cmd")
        if irmao.exists():
            return [str(irmao)]
        return [sys.executable, str(p)]
    return [binario]


class CLI:
    """Invocador de `chaos` ou `order` dentro de um repositório, sob uma identidade."""

    def __init__(self, binary: str | None, cwd: Path, name: str):
        self.binary = binary
        self.cwd = cwd
        self.name = name

    def __call__(self, *args: str, identity: "Identity | None" = None,
                 expect_ok: bool | None = None) -> Result:
        if not self.binary:
            raise CLIUnavailable(
                f"`{self.name}` não apontado. Rode com "
                f"--{self.name}-bin=/caminho/para/{self.name}"
            )
        env = dict(os.environ)
        if identity:
            env.update(identity.env())
        proc = subprocess.run(
            [*_invocacao(self.binary), *args], cwd=self.cwd, env=env,
            capture_output=True, text=True, timeout=120,
        )
        res = Result(proc.returncode, proc.stdout, proc.stderr)
        if expect_ok is True and not res.ok:
            raise AssertionError(
                f"{self.name} {' '.join(args)} falhou ({res.returncode}):\n{res.stderr}"
            )
        if expect_ok is False and res.ok:
            raise AssertionError(
                f"{self.name} {' '.join(args)} deveria ter sido recusado, mas passou:\n{res.stdout}"
            )
        return res


@dataclass(frozen=True)
class Identity:
    """
    Identidade Git. CHAOS §17.1 e Implementação §3.1 exigem credenciais distintas
    para humano e para cada executor; o validador cruza identidade x trailer.
    """
    kind: str           # "human" | "executor"
    actor: str          # "human:<owner>" | "executor:local_worker" | "agent:<id>"
    email: str
    surface: str

    def env(self) -> dict:
        return {
            "GIT_AUTHOR_NAME": self.actor,
            "GIT_AUTHOR_EMAIL": self.email,
            "GIT_COMMITTER_NAME": self.actor,
            "GIT_COMMITTER_EMAIL": self.email,
            "CHAOS_ACTOR": self.actor,
            "CHAOS_SURFACE": self.surface,
        }


HUMAN = Identity("human", "human:owner", "owner@example.invalid", "local:editor")
WORKER = Identity("executor", "executor:local_worker", "worker@example.invalid", "local:worker")
CLOUD = Identity("executor", "cloud:claude-code", "cloud@example.invalid", "cloud:claude-code")
AGENT = Identity("executor", "agent:area.demo", "cloud@example.invalid", "cloud:claude-code")


# --------------------------------------------------------------------------- #
# Leitura do repositório (o artefato canônico, não o estado interno da impl.)   #
# --------------------------------------------------------------------------- #

def frontmatter(path: Path) -> dict:
    """Frontmatter YAML de uma entidade (CHAOS §7.1: Markdown + frontmatter)."""
    import yaml
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise AssertionError(f"{path} não tem frontmatter — viola CHAOS §7.1")
    _, fm, _ = text.split("---", 2)
    return yaml.safe_load(fm) or {}


def events(repo: Path) -> list[dict]:
    """Linhas do ledger append-only (CHAOS §17.1)."""
    ledger = repo / "audit" / "events.jsonl"
    if not ledger.exists():
        return []
    return [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]


def git(repo: Path, *args: str, identity: Identity | None = None) -> Result:
    env = dict(os.environ)
    if identity:
        env.update(identity.env())
    p = subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, text=True)
    return Result(p.returncode, p.stdout, p.stderr)


# --------------------------------------------------------------------------- #
# Casos do guard, compartilhados entre nuvem e worker                          #
# --------------------------------------------------------------------------- #
#
# ORDER AT-22 exige que o worker local negue "as mesmas ações que o hook nega na
# nuvem (mesma suíte de casos)". ORDER §16 enumera as classes mínimas; esta
# tabela as instancia e é a MESMA lista consumida por AT-20 e AT-22 — é isso que
# dá sentido a "mesma". `test_contract_consistency.py` trava a correspondência.

GUARD_CASES = [
    # (id, argv do comando tentado, motivo esperado na recusa)
    #
    # Organizados por FAMÍLIA, não por plataforma, e todos negados em qualquer host:
    # um Windows com Git Bash executa `sed -i`; um Linux com PowerShell executa
    # `Set-Content`. Negar só a metade correspondente ao host abriria a outra na
    # máquina que tivesse os dois shells — o caso comum de quem usa Git no Windows.
    ("interpretador-python", ["bash", "-c", "python3 -c 'open(\"x.md\",\"w\")'"], "allowlist"),
    ("interpretador-node", ["bash", "-c", "node -e 'require(\"fs\")'"], "allowlist"),
    ("interpretador-powershell", ["powershell", "-Command", "Set-Content x.md 'y'"], "allowlist"),
    ("interpretador-powershell-enc", ["powershell", "-EncodedCommand", "UwBlAHQA"], "allowlist"),
    ("interpretador-cmd", ["cmd", "/c", "echo y > x.md"], "allowlist"),
    ("redirecionamento-posix", ["bash", "-c", "echo x >> tasks/qualquer.md"], "allowlist"),
    ("redirecionamento-outfile", ["powershell", "-Command", "'x' | Out-File tasks/qualquer.md"], "allowlist"),
    ("editor-sed", ["bash", "-c", "sed -i s/a/b/ tasks/qualquer.md"], "allowlist"),
    ("editor-tee", ["bash", "-c", "tee tasks/qualquer.md"], "allowlist"),
    ("editor-addcontent", ["powershell", "-Command", "Add-Content tasks/qualquer.md 'x'"], "allowlist"),
    ("shell-aninhado-posix", ["bash", "-c", "sh -c 'echo x > y.md'"], "allowlist"),
    ("shell-aninhado-windows", ["cmd", "/c", "powershell -Command exit"], "allowlist"),
    ("git-commit-direto", ["bash", "-c", "git commit -am x"], "allowlist"),
    ("git-push-direto", ["bash", "-c", "git push"], "allowlist"),
    ("protected-policies", ["write", "order/policies/quotas.yaml"], "protected"),
    ("protected-enforcement", ["write", ".claude/settings.json"], "protected"),
    ("protected-agents-md", ["write", "AGENTS.md"], "protected"),
    ("protected-automations", ["write", "order/automations/AUT-x.md"], "protected"),
    ("protected-paused", ["write", "order/PAUSED"], "protected"),
    ("audit-direto", ["write", "audit/events.jsonl"], "protected"),
]


def find_entity(repo: Path, entity_id: str) -> Path:
    """CHAOS §7.2: nome do arquivo = ID + .md."""
    hits = list(repo.rglob(f"{entity_id}.md"))
    if not hits:
        raise AssertionError(f"entidade {entity_id} não encontrada em {repo}")
    if len(hits) > 1:
        raise AssertionError(f"entidade {entity_id} duplicada: {hits}")
    return hits[0]
