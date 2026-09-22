"""
Localização do repositório, identidade e caminhos protegidos.

A derivação de ator (§17.1) está isolada neste módulo de propósito: é a única
peça cuja forma depende do resultado do spike de identidade. Se a sessão na
nuvem puder escolher a própria identidade, é aqui — e só aqui — que a raiz de
confiança muda.
"""
from __future__ import annotations

import fnmatch
import os
import subprocess
from pathlib import Path

from . import yamlio


class ErroChaos(Exception):
    """Erro de contrato: sai com código != 0 e mensagem categorizada."""

    def __init__(self, mensagem: str, categoria: str = "policy"):
        super().__init__(mensagem)
        self.categoria = categoria


# §4.1 — protected paths derivados do critério: todo arquivo que governa o
# comportamento de agentes futuros. A lista é a instanciação do critério; um
# arquivo que o satisfaça e não esteja aqui é defeito da lista, não permissão.
PROTECTED = [
    "metadata/policies/**", "metadata/registries/**", "metadata/schemas/**",
    "metadata/tooling.yaml",
    "order/policies/**", "order/agents/**", "order/automations/**", "order/PAUSED",
    "AGENTS.md", "CLAUDE.md",
    "workflows/**",
    ".claude/**", "tools/**", ".github/**", ".gitattributes", ".gitignore",
    ".ai-memory.toml",
    "audit/**",
]


def eh_protegido(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    for padrao in PROTECTED:
        if fnmatch.fnmatch(rel, padrao):
            return True
        if padrao.endswith("/**") and rel.startswith(padrao[:-2]):
            return True
    return False


def achar_repo(inicio: Path | None = None) -> Path:
    p = (inicio or Path.cwd()).resolve()
    for cand in [p, *p.parents]:
        if (cand / "metadata" / "repo.yaml").exists() or (cand / ".git").exists():
            return cand
    raise ErroChaos("nenhum repositório CHAOS encontrado a partir de "
                    f"{p} — rode `chaos init` primeiro", "reference")


class Identidade:
    """
    Ator e superfície da invocação corrente.

    §17.1: o `Actor:` é DERIVADO da credencial Git via executors.yaml, nunca
    declarado. O que o ambiente traz é uma *pretensão*; o registry decide se a
    credencial pode sustentá-la. Sem isso, "commit humano = sem trailer" vira
    afirmação negativa sobre algo que o próprio modelo controla.
    """

    def __init__(self, repo: Path):
        self.repo = repo
        self.email = (os.environ.get("GIT_AUTHOR_EMAIL")
                      or self._git_config("user.email") or "").strip().lower()
        self.pretendido = (os.environ.get("CHAOS_ACTOR") or "").strip()
        self.surface = (os.environ.get("CHAOS_SURFACE") or "local:editor").strip()

    def _git_config(self, chave: str) -> str:
        p = subprocess.run(["git", "config", "--get", chave], cwd=self.repo,
                           capture_output=True, text=True)
        return p.stdout.strip()

    def _registry(self) -> list[dict]:
        dados = yamlio.ler_yaml(self.repo / "metadata" / "registries" / "executors.yaml")
        return (dados or {}).get("executors", []) if isinstance(dados, dict) else []

    def entrada(self) -> dict | None:
        for e in self._registry():
            if str(e.get("git_identity", "")).strip().lower() == self.email:
                return e
        return None

    @property
    def ator(self) -> str:
        """O ator efetivo — derivado, nunca o pretendido cru."""
        e = self.entrada()
        if not e:
            raise ErroChaos(
                f"credencial `{self.email or '(vazia)'}` não consta em "
                "metadata/registries/executors.yaml — §17.1: o ator vem da "
                "credencial, e credencial desconhecida não tem ator", "integrity")

        permitidos = e.get("allowed_actors") or [e["id"]]
        if not self.pretendido:
            return e["id"]
        for padrao in permitidos:
            if fnmatch.fnmatch(self.pretendido, padrao):
                return self.pretendido
        raise ErroChaos(
            f"a credencial `{self.email}` não pode agir como `{self.pretendido}` "
            f"(§17.1; permitidos: {', '.join(permitidos)})", "integrity")

    @property
    def eh_humano(self) -> bool:
        try:
            return self.ator.startswith("human:")
        except ErroChaos:
            return False

    @property
    def eh_agente(self) -> bool:
        try:
            return self.ator.startswith("agent:")
        except ErroChaos:
            return False

    def exigir_nao_agente(self, rel: str) -> None:
        """§4.1: agente não escreve em protected path."""
        if eh_protegido(rel) and not self.eh_humano:
            raise ErroChaos(
                f"`{rel}` é protected path (CHAOS §4.1): governa o comportamento "
                f"de agentes futuros e só humano escreve. Ator: {self.pretendido or '?'}",
                "policy")


def cfg_repo(repo: Path) -> dict:
    return yamlio.ler_yaml(repo / "metadata" / "repo.yaml") or {}


def nuvem_alcanca(repo: Path) -> bool:
    """§4.1: `local_only` é proibido onde a nuvem tem credencial."""
    return bool(str(cfg_repo(repo).get("remote") or "").strip())
