#!/usr/bin/env python3
"""
Hook `PreToolUse` — a primeira das três camadas de enforcement (Impl. §9.1).

Recebe o JSON do Claude Code em stdin e devolve a decisão em
`hookSpecificOutput.permissionDecision`. Saída 2 sempre bloqueia, mesmo que o
JSON diga o contrário — usamos as duas formas para não depender de uma só.

É o MESMO código que o worker chama em processo (`order guard`): é isso que dá
sentido a "o worker nega as mesmas ações que o hook nega na nuvem" (AT-22). Um
hook que reimplementasse a regra divergiria do worker no primeiro ajuste.

Python, nunca `.sh` nem `.ps1`: um `guard.sh` funcionaria no Linux e falharia no
Windows sem Git Bash; um `guard.ps1` faria o inverso (Impl. §4.6).
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys


def decidir(negar: bool, motivo: str) -> None:
    saida = {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny" if negar else "allow",
        "permissionDecisionReason": motivo or "permitido pelo guard do CHAOS/ORDER",
    }}
    print(json.dumps(saida, ensure_ascii=False))
    sys.exit(2 if negar else 0)


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
        decidir(False, "sem payload — nada a avaliar")

    cwd = pathlib.Path(evento.get("cwd") or ".")
    ferramenta = evento.get("tool_name", "")
    entrada = evento.get("tool_input") or {}
    order = _cli(cwd, "order")

    # Numa sessão do Claude Code quem escreve é o MODELO. O ator nunca é humano
    # aqui, mesmo que a credencial Git da máquina seja a do proprietário — é
    # exatamente essa confusão que a derivação de ator (§17.1) existe para evitar.
    import os
    ator = os.environ.get("CHAOS_ACTOR") or "cloud:claude-code"
    argv: list[str] = ["--actor", ator]
    if ferramenta in ("Bash", "PowerShell"):
        comando = entrada.get("command") or ""
        argv += ["--", *comando.split()]
    elif ferramenta in ("Write", "Edit", "NotebookEdit"):
        alvo = entrada.get("file_path") or entrada.get("path") or ""
        try:
            alvo = str(pathlib.Path(alvo).resolve().relative_to(cwd.resolve()))
        except Exception:
            pass
        argv += ["--resource", alvo, "--action", "write"]
    else:
        decidir(False, "ferramenta fora do escopo do guard")

    p = subprocess.run([sys.executable, str(order), "guard", *argv],
                       cwd=cwd, capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        decidir(True, (p.stderr or p.stdout).strip().splitlines()[-1]
                if (p.stderr or p.stdout).strip() else "negado pelo guard")
    decidir(False, "")


if __name__ == "__main__":
    main()
