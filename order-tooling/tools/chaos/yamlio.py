"""
Leitura e escrita de entidades (CHAOS §7.1): Markdown com frontmatter YAML.

O harness da suíte parte o arquivo em `---` e faz `yaml.safe_load` do primeiro
bloco. Logo o corpo nunca pode conter uma linha `---` isolada, e o frontmatter
tem de ser YAML puro — sem truques de formatação.
"""
from __future__ import annotations

from pathlib import Path

import yaml


def ler(path: Path) -> tuple[dict, str]:
    texto = path.read_text(encoding="utf-8")
    if not texto.startswith("---"):
        raise ValueError(f"{path} não tem frontmatter (§7.1)")
    _, fm, corpo = texto.split("---", 2)
    return (yaml.safe_load(fm) or {}), corpo.lstrip("\n")


def escrever(path: Path, fm: dict, corpo: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bloco = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False)
    corpo = corpo.rstrip("\n")
    # Corpo com `---` isolado quebraria a leitura; recuar é melhor que corromper.
    corpo = "\n".join("  " + l if l.strip() == "---" else l for l in corpo.splitlines())
    texto = f"---\n{bloco}---\n{corpo}\n" if corpo else f"---\n{bloco}---\n"
    path.write_text(texto, encoding="utf-8", newline="\n")


def ler_yaml(path: Path):
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def escrever_yaml(path: Path, dados) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(dados, allow_unicode=True, sort_keys=False),
                    encoding="utf-8", newline="\n")


def ler_texto(texto: str) -> dict:
    """Frontmatter a partir de texto em memória (usado na resolução de conflito)."""
    if not texto.startswith("---"):
        raise ValueError("sem frontmatter")
    _, fm, _ = texto.split("---", 2)
    return yaml.safe_load(fm) or {}
