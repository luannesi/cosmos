"""
Consultas ao grafo derivado (CHAOS §15).

O grafo era gravado e nunca lido — um índice que ninguém consulta é peso morto.
As três consultas que §15 nomeia: vizinhos, caminho e subárvore de projeto ou
área. Tudo derivado: apagar `graph/` e reconstruir devolve o mesmo resultado.
"""
from __future__ import annotations

import json
from collections import deque
from pathlib import Path


def carregar(repo: Path) -> list[dict]:
    p = repo / "graph" / "graph.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    from . import indice
    indice.rebuild(repo)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def _adjacencia(arestas: list[dict], dirigido: bool = False) -> dict[str, list[tuple]]:
    g: dict[str, list[tuple]] = {}
    for a in arestas:
        g.setdefault(a["from"], []).append((a["to"], a.get("predicate", "")))
        if not dirigido:
            g.setdefault(a["to"], []).append((a["from"], a.get("predicate", "")))
    return g


def vizinhos(repo: Path, no: str, predicado: str = "") -> list[dict]:
    g = _adjacencia(carregar(repo))
    return [{"id": destino, "predicate": p} for destino, p in g.get(no, [])
            if not predicado or p == predicado]


def caminho(repo: Path, origem: str, destino: str) -> list[str]:
    """Busca em largura: o caminho mais curto é o que responde 'como isto se liga àquilo'."""
    g = _adjacencia(carregar(repo))
    if origem not in g:
        return []
    fila = deque([[origem]])
    vistos = {origem}
    while fila:
        rota = fila.popleft()
        if rota[-1] == destino:
            return rota
        for prox, _ in g.get(rota[-1], []):
            if prox not in vistos:
                vistos.add(prox)
                fila.append(rota + [prox])
    return []


def subarvore(repo: Path, raiz: str, profundidade: int = 3) -> list[dict]:
    """Subárvore dirigida a partir de um projeto ou área — o que pende dele."""
    g = _adjacencia(carregar(repo), dirigido=True)
    saida, vistos = [], {raiz}
    fila = deque([(raiz, 0)])
    while fila:
        no, nivel = fila.popleft()
        if nivel >= profundidade:
            continue
        for prox, pred in g.get(no, []):
            if prox in vistos:
                continue
            vistos.add(prox)
            saida.append({"id": prox, "via": pred, "depth": nivel + 1})
            fila.append((prox, nivel + 1))
    return saida
