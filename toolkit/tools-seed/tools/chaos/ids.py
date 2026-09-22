"""IDs de entidade (CHAOS §7.2) e vocabulários fechados."""
from __future__ import annotations

import datetime as _dt
import re
import secrets

ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # sem 0/O/1/I
PADRAO = re.compile(r"^[A-Z]{2,4}-\d{8}-[" + ALFABETO + r"]{6}$")

# §7.3 — prefixo por tipo
PREFIXOS = {
    "project": "PRJ", "task": "TSK", "decision": "DEC", "source": "SRC",
    "approval": "APV", "automation": "AUT", "handoff": "HND", "run": "RUN",
    "session": "SES", "document": "DOC", "meeting": "MTG", "risk": "RSK",
    "milestone": "MS", "deliverable": "DLV", "dependency": "DEP",
    "deadline": "DL", "event": "EVT", "inbox": "INB", "tec": "TEC",
}
TIPO_POR_PREFIXO = {v: k for k, v in PREFIXOS.items()}

# pasta canônica por tipo (§4.1)
PASTAS = {
    "project": "projects", "task": "tasks", "decision": "decisions",
    "source": "sources", "approval": "order/approvals", "automation": "order/automations",
    "handoff": "order/handoffs", "run": "order/runs", "session": "order/sessions",
    "document": "contracts", "meeting": "meetings", "risk": "risks",
    "milestone": "milestones", "deliverable": "deliverables",
    "dependency": "dependencies", "deadline": "deadlines", "inbox": "inbox",
    "tec": "decisions",
}

# §8.3 — vocabulário fechado de motivo de bloqueio
BLOCKED_REASONS = {
    "missing_checkpoint", "checkpoint_conflict", "no_local_worker",
    "no_model_capacity", "approval_rejected", "approval_expired",
    "dependency_failed", "entity_conflict", "quota_exceeded", "manual",
}

# §6 — vocabulário fechado de autoridade da fonte
AUTHORITY = {
    "canonical", "active", "historical", "superseded", "draft",
    "fixture", "do-not-answer-from",
}

# §7.6 — predicados tipados
PREDICADOS = {"causes", "fixes", "contradicts", "supersedes"}

RISCOS = ["A0", "A1", "A2", "A3", "A4"]


def novo_id(tipo: str, quando: _dt.datetime | None = None) -> str:
    prefixo = PREFIXOS.get(tipo)
    if not prefixo:
        raise ValueError(f"tipo desconhecido: {tipo}")
    quando = quando or _dt.datetime.now(_dt.timezone.utc)
    sufixo = "".join(secrets.choice(ALFABETO) for _ in range(6))
    return f"{prefixo}-{quando:%Y%m%d}-{sufixo}"


def tipo_de(entity_id: str) -> str | None:
    return TIPO_POR_PREFIXO.get(entity_id.split("-", 1)[0])


def id_valido(entity_id: str) -> bool:
    return bool(PADRAO.match(entity_id)) and tipo_de(entity_id) is not None


def agora() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
