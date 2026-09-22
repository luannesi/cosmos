"""
Índice derivado e busca (CHAOS §15, §19).

Contrato de reconstrução: `index rebuild` regenera tudo a partir dos arquivos, e
a mesma consulta devolve o mesmo conjunto antes e depois. Disto segue a regra que
sustenta a escolha de Markdown em Git como fonte: NENHUM dado existe apenas no
índice. Um índice não reconstruível é um banco primário disfarçado.

BM25 é baseline obrigatória; vetor é opcional e não entra aqui.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path

from . import entidades, yamlio

PALAVRA = re.compile(r"\w+", re.UNICODE)


def normalizar(texto: str) -> list[str]:
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return PALAVRA.findall(texto)


def construir(repo: Path) -> dict:
    docs = {}
    for path in entidades.todas(repo):
        try:
            fm, corpo = yamlio.ler(path)
        except Exception:
            continue
        texto = " ".join([str(fm.get("title", "")), corpo,
                          " ".join(str(v) for v in fm.values() if isinstance(v, str))])
        docs[fm.get("id", path.stem)] = {
            "tokens": normalizar(texto),
            "path": path.relative_to(repo).as_posix(),
            "title": fm.get("title", ""),
            "type": fm.get("type", ""),
            "privacy": fm.get("privacy", "cloud_allowed"),
            "authority": fm.get("authority", "active"),
            "valid_from": str(fm.get("valid_from") or ""),
            "valid_to": str(fm.get("valid_to") or ""),
        }
    return docs


def gravar(repo: Path, docs: dict) -> None:
    idx = repo / "indexes"
    idx.mkdir(parents=True, exist_ok=True)
    # ordenado e com separadores fixos: reconstrução byte a byte (AT-04)
    payload = {k: {kk: vv for kk, vv in sorted(v.items())} for k, v in sorted(docs.items())}
    (idx / "bm25.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")

    por_tipo: dict[str, list[str]] = {}
    for eid, d in sorted(docs.items()):
        por_tipo.setdefault(d["type"], []).append(eid)
    (idx / "por-tipo.json").write_text(
        json.dumps(por_tipo, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")

    g = repo / "graph"
    g.mkdir(parents=True, exist_ok=True)
    arestas = []
    for path in entidades.todas(repo):
        try:
            fm, _ = yamlio.ler(path)
        except Exception:
            continue
        for r in fm.get("relations") or []:
            if isinstance(r, dict) and r.get("target"):
                arestas.append({"from": fm.get("id"), "predicate": r.get("predicate"),
                                "to": r.get("target")})
        if fm.get("project"):
            arestas.append({"from": fm.get("id"), "predicate": "belongs_to",
                            "to": fm["project"]})
    (g / "graph.json").write_text(
        json.dumps(sorted(arestas, key=lambda a: json.dumps(a, sort_keys=True)),
                   ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")


def rebuild(repo: Path) -> int:
    docs = construir(repo)
    gravar(repo, docs)
    return len(docs)


def _carregar(repo: Path) -> dict:
    p = repo / "indexes" / "bm25.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return construir(repo)      # o índice é cache: ausente, reconstrói na hora


def vigente(d: dict, as_of: str | None) -> bool:
    """§15: `--as-of` resolve pela vigência, não pelo registro mais recente."""
    from .ids import agora
    corte = as_of or agora()[:10]
    vf, vt = d.get("valid_from") or "", d.get("valid_to") or ""
    if vf and vf[:10] > corte:
        return False
    if vt and vt[:10] <= corte:
        return False
    return True


def buscar(repo: Path, consulta: str, as_of: str | None = None,
           limite: int = 20) -> list[dict]:
    docs = _carregar(repo)
    termos = normalizar(consulta)
    if not termos:
        return []

    elegiveis = {k: v for k, v in docs.items() if vigente(v, as_of)}
    N = max(len(elegiveis), 1)
    df = {t: sum(1 for d in elegiveis.values() if t in d["tokens"]) for t in termos}
    avg = sum(len(d["tokens"]) for d in elegiveis.values()) / N if elegiveis else 1
    k1, b = 1.5, 0.75

    resultados = []
    for eid, d in elegiveis.items():
        score = 0.0
        L = len(d["tokens"]) or 1
        for t in termos:
            f = d["tokens"].count(t)
            if not f:
                continue
            idf = math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5))
            score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * L / avg))
        if score > 0:
            resultados.append({"id": eid, "score": round(score, 6),
                               "title": d["title"], "type": d["type"],
                               "path": d["path"], "authority": d["authority"]})
    resultados.sort(key=lambda r: (-r["score"], r["id"]))
    return resultados[:limite]
