#!/usr/bin/env python3
"""Hook `SessionEnd` — encerramento; HND se houver trabalho aberto (ORDER §30)."""
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
    raiz = pathlib.Path(__file__).resolve().parents[2]
    subprocess.run([sys.executable, str(_cli(cwd, "order")), "session", "close"],
                   cwd=cwd, capture_output=True, text=True, timeout=60)
    sys.exit(0)


if __name__ == "__main__":
    main()
