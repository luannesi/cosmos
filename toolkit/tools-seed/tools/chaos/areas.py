"""
Área State (CHAOS §9, ORDER §23, §27).

Áreas são responsabilidades contínuas — não terminam, ao contrário de projetos.
Cada uma tem um agente dono no ORDER, e `areas/<slug>/state.md` é o que esse
agente mantém e o que todo contexto recebe.

O arquivo é **conteúdo, não governança** (CHAOS §4.1): o agente dono é
justamente quem deve mantê-lo. Por isso não é protected path. Mas parte dele é
derivada do repositório, e essa parte é regenerada — o que o humano ou o agente
escrevem (`narrative`, `next_steps`, `risks`) é preservado.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import ids, yamlio

DERIVADOS = ("task_count", "open_tasks", "blocked_tasks", "projects",
             "overdue", "updated_at", "kind", "area", "title")
PRESERVADOS = ("narrative", "next_steps", "risks", "priorities", "owner_agent")

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,48}$")


def caminho(repo: Path, slug: str) -> Path:
    return repo / "areas" / slug / "state.md"


def listar(repo: Path) -> list[str]:
    base = repo / "areas"
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir()
                  if p.is_dir() and (p / "state.md").exists())


def criar(repo: Path, slug: str, titulo: str, ator: str,
          agente: str = "") -> Path:
    from .repo import ErroChaos
    if not SLUG.match(slug):
        raise ErroChaos(
            f"slug de área inválido: `{slug}` — minúsculas, dígitos e hífen, "
            "até 49 caracteres (§7.2: o caminho é usado em filesystem "
            "insensível a caso)", "schema")
    p = caminho(repo, slug)
    if p.exists():
        raise ErroChaos(f"área `{slug}` já existe", "reference")
    p.parent.mkdir(parents=True, exist_ok=True)
    yamlio.escrever(p, {
        "kind": "canonical",          # o Área State é conteúdo, não view derivada
        "area": slug,
        "title": titulo or slug,
        "owner_agent": agente or f"agent.area.{slug}",
        "narrative": "",
        "priorities": [],
        "next_steps": [],
        "risks": [],
        "task_count": 0, "open_tasks": [], "blocked_tasks": [],
        "projects": [], "overdue": [],
        "created_at": ids.agora(), "updated_at": ids.agora(),
        "created_by": ator, "updated_by": ator,
    }, "")
    return p


def sincronizar(repo: Path, slug: str, ator: str) -> dict:
    """Regenera a parte derivada; preserva o que foi escrito por gente ou agente."""
    from . import entidades
    p = caminho(repo, slug)
    if not p.exists():
        return {}
    fm, corpo = yamlio.ler(p)

    tarefas, projetos, atrasadas = [], [], []
    hoje = ids.agora()[:10]
    for path in entidades.todas(repo):
        e, _ = yamlio.ler(path)
        if e.get("area") != slug:
            continue
        if e.get("type") == "task":
            tarefas.append(e)
            venc = str(e.get("due_date") or "")
            if venc and venc < hoje and e.get("status") not in ("done", "archived"):
                atrasadas.append(e["id"])
        elif e.get("type") == "project":
            projetos.append(e["id"])

    fm.update({
        "task_count": len(tarefas),
        "open_tasks": sorted(t["id"] for t in tarefas
                             if t.get("status") not in ("done", "archived")),
        "blocked_tasks": sorted(t["id"] for t in tarefas
                                if t.get("status") == "blocked"),
        "projects": sorted(projetos),
        "overdue": sorted(atrasadas),
        "updated_at": ids.agora(),
        "updated_by": ator,
    })
    yamlio.escrever(p, fm, corpo)
    return fm


def ler(repo: Path, slug: str) -> dict:
    p = caminho(repo, slug)
    return yamlio.ler(p)[0] if p.exists() else {}


def da_entidade(repo: Path, fm: dict) -> str:
    """A área de uma tarefa: declarada nela, ou herdada do projeto."""
    from . import entidades
    if fm.get("area"):
        return str(fm["area"])
    prj = fm.get("project")
    if prj:
        p = entidades.achar(repo, str(prj))
        if p:
            return str(yamlio.ler(p)[0].get("area") or "")
    return ""
