"""
Camada episódica (CHAOS §4.2) — adaptador.

Não canônica por construção. O `chaos` LÊ; quem escreve é o componente que a
implementa (Implementação §17). Não existe `chaos episodic write`, pela mesma
razão que não existe `policy set`.

Ausente a camada, tudo continua funcionando e `context.episodic` vem vazio —
é o AT-34 que dá direito de adotar um componente de terceiro.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .repo import cfg_repo


def habilitada(repo: Path) -> bool:
    if os.environ.get("CHAOS_EPISODIC", "").lower() in ("disabled", "0", "off", "false"):
        return False
    if not cfg_repo(repo).get("episodic", False):
        return False
    return bool(binario())


def binario() -> str:
    return os.environ.get("CHAOS_EPISODIC_BIN", "")


def status(repo: Path) -> dict:
    bin_ = binario()
    return {
        "enabled": habilitada(repo),
        "binary": bin_ or None,
        "declared": bool(cfg_repo(repo).get("episodic", False)),
        "reason": None if habilitada(repo) else
                  ("desligada por CHAOS_EPISODIC" if os.environ.get("CHAOS_EPISODIC")
                   else "nenhum componente episódico apontado"),
    }


def consultar(repo: Path, consulta: str, limite: int = 5) -> list[dict]:
    """
    Sem consulta resolvível, devolve os registros mais recentes.

    O bloco `episodic` responde a uma pergunta só — *o que já foi tentado sobre
    isto* — e quando não há termo de busca a resposta útil é a recente, não o
    vazio. Devolver nada faria a camada parecer ausente quando ela está presente.
    """
    if not habilitada(repo):
        return []
    try:
        p = subprocess.run([binario(), "search", consulta or "", "--format", "json"],
                           cwd=repo, capture_output=True, text=True, timeout=20)
        if p.returncode != 0:
            return []
        dados = json.loads(p.stdout or "[]")
        itens = dados if isinstance(dados, list) else dados.get("results", [])
        itens = sorted(itens, key=lambda i: i.get("ts", ""), reverse=True)
        return [dict(i, episodic=True) for i in itens[:limite]]
    except Exception:
        # A camada é opcional: falha dela nunca vira falha do sistema (§40 ORDER).
        return []


def obter(repo: Path, ref: str) -> dict | None:
    if not binario():
        return None
    try:
        p = subprocess.run([binario(), "show", ref, "--format", "json"],
                           cwd=repo, capture_output=True, text=True, timeout=20)
        if p.returncode != 0:
            return None
        return json.loads(p.stdout)
    except Exception:
        return None
