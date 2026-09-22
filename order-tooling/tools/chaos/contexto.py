"""
Context Builder (CHAOS §16).

Duas exclusões são normativas e é aqui que elas vivem:
- `authority: do-not-answer-from` nunca entra em contexto montado (continua
  recuperável por busca explícita);
- o bloco `episodic` nunca é fundido a `entities` — é continuidade, não evidência.

E a regra de privacidade: nada `local_only` entra em contexto de executor nuvem,
e nada atravessa `privacy_class`.
"""
from __future__ import annotations

from pathlib import Path

from . import areas, entidades, episodico, yamlio
from .repo import cfg_repo


def montar(repo: Path, *, executor: str = "local", task: str = "",
           source: str = "", agent: str = "", area: str = "",
           as_of: str | None = None, token_budget: int = 8000) -> dict:
    ctx = {
        "bootstrap": "AGENTS.md",
        "state": [], "handoffs": [], "entities": [], "decisions": [],
        "sources": [], "constraints": [], "conflicts": [], "warnings": [],
        "untrusted": [], "episodic": [],
    }
    prov = []
    cfg = cfg_repo(repo)
    classe = cfg.get("privacy_class", "")

    # ORDER §23: o Área State entra no INÍCIO de todo contexto de agente.
    # É o que responde "sobre o que estamos falando" antes de qualquer entidade.
    slug = area
    if not slug and task:
        p_t = entidades.achar(repo, task)
        if p_t:
            slug = areas.da_entidade(repo, yamlio.ler(p_t)[0])
    if slug:
        st = areas.ler(repo, slug)
        if st:
            ctx["state"].append({"area": slug, "title": st.get("title"),
                                 "narrative": st.get("narrative", ""),
                                 "priorities": st.get("priorities", []),
                                 "open_tasks": st.get("open_tasks", []),
                                 "blocked_tasks": st.get("blocked_tasks", []),
                                 "next_steps": st.get("next_steps", [])})

    alvos = []
    if task:
        p = entidades.achar(repo, task)
        if p:
            alvos.append(p)
    if source:
        p = entidades.achar(repo, source)
        if p:
            alvos.append(p)
    if not alvos:
        alvos = entidades.todas(repo)

    for path in alvos:
        try:
            fm, corpo = yamlio.ler(path)
        except Exception:
            continue

        # §16: local_only nunca entra em contexto de executor nuvem
        if fm.get("privacy") == "local_only" and executor == "cloud":
            continue
        # §6/§16: material marcado como não citável não entra em contexto montado
        if fm.get("authority") == "do-not-answer-from":
            ctx["warnings"].append(
                f"{fm.get('id')} existe como registro mas é `do-not-answer-from`")
            continue

        item = {"id": fm.get("id"), "type": fm.get("type"),
                "title": fm.get("title"), "privacy_class": classe}
        origem = (fm.get("provenance") or {}).get("origin")
        if origem == "external_source":
            item["untrusted"] = True
            ctx["untrusted"].append({"id": fm.get("id"), "excerpt": corpo[:200],
                                     "untrusted": True})
        if fm.get("type") == "decision":
            ctx["decisions"].append(item)
        elif fm.get("type") == "source":
            ctx["sources"].append(item)
        elif fm.get("type") == "handoff":
            ctx["handoffs"].append(item)
        else:
            ctx["entities"].append(item)

        if fm.get("conflicts"):
            ctx["conflicts"].append({"id": fm.get("id"), "conflicts": fm["conflicts"]})
        prov.append({"id": fm.get("id"), "origin": origem})

    # §4.2: bloco separado, orçamento próprio, jamais evidência.
    # A consulta usa o TÍTULO da entidade quando ela resolve; o identificador cru
    # não é termo de busca útil.
    termo = ""
    for ref in (task, source):
        if ref:
            p_ref = entidades.achar(repo, ref)
            if p_ref:
                termo = yamlio.ler(p_ref)[0].get("title", "") or ""
                break
    ctx["episodic"] = episodico.consultar(repo, termo, limite=5)
    ctx["provenance"] = prov
    ctx["token_budget"] = token_budget
    return ctx
