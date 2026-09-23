#!/usr/bin/env python3
"""
Hook `Stop` — checkpoint do RUN ativo ao fim de cada turno (CHAOS §7.4).

Continuidade vive em RUN, HND e SES; nunca na sessão. Se o turno acabar sem
checkpoint, a retomada por outro executor perde o progresso — e o contrato diz
que ela não deve inferir nada.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys


def _cli(cwd: pathlib.Path, nome: str) -> pathlib.Path:
    """
    A CLI vem do REPOSITÓRIO, não da árvore do hook.

    O repositório vendoriza `tools/` e `bin/` por tag (Impl. §4.3): é o código
    que ele declara que tem de rodar, e é isso que `chaos health` verifica.
    """
    for cand in (cwd / "bin" / nome,
                 pathlib.Path(__file__).resolve().parents[2] / "bin" / nome):
        if cand.exists():
            return cand
    return cwd / "bin" / nome


def main() -> None:
    try:
        evento = json.load(sys.stdin)
    except Exception:
        evento = {}
    cwd = pathlib.Path(evento.get("cwd") or ".")
    order = _cli(cwd, "order")

    p = subprocess.run([sys.executable, str(order), "run", "list", "--format", "json"],
                       cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if p.returncode != 0:
        sys.exit(0)
    try:
        runs = json.loads(p.stdout)
    except Exception:
        sys.exit(0)

    ativos = [r for r in runs if r.get("status") in ("claimed", "running")]
    for r in ativos:
        subprocess.run([sys.executable, str(order), "run", "checkpoint", r["id"],
                        "--step", "fim de turno",
                        "--last-action", "turno encerrado pelo hook Stop",
                        "--resume-hint", "retomar do último artefato comitado"],
                       cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    sys.exit(0)


if __name__ == "__main__":
    main()
