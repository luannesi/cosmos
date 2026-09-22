"""
`chaos health` (CHAOS §21.1).

Responde a pergunta que ninguém faz até um defeito inexplicável aparecer: o
código que está executando é o que este repositório declara?

Somente leitura. Nunca atualiza, nunca instala, nunca corrige — alinhar é
`chaos tooling update <tag>`, escrita em protected path, logo humana. Um
`health` que se conserta sozinho seria caminho de escrita não governado com
nome tranquilizador.
"""
from __future__ import annotations

from pathlib import Path

from . import episodico, yamlio
from .layout import TAG


def avaliar(repo: Path) -> dict:
    tooling = repo / "metadata" / "tooling.yaml"
    out = {"status": "ok", "running_tag": TAG, "vendored_tag": None,
           "checks": [], "episodic": episodico.status(repo)}

    if not tooling.exists():
        out["status"] = "broken"
        out["checks"].append({"check": "tooling.yaml", "status": "broken",
                              "detail": "metadata/tooling.yaml ausente — não há como "
                                        "saber qual toolchain este repositório declara"})
        return out

    try:
        dados = yamlio.ler_yaml(tooling) or {}
    except Exception as exc:
        out["status"] = "broken"
        out["checks"].append({"check": "tooling.yaml", "status": "broken",
                              "detail": f"ilegível: {exc}"})
        return out

    vendored = str(dados.get("vendored_tag") or "").strip()
    out["vendored_tag"] = vendored or None
    if not vendored:
        out["status"] = "broken"
        out["checks"].append({"check": "vendored_tag", "status": "broken",
                              "detail": "metadata/tooling.yaml não declara `vendored_tag`"})
        return out

    if vendored != TAG:
        out["status"] = "drift"
        out["checks"].append({
            "check": "toolchain", "status": "drift",
            "detail": f"executando `{TAG}`, repositório declara `{vendored}` — "
                      "reprodutibilidade (ORDER §39) não vale até alinhar com "
                      "`chaos tooling update`"})
    else:
        out["checks"].append({"check": "toolchain", "status": "ok",
                              "detail": f"tag `{TAG}`"})

    # pré-condições de plataforma (§7.2, §17.1)
    ga = repo / ".gitattributes"
    if not ga.exists() or "eol=lf" not in ga.read_text(encoding="utf-8"):
        out["checks"].append({"check": "line-endings", "status": "broken",
                              "detail": ".gitattributes sem `* text=auto eol=lf` (§17.1)"})
        out["status"] = "broken"

    return out


def codigo_de_saida(estado: str) -> int:
    return {"ok": 0, "drift": 1, "broken": 2}.get(estado, 2)
