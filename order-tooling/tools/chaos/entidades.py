"""
Entidades canônicas: criação, atualização, leitura (CHAOS §7).

Regras que vivem aqui porque são do modelo, não da CLI:
- o ID é imutável e o nome do arquivo é o ID (§7.2), logo renomear título nunca move arquivo;
- `migrated_to` preenchido torna a entidade read-only (§7.1);
- supersessão preenche `valid_to` e `authority: superseded` do anterior (§7.1);
- evidências incompatíveis sobre o mesmo campo viram `conflicts`, nunca sobrescrita (§14).
"""
from __future__ import annotations

from pathlib import Path

from . import ids, yamlio
from .repo import ErroChaos, nuvem_alcanca

CAMPOS_COMUNS = ("id", "type", "schema_version", "title", "status",
                 "created_at", "updated_at", "created_by", "updated_by")


def pasta_de(repo: Path, tipo: str, projeto: str | None = None) -> Path:
    if tipo == "task" and projeto:
        prj = achar(repo, projeto)
        if prj:
            return prj.parent / "tasks"
    return repo / ids.PASTAS[tipo]


def achar(repo: Path, entity_id: str) -> Path | None:
    hits = [p for p in repo.rglob(f"{entity_id}.md") if ".git" not in p.parts]
    return hits[0] if len(hits) == 1 else (hits[0] if hits else None)


def todas(repo: Path) -> list[Path]:
    saida = []
    for p in repo.rglob("*.md"):
        if ".git" in p.parts or p.name in {"state.md", "README.md", "AGENTS.md", "CLAUDE.md"}:
            continue
        if ids.id_valido(p.stem):
            saida.append(p)
    return sorted(saida)


def _base(tipo: str, entity_id: str, ator: str, titulo: str) -> dict:
    return {
        "id": entity_id,
        "type": tipo,
        "schema_version": "2.5",
        "title": titulo,
        "status": _status_inicial(tipo),
        "created_at": ids.agora(),
        "updated_at": ids.agora(),
        "created_by": ator,
        "updated_by": ator,
        "authority": "active",
        "valid_from": "",
        "valid_to": "",
        "relations": [],
        "conflicts": [],
        "provenance": {
            "origin": "human" if ator.startswith("human:") else "agent",
            "source_refs": [],
            "confidence": "unknown",
            "epistemic_status": "unknown",
            "verified_at": "",
            "verified_by": "",
        },
    }


def _status_inicial(tipo: str) -> str:
    return {
        "task": "todo", "project": "active", "decision": "proposed",
        "approval": "pending", "automation": "registered", "handoff": "open",
        "run": "claimed", "session": "open", "inbox": "raw",
    }.get(tipo, "active")


def criar(repo: Path, tipo: str, ator: str, opcoes: dict) -> dict:
    titulo = opcoes.get("title") or "(sem título)"
    entity_id = ids.novo_id(tipo)
    fm = _base(tipo, entity_id, ator, titulo)

    if tipo == "task":
        fm.update({"priority": "normal", "privacy": "cloud_allowed",
                   "execution": "any", "blocked_reason": "",
                   "project": "", "area": "", "parent_task": "", "claimed_by": "",
                   "lease_until": "", "risk_hint": "", "model_policy": "",
                   "has_conflict": False, "evidence": {}})
    elif tipo == "project":
        fm["area"] = ""
    elif tipo == "decision":
        fm.update({"context": "", "alternatives": [], "decided_by": "",
                   "outcome": "", "approval": ""})
    elif tipo == "approval":
        fm.update({"risk": opcoes.get("risk", "A3"), "action": opcoes.get("action", ""),
                   "decided_by": "", "decision_note": "",
                   "expires_at": "", "run": ""})
    elif tipo == "automation":
        fm.update({"name": opcoes.get("name", titulo), "trigger": opcoes.get("trigger", "time"),
                   "mode": "shadow", "max_risk": opcoes.get("max_risk", "A1"),
                   "enabled": False, "quota": 0})
        fm["title"] = opcoes.get("name") or titulo
    elif tipo == "run":
        fm.update({"task": opcoes.get("task", ""), "mode": "normal",
                   "resumes_run": "", "has_conflict": False,
                   "risk_class": "A1", "checkpoint": {}})
    elif tipo == "handoff":
        fm.update({"from_agent": "", "to_agent": "", "objective": "",
                   "context_refs": [], "constraints": [], "open_questions": [],
                   "task": ""})
    elif tipo == "inbox":
        fm["provenance"]["origin"] = "external_source"
        fm["provenance"]["epistemic_status"] = "unknown"

    aplicar_opcoes(repo, fm, opcoes, ator, criando=True)
    return fm


def aplicar_opcoes(repo: Path, fm: dict, opcoes: dict, ator: str, criando: bool = False) -> None:
    """Aplica as opções de CLI ao frontmatter, com as regras do modelo."""
    for chave, valor in opcoes.items():
        if valor is None:
            continue
        if chave in ("title",):
            fm["title"] = valor
        elif chave == "privacy":
            if valor == "local_only" and nuvem_alcanca(repo):
                raise ErroChaos(
                    "§4.1: `privacy: local_only` é proibido em repositório cujo "
                    "remote é alcançável pela nuvem — o clone já levaria o conteúdo. "
                    "A fronteira é a credencial, não o campo.", "privacy")
            fm["privacy"] = valor
            if valor == "local_only":
                fm["execution"] = "local"
        elif chave == "execution":
            fm["execution"] = valor
        elif chave == "authority":
            if valor not in ids.AUTHORITY:
                raise ErroChaos(
                    f"§6: `authority: {valor}` fora do vocabulário fechado "
                    f"({', '.join(sorted(ids.AUTHORITY))})", "schema")
            fm["authority"] = valor
        elif chave in ("priority", "risk_hint", "model_policy", "project", "area",
                       "parent_task", "name", "trigger", "max_risk", "action", "risk"):
            fm[chave] = valor
        elif chave == "valid_from":
            fm["valid_from"] = valor
        elif chave == "text":
            fm["title"] = (valor[:80] + "…") if len(valor) > 80 else valor
            fm.setdefault("_corpo", valor)
        elif chave == "field":
            for par in valor if isinstance(valor, list) else [valor]:
                if "=" in par:
                    k, v = par.split("=", 1)
                    fm[k.strip()] = v.strip()
        elif chave == "source_refs":
            refs = list(valor) if isinstance(valor, list) else [valor]
            for ref in refs:
                if str(ref).startswith("episodic:"):
                    raise ErroChaos(
                        "§4.2: registro da camada episódica não é fonte primária — "
                        "ele não passou pelo guard e não foi classificado. Promova "
                        "com `chaos promote` e aponte para a entidade resultante.",
                        "policy")
            fm["provenance"]["source_refs"] = refs

    # coerência §8.3: local_only implica execution local
    if fm.get("privacy") == "local_only" and fm.get("execution") not in (None, "", "local"):
        raise ErroChaos("§8.3: `privacy: local_only` exige `execution: local`", "semantic")

    fm["updated_at"] = ids.agora()
    fm["updated_by"] = ator


def registrar_evidencia(fm: dict, campo: str, valor, fonte: str) -> None:
    """
    §14: duas fontes sustentando valores incompatíveis do mesmo campo não se
    sobrescrevem — o desacordo é registrado e nenhuma some.
    """
    ev = fm.setdefault("evidence", {})
    anterior = ev.get(campo)
    if anterior and anterior.get("value") != valor:
        fm.setdefault("conflicts", []).append({
            "field": campo,
            "values": [anterior.get("value"), valor],
            "sources": [anterior.get("source"), fonte],
            "detected_at": ids.agora(),
        })
    ev[campo] = {"value": valor, "source": fonte}


def carregar(repo: Path, entity_id: str) -> tuple[Path, dict, str]:
    path = achar(repo, entity_id)
    if not path:
        raise ErroChaos(f"entidade `{entity_id}` não encontrada", "reference")
    fm, corpo = yamlio.ler(path)
    return path, fm, corpo


def exigir_editavel(fm: dict) -> None:
    if str(fm.get("migrated_to") or "").strip():
        raise ErroChaos(
            f"§7.1: `{fm['id']}` tem `migrated_to` preenchido e é read-only — "
            "a cópia viva está no repositório de destino", "policy")
