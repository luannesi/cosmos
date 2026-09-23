"""
Validador (CHAOS §20).

Categorias: syntax, schema, reference, semantic, integrity, policy, privacy.

Cada regra aqui nasceu de uma rodada adversarial. As que dependiam do spike de
identidade estavam agrupadas em `_identidade()`; o spike foi executado em
21/09/2026, falhou, e esta é a forma resultante: a autoridade migrou de
`_identidade()` (que agora só produz AVISOS) para `_assinatura()` (que produz
violações). O isolamento valeu a pena exatamente uma vez, que é o número de
vezes que ele precisava valer.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import assinatura, entidades, gitops, ids, ledger, yamlio
from .repo import PROTECTED, cfg_repo, eh_protegido, nuvem_alcanca

RESERVADOS_WIN = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | \
                 {f"LPT{i}" for i in range(1, 10)}
PROIBIDOS_WIN = set('<>:"|?*')

CONFIG_DIRS = ("order/policies", "metadata/policies", "metadata/registries", "metadata")


class Violacao:
    """
    `severidade` existe desde a v2.6 por uma razão específica.

    A v2.5 tratava "identidade de executor sem trailer" como `integrity`, isto
    é, como fronteira. O spike mostrou que identidade Git não é fronteira, mas
    a anomalia continua valendo alguma coisa: um executor bem-comportado sempre
    põe o trailer, e a ausência indica defeito de implementação ou caminho de
    escrita não governado. Apagar a regra perderia o sinal; mantê-la como erro
    mentiria sobre a garantia. Avisos são reportados e não reprovam.
    """

    def __init__(self, categoria: str, mensagem: str, onde: str = "",
                 severidade: str = "erro"):
        self.categoria, self.mensagem, self.onde = categoria, mensagem, onde
        self.severidade = severidade

    @property
    def eh_erro(self) -> bool:
        return self.severidade == "erro"

    def __str__(self) -> str:
        marca = "" if self.eh_erro else " (aviso)"
        base = f"[{self.categoria}]{marca}"
        return f"{base} {self.onde}: {self.mensagem}" if self.onde \
            else f"{base} {self.mensagem}"


def validar(repo: Path) -> list[Violacao]:
    v: list[Violacao] = []
    v += _sistema_de_arquivos(repo)
    v += _entidades(repo)
    v += _configs(repo)
    v += _identidade(repo)
    v += _assinatura(repo)
    v += _auditoria(repo)
    v += _marcadores(repo)
    return v


# --------------------------------------------------------------------------- #
def _sistema_de_arquivos(repo: Path) -> list[Violacao]:
    """§7.2: um repositório que viole isto simplesmente não clona no Windows."""
    v = []
    for p in repo.rglob("*"):
        if ".git" in p.parts or not p.is_file():
            continue
        rel = p.relative_to(repo).as_posix()
        if len(rel) > 200:
            v.append(Violacao("syntax", f"caminho acima de 200 caracteres", rel))
        for parte in p.relative_to(repo).parts:
            if set(parte) & PROIBIDOS_WIN:
                v.append(Violacao("syntax", "caractere proibido no Windows", rel))
            if parte.rstrip(". ") != parte:
                v.append(Violacao("syntax", "termina em ponto ou espaço", rel))
            if parte.split(".")[0].upper() in RESERVADOS_WIN:
                v.append(Violacao("syntax", "nome reservado do Windows", rel))
        if p.suffix in (".md", ".yaml", ".yml", ".json", ".jsonl", ".txt"):
            versionado = gitops.git(repo, "show", f"HEAD:{rel}")
            if versionado.returncode == 0 and "\r\n" in versionado.stdout:
                v.append(Violacao("syntax", "CRLF em arquivo versionado — §17.1 "
                                            "exige normalização", rel))
    return v


def _entidades(repo: Path) -> list[Violacao]:
    v = []
    vistos: dict[str, str] = {}
    for path in entidades.todas(repo):
        rel = path.relative_to(repo).as_posix()
        try:
            fm, _ = yamlio.ler(path)
        except Exception as exc:
            v.append(Violacao("syntax", f"frontmatter ilegível: {exc}", rel))
            continue

        eid = fm.get("id", "")
        if not ids.id_valido(str(eid)):
            v.append(Violacao("schema", f"ID fora do formato §7.2: {eid!r}", rel))
        if eid in vistos:
            v.append(Violacao("integrity", f"ID duplicado (também em {vistos[eid]})", rel))
        vistos[eid] = rel
        if path.stem != eid:
            v.append(Violacao("integrity", "§7.2: nome do arquivo tem de ser o ID", rel))

        if fm.get("status") == "blocked":
            motivo = str(fm.get("blocked_reason") or "").strip()
            if not motivo:
                v.append(Violacao("semantic", "§8.3: `status: blocked` sem "
                                              "`blocked_reason`", rel))
            elif motivo not in ids.BLOCKED_REASONS:
                v.append(Violacao("semantic", f"§8.3: `blocked_reason: {motivo}` fora "
                                              "do vocabulário fechado", rel))

        if fm.get("privacy") == "local_only":
            if fm.get("execution") in ("cloud", "any"):
                v.append(Violacao("privacy", "§8.3: `local_only` com `execution` "
                                             "incompatível", rel))
            if nuvem_alcanca(repo):
                v.append(Violacao("privacy", "§4.1: `local_only` em repositório "
                                             "alcançável pela nuvem", rel))

        aut = fm.get("authority")
        if aut and aut not in ids.AUTHORITY:
            v.append(Violacao("schema", f"§6: `authority: {aut}` fora do vocabulário", rel))
        if aut == "superseded" and not str(fm.get("valid_to") or "").strip():
            v.append(Violacao("semantic", "§7.1: `superseded` exige `valid_to`", rel))

        vf, vt = str(fm.get("valid_from") or ""), str(fm.get("valid_to") or "")
        if vf and vt and vt < vf:
            v.append(Violacao("semantic", "§7.1: `valid_to` anterior a `valid_from`", rel))

        for r in fm.get("relations") or []:
            if not isinstance(r, dict):
                continue
            if r.get("predicate") not in ids.PREDICADOS:
                v.append(Violacao("schema", f"§7.6: predicado `{r.get('predicate')}` "
                                            "fora do vocabulário", rel))
            alvo = r.get("target")
            if alvo and not entidades.achar(repo, str(alvo)):
                v.append(Violacao("reference", f"§7.6: `{alvo}` não existe", rel))

        for ref in (fm.get("provenance") or {}).get("source_refs") or []:
            if str(ref).startswith("episodic:"):
                v.append(Violacao("policy", "§4.2: registro episódico não é fonte "
                                            "primária — promova antes", rel))
    return v


def _configs(repo: Path) -> list[Violacao]:
    """§20: schema ausente para arquivo de configuração é erro, não aviso."""
    v = []
    schemas = repo / "metadata" / "schemas"
    for d in CONFIG_DIRS:
        base = repo / d
        if not base.is_dir():
            continue
        for p in sorted(base.glob("*.yaml")):
            rel = p.relative_to(repo).as_posix()
            schema_path = schemas / f"{p.stem}.schema.json"
            if not schema_path.exists():
                v.append(Violacao("schema", f"arquivo de configuração sem schema em "
                                            f"metadata/schemas/{p.stem}.schema.json — "
                                            "policy que não valida é policy que ninguém "
                                            "verifica", rel))
                continue
            try:
                dados = yamlio.ler_yaml(p)
                esquema = json.loads(schema_path.read_text(encoding="utf-8"))
            except Exception as exc:
                v.append(Violacao("schema", f"ilegível: {exc}", rel))
                continue
            try:
                import jsonschema
                jsonschema.validate(dados, esquema)
            except ImportError:
                v += _valida_minimo(dados, esquema, rel)
            except Exception as exc:
                primeira = str(exc).splitlines()[0]
                v.append(Violacao("schema", f"viola o schema: {primeira}", rel))
    return v


def _valida_minimo(dados, esquema, rel) -> list[Violacao]:
    """Fallback sem jsonschema: tipos e obrigatórios do primeiro nível."""
    v = []
    if esquema.get("type") == "object" and not isinstance(dados, dict):
        return [Violacao("schema", "esperava objeto", rel)]
    for k in esquema.get("required", []):
        if not isinstance(dados, dict) or k not in dados:
            v.append(Violacao("schema", f"campo obrigatório ausente: `{k}`", rel))
    props = esquema.get("properties", {})
    if isinstance(dados, dict):
        for k, sub in props.items():
            if k not in dados:
                continue
            tipo = sub.get("type")
            val = dados[k]
            if tipo == "integer" and not isinstance(val, int):
                v.append(Violacao("schema", f"`{k}` deveria ser inteiro", rel))
            if tipo == "object" and isinstance(val, dict):
                v += _valida_minimo(val, sub, rel)
            if "enum" in sub and val not in sub["enum"]:
                v.append(Violacao("schema", f"`{k}` fora do enum", rel))
    return v


def _identidade(repo: Path) -> list[Violacao]:
    """
    §17.1 (v2.6) — atribuição, não autorização.

    O spike de 21/09/2026 rebaixou esta função. Ela continua cruzando
    identidade e trailer porque a divergência é sintoma útil, mas NENHUMA
    decisão de autorização depende do que ela encontra: quem autoriza é
    `_assinatura()`. As duas regras de cruzamento saíram de `integrity` para
    aviso; a de protected path continua erro, agora como defesa em
    profundidade e não como garantia.
    """
    v = []
    reg = yamlio.ler_yaml(repo / "metadata" / "registries" / "executors.yaml") or {}
    por_email = {str(e.get("git_identity", "")).lower(): e
                 for e in reg.get("executors", [])}

    for c in gitops.commits(repo):
        entrada = por_email.get(c["email"])
        trailers = c["trailers"]
        ator = trailers.get("Actor", "")
        curto = c["hash"][:8]

        if entrada is None:
            v.append(Violacao("integrity", f"commit {curto}: credencial `{c['email']}` "
                                           "não consta em executors.yaml (§17.1)"))
            continue

        humano = entrada.get("kind") == "human"
        if humano and trailers:
            v.append(Violacao("integrity", f"commit {curto}: identidade humana COM "
                                           "trailer `Actor:` — anomalia de atribuição "
                                           "(v2.6: aviso, não fronteira)",
                              severidade="aviso"))
        if not humano and not trailers:
            v.append(Violacao("integrity", f"commit {curto}: identidade de executor SEM "
                                           "trailer `Actor:` — indica caminho de escrita "
                                           "não governado (v2.6: aviso)",
                              severidade="aviso"))
        if ator.startswith("agent:"):
            tocados = gitops.arquivos_do_commit(repo, c["hash"])
            for rel in tocados:
                if eh_protegido(rel):
                    v.append(Violacao("policy", f"commit {curto}: ator `{ator}` tocou "
                                                f"protected path `{rel}` (§4.1)"))
        if ator.startswith("human:") and not humano:
            v.append(Violacao("integrity", f"commit {curto}: credencial de executor "
                                           f"declarando ator humano `{ator}`",
                              severidade="aviso"))
    return v


def _assinatura(repo: Path) -> list[Violacao]:
    """
    §17.6 — a raiz de confiança, depois do spike.

    Regra única, positiva: escrita em protected path e decisão de APV A4 só
    valem em commit com assinatura verificável de chave `human:*`. Tudo o mais
    — autor, committer, trailers — é atribuição.

    Note que a ausência de `allowed_signers` NÃO é violação aqui. É estado
    inicial legítimo (AT-37): o sistema funciona em A0–A2 sem chave nenhuma e
    simplesmente não aprova nada de alto risco. O que seria violação é o
    inverso — protected path escrito sem assinatura quando o arquivo existe.
    """
    v: list[Violacao] = []

    for rel in assinatura.achar_chaves_privadas(repo):
        v.append(Violacao("policy", "chave privada em caminho versionado: um "
                                    "repositório que contenha a chave que o "
                                    "autoriza não autoriza nada (§17.6)", rel))

    desde = assinatura.commit_da_primeira_chave_humana(repo)
    if not desde:
        # AT-37: nenhuma chave humana JAMAIS existiu aqui. Não há o que exigir;
        # a ausência degrada a AUTONOMIA (ORDER §18 recusa abrir A4), não a
        # validade do repositório. Reprovar aqui tornaria impossível o estado
        # inicial, que é legítimo e é por onde todo repositório começa.
        #
        # O critério é "já existiu", não "está vigente hoje", de propósito: uma
        # vez estabelecida, a raiz de confiança não some porque a chave expirou.
        # Expirar a única chave humana deixa o repositório sem caminho de
        # aprovação — que é falhar fechando, e não voltar ao estado inicial.
        return v

    em_vigor = assinatura.commits_apos(repo, desde)

    for c in gitops.commits(repo):
        curto = c["hash"][:8]
        if em_vigor is not None and c["hash"] not in em_vigor:
            # Commits anteriores ao registro da primeira chave humana não
            # podiam ser assinados — não havia chave. Inclusive o `chaos init`,
            # que cria o próprio allowed_signers. Exigir assinatura deles seria
            # exigir que o sistema existisse antes de ser criado.
            continue
        tocados = gitops.arquivos_do_commit(repo, c["hash"])
        protegidos = [r for r in tocados
                      if eh_protegido(r) and not _crescimento_do_ledger(repo, c, r)]
        if not protegidos:
            continue
        ver = assinatura.verificar_commit(repo, c["hash"])
        if ver.eh_humano:
            continue
        if ver.estado == "B":
            v.append(Violacao("integrity", f"commit {curto}: assinatura INVÁLIDA — "
                                           "histórico adulterado ou chave trocada"))
            continue
        alvo = protegidos[0] + ("" if len(protegidos) == 1 else
                                f" (e mais {len(protegidos) - 1})")
        v.append(Violacao("integrity",
                          f"commit {curto} tocou protected path sem assinatura de "
                          f"chave `human:*` ({ver.motivo}) — §17.6", alvo))

    v += _allowed_signers_apagado(repo)
    return v


def _crescimento_do_ledger(repo: Path, commit: dict, rel: str) -> bool:
    """
    `audit/events.jsonl` está em protected paths, mas cresce por todo executor.

    A exceção já existia no caminho de escrita (`_recusar_protegidos`): o que
    se proíbe ali é REESCRITA, não crescimento. A regra de assinatura precisa
    da mesma exceção, e por pouco não passou sem ela — exigir assinatura
    humana para cada linha de auditoria tornaria o ledger inescrevível por
    quem o alimenta, que é o oposto do que §17.1 quer.

    Verificação: o arquivo no commit anterior é prefixo do arquivo neste
    commit. Se for, só cresceu.
    """
    if rel != "audit/events.jsonl":
        return False
    sha = commit["hash"]
    atual = gitops.git(repo, "show", f"{sha}:{rel}")
    if atual.returncode != 0:
        return False
    anterior = gitops.git(repo, "show", f"{sha}^:{rel}")
    antes = anterior.stdout if anterior.returncode == 0 else ""
    return atual.stdout.startswith(antes)


def _allowed_signers_apagado(repo: Path) -> list[Violacao]:
    """
    §17.6: revogar é expirar, nunca apagar.

    Apagar uma linha torna inverificáveis, retroativamente, todos os commits
    que aquela chave assinou — e um histórico que deixa de verificar é
    indistinguível de um histórico adulterado. A regra é verificável porque o
    próprio arquivo está versionado: basta comparar com a revisão anterior.
    """
    rel = assinatura.REL_ALLOWED_SIGNERS
    p = gitops.git(repo, "log", "--format=%H", "--", rel)
    revs = [r for r in p.stdout.split() if r]
    if len(revs) < 2:
        return []
    def chaves(rev: str) -> set[str]:
        saida = gitops.git(repo, "show", f"{rev}:{rel}").stdout
        return {l.split()[-2] if len(l.split()) >= 2 else l
                for l in (x.strip() for x in saida.splitlines())
                if l and not l.startswith("#")}
    atual, anterior = chaves(revs[0]), chaves(revs[1])
    sumidas = anterior - atual
    if sumidas:
        return [Violacao("integrity",
                         f"{len(sumidas)} chave(s) REMOVIDA(S) do allowed_signers entre "
                         f"{revs[1][:8]} e {revs[0][:8]} — §17.6 admite expirar com "
                         "`valid-before`, nunca apagar: apagar torna inverificáveis os "
                         "commits históricos daquela chave", rel)]
    return []


def _auditoria(repo: Path) -> list[Violacao]:
    """§17.1: toda alteração de entidade tem EVT correspondente."""
    v = []
    evts = ledger.ler(repo)
    conhecidos = {e.get("entity_id") for e in evts}
    n_evt_por_entidade: dict[str, int] = {}
    n_commits_por_entidade: dict[str, int] = {}
    for e in evts:
        eid = e.get("entity_id")
        # Só EVT de EXECUTOR cobre commit de executor. Um evento gravado pelo
        # humano ao criar a entidade não justifica uma escrita crua que um
        # executor fez depois — contá-lo deixaria passar exatamente o caso que
        # AT-07 procura.
        if eid and not str(e.get("actor", "")).startswith("human:"):
            n_evt_por_entidade[eid] = n_evt_por_entidade.get(eid, 0) + 1

    reg = yamlio.ler_yaml(repo / "metadata" / "registries" / "executors.yaml") or {}
    humanos = {str(e.get("git_identity", "")).lower()
               for e in reg.get("executors", []) if e.get("kind") == "human"}

    for c in gitops.commits(repo):
        # Implementação §11: edição manual por HUMANO é aceita e reconciliada;
        # toda escrita de entidade por EXECUTOR passa pelo CLI. A exigência de
        # EVT é sobre executores — exigi-la do humano tornaria o repositório
        # ineditável à mão, que é a promessa do AT-01.
        if c["email"] in humanos:
            continue
        for rel in gitops.arquivos_do_commit(repo, c["hash"]):
            if not rel.endswith(".md"):
                continue
            stem = Path(rel).stem
            if not ids.id_valido(stem):
                continue
            if stem not in conhecidos:
                v.append(Violacao("integrity", f"commit {c['hash'][:8]} altera `{stem}` "
                                               "sem EVT correspondente no ledger (§17.1)"))
            else:
                n_commits_por_entidade[stem] = n_commits_por_entidade.get(stem, 0) + 1

    # A regra anterior só via entidades com ZERO evento — e por isso deixava
    # passar o caso que importa: executor que altera à mão uma entidade que já
    # tem histórico. "Evento correspondente" é por ESCRITA, não por entidade;
    # descoberto ao reescrever AT-07 na v2.6, que até então passava pela regra
    # errada (identidade sem trailer, agora rebaixada a aviso).
    for eid, n_commits in n_commits_por_entidade.items():
        n_evt = n_evt_por_entidade.get(eid, 0)
        if n_commits > n_evt:
            v.append(Violacao("integrity",
                              f"`{eid}`: {n_commits} commit(s) de executor alteram a "
                              f"entidade e o ledger tem {n_evt} evento(s) — escrita de "
                              "executor fora do caminho governado (§17.1)"))
    return v


def _marcadores(repo: Path) -> list[Violacao]:
    v = []
    for p in repo.rglob("*.md"):
        if ".git" in p.parts:
            continue
        texto = p.read_text(encoding="utf-8", errors="replace")
        if "<<<<<<<" in texto or ">>>>>>>" in texto:
            v.append(Violacao("integrity", "marcador de conflito no arquivo",
                              p.relative_to(repo).as_posix()))
    return v
