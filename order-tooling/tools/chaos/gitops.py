"""Operações Git — o único caminho de commit e sincronização de agentes (§21)."""
from __future__ import annotations

import subprocess
from pathlib import Path


def git(repo: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    p = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p


def arquivos_modificados(repo: Path) -> list[str]:
    saida = git(repo, "status", "--porcelain").stdout
    rels = []
    for linha in saida.splitlines():
        if not linha.strip():
            continue
        caminho = linha[3:].strip()
        if " -> " in caminho:
            caminho = caminho.split(" -> ", 1)[1]
        rels.append(caminho.strip('"'))
    return rels


def head(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def trailers_de(mensagem: str) -> dict:
    achados = {}
    for linha in mensagem.splitlines():
        for chave in ("Actor", "Surface"):
            if linha.strip().startswith(f"{chave}:"):
                achados[chave] = linha.split(":", 1)[1].strip()
    return achados


def commits(repo: Path, limite: int | None = None) -> list[dict]:
    SEP, FIM = "\x1f", "\x1e"
    fmt = SEP.join(["%H", "%ae", "%s", "%b"]) + FIM
    args = ["log", f"--format={fmt}"]
    if limite:
        args += [f"-{limite}"]
    bruto = git(repo, *args).stdout
    saida = []
    for bloco in bruto.split(FIM):
        if not bloco.strip():
            continue
        h, email, assunto, corpo = bloco.lstrip("\n").split(SEP)
        saida.append({"hash": h, "email": email.lower(), "assunto": assunto,
                      "corpo": corpo, "trailers": trailers_de(corpo)})
    return saida


def arquivos_do_commit(repo: Path, sha: str) -> list[str]:
    return [l for l in git(repo, "show", "--name-only", "--format=", sha)
            .stdout.splitlines() if l.strip()]
