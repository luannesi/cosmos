#!/usr/bin/env python3
"""
Hook `PostToolUse` — EVT para toda escrita via CLI (CHAOS §17.1).

Os trailers são injetados ANTES do commit por `chaos commit`; aqui só se
registra que a ferramenta rodou. O ledger cresce pelo adapter, nunca por
escrita direta no arquivo.
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
        sys.exit(0)
    cwd = pathlib.Path(evento.get("cwd") or ".")
    raiz = pathlib.Path(__file__).resolve().parents[2]
    comando = (evento.get("tool_input") or {}).get("command", "")
    if not comando.strip().startswith(("chaos", "order")):
        sys.exit(0)
    subprocess.run([sys.executable, str(_cli(cwd, "chaos")), "audit", "append",
                    "--action", comando.split()[0] + ".cli"],
                   cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    sys.exit(0)


if __name__ == "__main__":
    main()
