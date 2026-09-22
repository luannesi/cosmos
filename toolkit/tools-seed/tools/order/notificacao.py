"""
Notification Adapter (ORDER §3, §41).

Canais são substituíveis; o que não é substituível é o registro. Toda
notificação vira arquivo em `order/notifications/` **antes** de sair — assim,
sem canal externo configurado, nada se perde: aparece no próximo briefing
(§40, degradação declarada).

Notificar o próprio usuário é A2; qualquer outro canal é A3 (§14) — e quem
decide isso é o Risk Engine, não este módulo.
"""
from __future__ import annotations

import json
from pathlib import Path

from tools.chaos import ids, yamlio


def canais_permitidos(repo: Path) -> list[str]:
    cfg = yamlio.ler_yaml(repo / "metadata" / "repo.yaml") or {}
    return list(cfg.get("allowed_channels") or [])


def enviar(repo: Path, *, canal: str, mensagem: str, ator: str,
           entidade: str = "") -> dict:
    from tools.chaos.repo import ErroChaos
    permitidos = canais_permitidos(repo)
    if canal not in permitidos and canal != "self":
        raise ErroChaos(
            f"canal `{canal}` não está em `allowed_channels` deste repositório "
            f"({', '.join(permitidos) or 'nenhum'}) — policies de canal são por "
            "repositório (§4)", "policy")

    destino = repo / "order" / "notifications"
    destino.mkdir(parents=True, exist_ok=True)
    registro = {"ts": ids.agora(), "channel": canal, "message": mensagem,
                "actor": ator, "entity_id": entidade, "delivered": canal == "self"}
    with (destino / "outbox.jsonl").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n")
    return registro


def pendentes(repo: Path) -> list[dict]:
    p = repo / "order" / "notifications" / "outbox.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
            if l.strip() and not json.loads(l).get("delivered")]
