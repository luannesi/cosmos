"""
Ledger append-only (CHAOS §17.1).

Nunca reescreve linha. A concorrência entre executores é resolvida por
`merge=union` no .gitattributes, não por exclusividade — por isso o adapter é o
único caminho de escrita e cada linha é autocontida.

§17.5: o EVT registra a AÇÃO, nunca o conteúdo. `summary` é truncado.
"""
from __future__ import annotations

import json
import secrets
from pathlib import Path

from .ids import agora


def caminho(repo: Path) -> Path:
    return repo / "audit" / "events.jsonl"


def append(repo: Path, *, actor: str, surface: str, action: str,
           risk_class: str = "A1", entity_id: str = "", level: str = "info",
           approval_id: str = "", policy: str = "", summary: str = "") -> dict:
    limite = 200
    cfg = repo / "metadata" / "repo.yaml"
    if cfg.exists():
        import yaml
        d = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        limite = int(d.get("audit_summary_max", 200))

    evt = {
        "event_id": f"EVT-{agora()[:10].replace('-', '')}-{secrets.token_hex(4).upper()}",
        "ts": agora(),
        "actor": actor,
        "surface": surface,
        "action": action,
        "risk_class": risk_class,
        "entity_id": entity_id,
        "level": level,
    }
    if approval_id:
        evt["approval_id"] = approval_id
    if policy:
        evt["policy"] = policy
    if summary:
        evt["summary"] = summary[:limite]

    p = caminho(repo)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(evt, ensure_ascii=False, sort_keys=True) + "\n")
    return evt


def ler(repo: Path, ordenado: bool = False) -> list[dict]:
    p = caminho(repo)
    if not p.exists():
        return []
    linhas = []
    for l in p.read_text(encoding="utf-8").splitlines():
        if l.strip():
            try:
                linhas.append(json.loads(l))
            except json.JSONDecodeError:
                continue
    # A ordem física é o que o `merge=union` deixou; a ordem semântica é `ts`.
    # Quem precisa de cronologia ordena na leitura (§17.1).
    return sorted(linhas, key=lambda e: e.get("ts", "")) if ordenado else linhas
