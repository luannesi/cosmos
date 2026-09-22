"""
CLI do `chaos` — CHAOS §21 é o contrato completo.

Um binding pode acrescentar comandos do seu perfil, mas MUST NOT declarar lista
paralela nem renomear estes. `guard`, `risk eval`, `delegate` e `trigger`
pertencem à CLI do `order`, não a esta.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import (areas, assinatura, contexto, entidades, episodico, gitops, grafo,
               ids, indice, layout, ledger, onboarding, saude, validador, yamlio)
from .repo import ErroChaos, Identidade, achar_repo, cfg_repo, eh_protegido

TIPOS = sorted(ids.PREFIXOS)


def saida(dados, formato: str = "json") -> None:
    if formato == "json" or isinstance(dados, (dict, list)):
        print(json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(dados)


# --------------------------------------------------------------------------- #
# commit e sincronização — o único caminho de agentes (§21)                    #
# --------------------------------------------------------------------------- #

def _apenas_append(repo: Path, rel: str) -> bool:
    """A versão em disco começa com a versão comitada? Então só cresceu."""
    atual = (repo / rel)
    if not atual.exists():
        return False
    p = gitops.git(repo, "show", f"HEAD:{rel}")
    anterior = p.stdout if p.returncode == 0 else ""
    return atual.read_text(encoding="utf-8").startswith(anterior)


def _recusar_protegidos(repo: Path, ident: Identidade, rels: list[str]) -> None:
    if ident.eh_humano:
        return
    for rel in rels:
        if rel == "audit/events.jsonl":
            # O ledger cresce pelo adapter, que qualquer executor invoca (§4.1).
            # O que se recusa é REESCRITA: perder ou alterar linha é o dano que
            # "append-only" existe para impedir, e isso é verificável aqui.
            if _apenas_append(repo, rel):
                continue
            raise ErroChaos(
                "`audit/events.jsonl` só cresce (§17.1): esta mudança reescreve "
                "ou remove linha já gravada, o que nenhum ator pode fazer",
                "integrity")
        if eh_protegido(rel):
            raise ErroChaos(
                f"`{rel}` é protected path (CHAOS §4.1): governa o comportamento de "
                f"agentes futuros. Ator `{ident.pretendido}` não escreve aqui — "
                "abra uma tarefa A4 para o humano.", "policy")


def commit(repo: Path, ident: Identidade, mensagem: str,
           evento: dict | None = None) -> str | None:
    """Injeta os trailers ANTES do commit, recusa protected paths, exige EVT."""
    rels = gitops.arquivos_modificados(repo)
    if not rels:
        return None
    _recusar_protegidos(repo, ident, rels)

    ator = ident.ator
    corpo = mensagem
    if not ident.eh_humano:
        corpo += f"\n\nActor: {ator}\nSurface: {ident.surface}"

    gitops.git(repo, "add", "-A")
    p = gitops.git(repo, *_args_de_assinatura(repo, ident),
                   "commit", "-q", "-m", corpo)
    if p.returncode != 0 and "nothing to commit" not in (p.stdout + p.stderr):
        raise ErroChaos(f"commit falhou: {p.stderr.strip()}", "integrity")
    return gitops.head(repo)


def _args_de_assinatura(repo: Path, ident: Identidade) -> list[str]:
    """
    Marca de PROCEDÊNCIA do worker (ORDER §18).

    O worker assina para dizer "esta ação veio da máquina do usuário", nunca
    "uma pessoa autorizou" — são principais distintos e a verificação é por
    principal, não por presença de assinatura. Assinar por padrão porque
    procedência só é verificável se gravada no momento: um commit antigo sem
    assinatura é indistinguível de um que veio da nuvem.

    Quem NÃO assina aqui: a nuvem (não tem chave — medido no spike) e o humano
    (a chave dele tem frase-secreta e é acionada pelo Git dele, não por este
    caminho; assinar A4 em nome dele a partir de um comando de CLI seria
    exatamente o oráculo que §17.6 recusa).
    """
    if not ident.ator.startswith("executor:"):
        return []
    cfg = yamlio.ler_yaml(repo / "order" / "policies" / "worker.yaml") or {}
    if cfg.get("signature_mode", "always") != "always":
        return []
    chave = os.environ.get("CHAOS_WORKER_SIGNING_KEY", "").strip()
    if not chave or not Path(chave).exists():
        # Ausência de chave não impede o commit: procedência é informação
        # adicional, não portão. O portão é a assinatura HUMANA, e a falta
        # dela já nega A4 no caminho de aprovação.
        return []
    return ["-c", "gpg.format=ssh", "-c", f"user.signingkey={chave}", "-c",
            "commit.gpgsign=true"]


def _registrar_e_comitar(repo: Path, ident: Identidade, *, action: str,
                         entity_id: str, risk: str = "A1", mensagem: str,
                         level: str = "info", summary: str = "") -> None:
    ledger.append(repo, actor=ident.ator, surface=ident.surface, action=action,
                  risk_class=risk, entity_id=entity_id, level=level, summary=summary)
    commit(repo, ident, mensagem)


# --------------------------------------------------------------------------- #
# entidades                                                                     #
# --------------------------------------------------------------------------- #

def cmd_create(repo: Path, ident: Identidade, tipo: str, args) -> None:
    opcoes = _opcoes(args)
    fm = entidades.criar(repo, tipo, ident.ator, opcoes)
    corpo = fm.pop("_corpo", "")

    destino = entidades.pasta_de(repo, tipo, opcoes.get("project"))
    if tipo == "project":
        destino = destino / fm["id"]
    path = destino / f"{fm['id']}.md"

    if not ident.eh_humano:
        _recusar_protegidos(repo, ident, [path.relative_to(repo).as_posix()])

    if opcoes.get("supersedes"):
        _superseder(repo, ident, opcoes["supersedes"], fm)

    yamlio.escrever(path, fm, corpo)
    if tipo == "project":
        _escrever_state(repo, fm["id"])
    elif fm.get("project"):
        # O state é derivado: criar tarefa dentro de um projeto muda o derivado,
        # e deixá-lo defasado tornaria a "reprodutibilidade" do AT-02 falsa.
        _escrever_state(repo, fm["project"])
    _sincronizar_area(repo, ident, fm)

    _registrar_e_comitar(repo, ident, action=f"{tipo}.create", entity_id=fm["id"],
                         mensagem=f"cria {fm['id']}: {fm['title']}",
                         summary=fm["title"])
    saida({"id": fm["id"], "path": path.relative_to(repo).as_posix()})


def _superseder(repo: Path, ident: Identidade, anterior: str, novo: dict) -> None:
    """§7.1: supersessão em vez de sobrescrita — nada é apagado."""
    path, fm, corpo = entidades.carregar(repo, anterior)
    entidades.exigir_editavel(fm)
    fm["valid_to"] = novo.get("valid_from") or ids.agora()
    fm["authority"] = "superseded"
    fm["updated_at"] = ids.agora()
    fm["updated_by"] = ident.ator
    yamlio.escrever(path, fm, corpo)
    novo.setdefault("relations", []).append(
        {"predicate": "supersedes", "target": anterior, "note": ""})
    ledger.append(repo, actor=ident.ator, surface=ident.surface,
                  action="entity.supersede", entity_id=anterior, risk_class="A1")


def cmd_update(repo: Path, ident: Identidade, tipo: str, args) -> None:
    entity_id = args.id
    path, fm, corpo = entidades.carregar(repo, entity_id)
    entidades.exigir_editavel(fm)
    rel = path.relative_to(repo).as_posix()
    if not ident.eh_humano:
        _recusar_protegidos(repo, ident, [rel])

    opcoes = _opcoes(args)

    # rebaixamento de privacidade é A4 (ORDER §14): não é executado por agente
    for campo in ("privacy", "execution", "privacy_class"):
        if campo in opcoes and opcoes[campo] is not None:
            antigo, novo = fm.get(campo), opcoes[campo]
            if _rebaixa(campo, antigo, novo) and not ident.eh_humano:
                raise ErroChaos(
                    f"alterar `{campo}` de `{antigo}` para `{novo}` é **A4** "
                    "(ORDER §14: reversibilidade é do efeito, não do arquivo) — "
                    "exige commit humano fora do caminho do modelo", "policy")

    evidencia = opcoes.pop("evidence", None)
    for campo_ev in ("due_date",):
        if evidencia and opcoes.get(campo_ev) is not None:
            entidades.registrar_evidencia(fm, campo_ev, opcoes[campo_ev], evidencia)

    for k, v in list(opcoes.items()):
        if k in ("due_date",):
            fm[k] = v
            opcoes.pop(k)

    entidades.aplicar_opcoes(repo, fm, opcoes, ident.ator)
    yamlio.escrever(path, fm, corpo)
    if fm.get("project"):
        _escrever_state(repo, fm["project"])
    _sincronizar_area(repo, ident, fm)

    _registrar_e_comitar(repo, ident, action=f"{tipo}.update", entity_id=entity_id,
                         mensagem=f"atualiza {entity_id}")
    saida({"id": entity_id, "updated_at": fm["updated_at"]})


def _rebaixa(campo: str, antigo, novo) -> bool:
    if campo == "privacy":
        return antigo == "local_only" and novo == "cloud_allowed"
    if campo == "execution":
        return antigo == "local" and novo in ("cloud", "any")
    if campo == "privacy_class":
        return antigo != novo
    return False


def cmd_show(repo: Path, ident: Identidade, tipo: str, args) -> None:
    path, fm, corpo = entidades.carregar(repo, args.id)
    if tipo == "project":
        _escrever_state(repo, args.id)
    saida({"frontmatter": fm, "body": corpo,
           "path": path.relative_to(repo).as_posix()})


def cmd_list(repo: Path, ident: Identidade, tipo: str, args) -> None:
    itens = []
    for path in entidades.todas(repo):
        fm, _ = yamlio.ler(path)
        if fm.get("type") == tipo:
            itens.append({"id": fm["id"], "title": fm.get("title"),
                          "status": fm.get("status")})
    saida(sorted(itens, key=lambda i: i["id"]))


def _escrever_state(repo: Path, prj_id: str) -> None:
    """
    §9.1: Project State é derivado e regenerável; `narrative` é humano e
    preservado quando existe, nascendo vazio na reconstrução a partir de clone
    limpo — sua ausência nunca é divergência.
    """
    path = entidades.achar(repo, prj_id)
    if not path:
        return
    state = path.parent / "state.md"
    narrativa = ""
    if state.exists():
        try:
            fm_ant, corpo_ant = yamlio.ler(state)
            narrativa = fm_ant.get("narrative", "") or ""
        except Exception:
            pass

    tarefas = []
    for p in entidades.todas(repo):
        fm, _ = yamlio.ler(p)
        if fm.get("project") == prj_id:
            tarefas.append(fm)

    fm_prj, _ = yamlio.ler(path)
    derivado = {
        "kind": "derived",
        "project": prj_id,
        "title": fm_prj.get("title", ""),
        "task_count": len(tarefas),
        "open_tasks": sorted(t["id"] for t in tarefas if t.get("status") != "done"),
        "blocked_tasks": sorted(t["id"] for t in tarefas if t.get("status") == "blocked"),
        "narrative": narrativa,
    }
    yamlio.escrever(state, derivado, "")


def _sincronizar_area(repo: Path, ident: Identidade, fm: dict) -> None:
    slug = areas.da_entidade(repo, fm)
    if slug and areas.caminho(repo, slug).exists():
        areas.sincronizar(repo, slug, ident.ator)


def cmd_area(repo: Path, ident: Identidade, args) -> None:
    """
    §9/§27: a área é responsabilidade contínua, com agente dono e um State que
    todo contexto recebe. O arquivo é conteúdo — o agente dono é quem o mantém —
    e por isso NÃO é protected path (§4.1 separa governança de conteúdo).
    """
    if args.sub == "create":
        p = areas.criar(repo, args.slug, args.title or args.slug, ident.ator,
                        args.owner_agent or "")
        areas.sincronizar(repo, args.slug, ident.ator)
        ledger.append(repo, actor=ident.ator, surface=ident.surface,
                      action="area.create", entity_id=args.slug, risk_class="A1")
        commit(repo, ident, f"cria área {args.slug}")
        saida({"area": args.slug, "path": p.relative_to(repo).as_posix()})
    elif args.sub == "sync":
        alvos = [args.slug] if args.slug else areas.listar(repo)
        for slug in alvos:
            areas.sincronizar(repo, slug, ident.ator)
        commit(repo, ident, f"sincroniza {len(alvos)} área(s)")
        saida({"synced": alvos})
    elif args.sub == "show":
        saida(areas.ler(repo, args.slug))
    else:
        saida([{"area": s, **{k: v for k, v in areas.ler(repo, s).items()
                              if k in ("title", "task_count", "blocked_tasks")}}
               for s in areas.listar(repo)])


def _opcoes(args) -> dict:
    ignorar = {"func", "tipo", "id", "formato", "comando", "sub", "message",
               "reason", "dry_run", "keep", "as_of", "entity", "target", "into",
               "as_type", "text_positional"}
    out = {}
    for k, v in vars(args).items():
        if k in ignorar or v is None:
            continue
        out[k] = v
    return out


# --------------------------------------------------------------------------- #
# comandos de repositório                                                       #
# --------------------------------------------------------------------------- #

def cmd_init(args) -> None:
    """
    §17.6: o `init` é o único momento em que `allowed_signers` é escrito sem
    assinatura prévia — não há chave ainda. A janela é fechada aqui, do único
    jeito possível: `init` recusa rodar sob ator que não seja humano.

    Não é defesa forte, e não pretende ser: quem controla a variável de
    ambiente controla a declaração. É defesa contra o caso realista — uma
    sessão de agente que, por instrução embutida ou por engano, rode `chaos
    init` num diretório e se registre como a primeira chave humana. Contra
    adversário com shell na máquina do usuário, a barreira é a frase-secreta,
    não esta linha.
    """
    ator_declarado = (os.environ.get("CHAOS_ACTOR") or "").strip()
    if ator_declarado and not ator_declarado.startswith("human:"):
        raise ErroChaos(
            f"`chaos init` cria a raiz de confiança do repositório e recusa "
            f"rodar como `{ator_declarado}` (§17.6). Quem escreve a primeira "
            "linha do allowed_signers define quem é humano — esse commit é o "
            "único isento de assinatura, e por isso acontece no Onboarding, "
            "antes de existir agente.", "policy")
    repo = Path.cwd()
    (repo / ".git").exists() or gitops.git(repo, "init", "-q", "-b", "main")
    layout.init(repo, args.privacy_class, args.owner)
    gitops.git(repo, "add", "-A")
    gitops.git(repo, "commit", "-q", "-m", f"chaos init: classe {args.privacy_class}")
    _configurar_verificacao_local(repo)
    saida({"repo": str(repo), "privacy_class": args.privacy_class,
           "owner": args.owner, "tag": layout.TAG})


def _configurar_verificacao_local(repo: Path) -> None:
    """
    Configuração Git LOCAL do repositório para verificar assinatura (§17.6).

    Não é versionada e não é segurança — as ferramentas passam `-c` em toda
    verificação justamente para não depender dela. Existe para o humano: sem
    isto, `git log --show-signature` na máquina não verifica nada, e o usuário
    vê `N` num commit assinado, que é a leitura mais enganosa possível.

    Um clone novo não herda config local. Quem clona roda `chaos bootstrap
    sync`, que chama isto de novo.
    """
    gitops.git(repo, "config", "gpg.format", "ssh")
    gitops.git(repo, "config", "gpg.ssh.allowedSignersFile",
               str(repo / "metadata" / "registries" / "allowed_signers"))


def cmd_validate(repo: Path, ident: Identidade, args) -> int:
    violacoes = validador.validar(repo)
    erros = [v for v in violacoes if v.eh_erro]
    if args.formato == "json":
        saida([{"category": v.categoria, "where": v.onde, "message": v.mensagem,
                "severity": v.severidade} for v in violacoes])
    else:
        for v in violacoes:
            print(str(v))
        if not violacoes:
            print("[ok] nenhuma violação")
        elif not erros:
            print(f"[ok] nenhum erro ({len(violacoes)} aviso(s))")
    return 1 if erros else 0


def cmd_key(repo: Path, ident: Identidade, args) -> int:
    """
    `chaos key` — gera, prepara e verifica. NUNCA autoriza.

    A assimetria entre `new`/`register` e o registro efetivo é o ponto do
    comando. Gerar um par de chaves é inofensivo; acrescentá-lo ao
    `allowed_signers` é conceder autoridade, e é commit em protected path —
    portanto humano e assinado, pela regra que o próprio arquivo define. Um
    `key register` que comitasse sozinho seria a porta que §17.6 existe para
    trancar, com o nome mais inocente possível.
    """
    if args.sub == "new":
        destino = Path(args.arquivo).expanduser() if args.arquivo else \
            (repo / ".." / f"chaos-{args.papel.replace(':', '-')}").resolve()
        if destino.exists():
            raise ErroChaos(f"`{destino}` já existe — não sobrescrevo chave "
                            "privada por acidente", "policy")
        if args.papel.startswith("human:") and args.sem_frase:
            raise ErroChaos(
                "chave `human:*` sem frase-secreta é um oráculo de assinatura: "
                "qualquer processo na máquina assina como você, e a presença "
                "humana que A4 exige deixa de existir (§17.6)", "policy")
        cmd = ["ssh-keygen", "-t", "ed25519", "-f", str(destino),
               "-C", args.principal]
        if args.sem_frase:
            cmd += ["-N", ""]
        # A saída do ssh-keygen vai para stderr: stdout deste comando é JSON,
        # e o randomart no meio dele quebraria qualquer consumidor. Não usamos
        # capture_output porque a chave humana pede frase-secreta de forma
        # interativa — capturar mataria o prompt, que é justamente o controle.
        r = subprocess.run(cmd, stdout=sys.stderr)
        if r.returncode != 0:
            raise ErroChaos("ssh-keygen falhou", "policy")
        saida({"papel": args.papel, "privada": str(destino),
               "publica": str(destino) + ".pub",
               "proximo_passo": f"chaos key register {args.papel} "
                                f"{destino}.pub",
               "aviso": "a chave PRIVADA nunca entra em repositório algum"})
        return 0

    if args.sub == "register":
        pub = Path(args.arquivo).expanduser().read_text(encoding="utf-8").split()
        if len(pub) < 2:
            raise ErroChaos(f"`{args.arquivo}` não parece uma chave pública", "syntax")
        hoje = _dt.date.today().strftime("%Y%m%d")
        linha = (f'{args.principal} namespaces="git",valid-after="{hoje}" '
                 f'{pub[0]} {pub[1]} {args.papel}')
        saida({
            "linha": linha,
            "arquivo": assinatura.REL_ALLOWED_SIGNERS,
            "instrucao": "acrescente esta linha ao arquivo e comite — é "
                         "protected path, portanto humano e assinado. Este "
                         "comando NÃO comita de propósito (§17.6).",
            "opcoes_separadas_por_virgula": "sim — espaço quebra o OpenSSH "
                                            "silenciosamente e a assinatura "
                                            "passa a devolver U em vez de G",
        })
        return 0

    if args.sub == "verify":
        v = assinatura.verificar_commit(repo, args.ref or "HEAD")
        saida({"ref": args.ref or "HEAD", "verificada": v.verificada,
               "estado": v.estado, "principal": v.principal, "ator": v.ator,
               "humano": v.eh_humano, "worker": v.eh_worker, "motivo": v.motivo})
        return 0 if v.verificada else 1

    if args.sub == "list":
        hoje = _dt.date.today()
        saida([{"principal": l.principal, "papel": assinatura.papel_do_principal(
                    repo, l.principal), "opcoes": l.opcoes,
                "vigente": l.vigente_em(hoje), "comentario": l.comentario}
               for l in assinatura.ler_allowed_signers(repo)])
        return 0

    raise ErroChaos(f"subcomando `{args.sub}` desconhecido em `chaos key`", "syntax")


def cmd_health(repo: Path, args) -> int:
    estado = saude.avaliar(repo)
    saida(estado)
    return saude.codigo_de_saida(estado["status"])


def cmd_status(repo: Path, args) -> None:
    evts = ledger.ler(repo)
    saida({
        "repo_id": cfg_repo(repo).get("repo_id"),
        "privacy_class": cfg_repo(repo).get("privacy_class"),
        "paused": (repo / "order" / "PAUSED").exists(),
        "entities": len(entidades.todas(repo)),
        "events": len(evts),
        "toolchain": saude.avaliar(repo),
    })


def cmd_pause(repo: Path, ident: Identidade, args) -> None:
    """O kill-switch é do `chaos`: PAUSED é estado no repositório e precisa
    funcionar com o ORDER ausente (AT-09). O `order` apenas lê."""
    if not ident.eh_humano:
        raise ErroChaos("o kill-switch é do proprietário (§21)", "policy")
    p = repo / "order" / "PAUSED"
    p.write_text(f"reason: {args.reason or 'sem motivo declarado'}\nat: {ids.agora()}\n",
                 encoding="utf-8", newline="\n")
    ledger.append(repo, actor=ident.ator, surface=ident.surface,
                  action="kill_switch.pause", risk_class="A1")
    gitops.git(repo, "add", "-A")
    gitops.git(repo, "commit", "-q", "-m", "PAUSED")
    saida({"paused": True})


def cmd_resume(repo: Path, ident: Identidade, args) -> None:
    if not ident.eh_humano:
        raise ErroChaos("o kill-switch é do proprietário (§21)", "policy")
    p = repo / "order" / "PAUSED"
    if p.exists():
        p.unlink()
    ledger.append(repo, actor=ident.ator, surface=ident.surface,
                  action="kill_switch.resume", risk_class="A1")
    gitops.git(repo, "add", "-A")
    gitops.git(repo, "commit", "-q", "-m", "resume")
    saida({"paused": False})


def cmd_index_rebuild(repo: Path, ident: Identidade, args) -> None:
    n = indice.rebuild(repo)
    saida({"indexed": n})


def cmd_search(repo: Path, args) -> None:
    saida(indice.buscar(repo, args.consulta, as_of=args.as_of))


def cmd_context(repo: Path, ident: Identidade, args) -> None:
    executor = args.executor or ("cloud" if ident.surface.startswith("cloud") else "local")
    ctx = contexto.montar(repo, executor=executor, task=args.task or "",
                          source=args.source or "", agent=args.agent or "",
                          area=getattr(args, "area", "") or "", as_of=args.as_of)
    saida(ctx)


def cmd_commit(repo: Path, ident: Identidade, args) -> None:
    ident.ator          # §17.1: credencial desconhecida ou ator forjado recusa aqui,
                        # antes de qualquer consideração sobre haver ou não mudanças
    sha = commit(repo, ident, args.message or "commit")
    if sha is None:
        saida({"committed": False, "reason": "nada a comitar"})
        return
    ledger.append(repo, actor=ident.ator, surface=ident.surface,
                  action="repo.commit", risk_class="A1", summary=args.message or "")
    # o EVT criado depois do commit entra no próximo; anexa agora para não perder
    gitops.git(repo, "add", "audit/events.jsonl")
    gitops.git(repo, "commit", "-q", "--amend", "--no-edit")
    saida({"committed": True, "sha": gitops.head(repo)})


def cmd_audit(repo: Path, ident: Identidade, args) -> int:
    if args.sub == "append":
        evt = ledger.append(repo, actor=ident.ator, surface=ident.surface,
                            action=args.action or "manual", risk_class=args.risk or "A1",
                            entity_id=args.entity or "")
        saida(evt)
        return 0
    evts = ledger.ler(repo)
    ts = [e.get("ts", "") for e in evts]
    # Append-only garante que nada se perde; NÃO garante ordem física, porque o
    # `merge=union` concatena sem conhecer a semântica das linhas. O que se
    # verifica é a integridade: sem duplicata de `event_id`, `ts` utilizável.
    ids_ = [e.get("event_id") for e in evts]
    duplicados = len(ids_) != len(set(ids_))
    saida({"events": len(evts), "duplicate_ids": duplicados,
           "physically_ordered": ts == sorted(ts),
           "note": "ordem cronológica é recuperada na leitura (§17.1)"})
    return 1 if duplicados else 0


def cmd_episodic(repo: Path, args) -> int:
    if args.sub == "status":
        saida(episodico.status(repo))
        return 0
    saida(episodico.consultar(repo, args.consulta or "", limite=20))
    return 0


def cmd_tooling_update(repo: Path, ident: Identidade, args) -> None:
    rel = "metadata/tooling.yaml"
    if not ident.eh_humano:
        raise ErroChaos(
            f"`{rel}` é protected path (CHAOS §4.1): decide QUAL código executa "
            "tudo o mais. Alterá-lo é A4 e exige commit humano.", "policy")
    yamlio.escrever_yaml(repo / "metadata" / "tooling.yaml",
                         {"vendored_tag": args.tag, "vendored_at": ids.agora()})
    gitops.git(repo, "add", "-A")
    gitops.git(repo, "commit", "-q", "-m", f"tooling update {args.tag}")
    saida({"vendored_tag": args.tag})


def cmd_schema_migrate(repo: Path, ident: Identidade, args) -> int:
    """
    §7.5: migração de `schema_version`.

    Campo desconhecido é PRESERVADO, nunca removido — o contrário transformaria
    "migrar" em "perder o que a versão nova não entende".
    """
    atual = "2.5"
    migradas, ja_na_versao = [], 0
    for path in entidades.todas(repo):
        fm, corpo = yamlio.ler(path)
        versao = str(fm.get("schema_version") or "")
        if versao == atual:
            ja_na_versao += 1
            continue
        for campo, default in (("authority", "active"), ("valid_from", ""),
                               ("valid_to", ""), ("relations", []),
                               ("conflicts", [])):
            fm.setdefault(campo, default if not isinstance(default, list) else list(default))
        fm["schema_version"] = atual
        fm["updated_at"] = ids.agora()
        if not args.dry_run:
            yamlio.escrever(path, fm, corpo)
        migradas.append(fm["id"])

    if migradas and not args.dry_run:
        ledger.append(repo, actor=ident.ator, surface=ident.surface,
                      action="schema.migrate", risk_class="A2",
                      summary=f"{len(migradas)} entidades → {atual}")
        commit(repo, ident, f"migra {len(migradas)} entidades para schema {atual}")
    saida({"target": atual, "migrated": migradas,
           "already_current": ja_na_versao, "dry_run": bool(args.dry_run)})
    return 0


def cmd_onboarding(repo: Path, ident: Identidade, args) -> int:
    """
    Implementação §3. O produto é um relatório que o usuário confirma — e só
    depois dessa confirmação a Fase 0 começa.
    """
    marcador = repo / "reports" / ".onboarding-confirmado"

    if args.sub == "questions":
        saida([{"chave": q.chave, "pergunta": q.texto, "destino": q.destino,
                "default": q.default, "opcoes": q.opcoes, "bloco": q.bloco,
                "obrigatoria": q.default is None}
               for q in onboarding.PERGUNTAS])
        return 0

    if args.sub == "report":
        relatorios = sorted((repo / "reports").glob("onboarding-*.md"))
        saida({"reports": [r.name for r in relatorios],
               "latest": relatorios[-1].name if relatorios else None,
               "confirmed": marcador.exists(),
               "phase_0_unlocked": marcador.exists()})
        return 0 if relatorios else 1

    if not ident.eh_humano:
        raise ErroChaos("o Onboarding é do proprietário: ele define classes de "
                        "privacidade, identidades e cotas (§3)", "policy")

    if args.confirm:
        relatorios = sorted((repo / "reports").glob("onboarding-*.md"))
        if not relatorios:
            raise ErroChaos("não há relatório para confirmar — rode "
                            "`chaos onboarding run` primeiro", "reference")
        marcador.write_text(f"confirmado_em: {ids.agora()}\n"
                            f"relatorio: {relatorios[-1].name}\n",
                            encoding="utf-8", newline="\n")
        commit(repo, ident, "confirma o relatório de onboarding")
        saida({"confirmed": relatorios[-1].name, "phase_0_unlocked": True})
        return 0

    arquivo = Path(args.answers) if args.answers else None
    interativo = sys.stdin.isatty() and not args.nao_interativo and not arquivo
    respostas = onboarding.coletar(arquivo, interativo)
    tocados = onboarding.materializar(repo, respostas, ident.ator)
    destino = onboarding.relatorio(repo, respostas, tocados)

    ledger.append(repo, actor=ident.ator, surface=ident.surface,
                  action="onboarding.run", risk_class="A4",
                  summary=f"{len(respostas)} respostas, {len(set(tocados))} arquivos")
    gitops.git(repo, "add", "-A")
    gitops.git(repo, "commit", "-q", "-m", "onboarding: materializa as respostas")

    saida({"answers": len(respostas), "files": sorted(set(tocados)),
           "report": destino.relative_to(repo).as_posix(),
           "confirmed": False,
           "next": "revise o relatório e rode `chaos onboarding run --confirm`"})
    return 0


def cmd_bootstrap_sync(repo: Path, ident: Identidade, args) -> None:
    if not ident.eh_humano:
        raise ErroChaos("AGENTS.md é protected path (§4.1)", "policy")
    cfg = cfg_repo(repo)
    layout.escrever_agents_md(repo, cfg.get("privacy_class", ""), args.owner or "human:owner")
    gitops.git(repo, "add", "-A")
    gitops.git(repo, "commit", "-q", "-m", "bootstrap sync")
    _configurar_verificacao_local(repo)
    saida({"bootstrap": "AGENTS.md"})


# --------------------------------------------------------------------------- #
# inbox, promoção, vault, migração, sync, conflitos                            #
# --------------------------------------------------------------------------- #

def cmd_inbox_add(repo: Path, ident: Identidade, args) -> None:
    """§14.1: o que entra pelo inbox nasce `external_source` — é dado, nunca instrução."""
    fm = entidades.criar(repo, "inbox", ident.ator, {"text": args.text})
    corpo = fm.pop("_corpo", args.text or "")
    path = repo / "inbox" / f"{fm['id']}.md"
    yamlio.escrever(path, fm, corpo)
    _registrar_e_comitar(repo, ident, action="inbox.add", entity_id=fm["id"],
                         mensagem=f"inbox {fm['id']}")
    saida({"id": fm["id"]})


def cmd_promote(repo: Path, ident: Identidade, args) -> None:
    """
    §4.2: único caminho episódico → canônico, e é escrita comum.

    Não tem privilégio: mesmo caminho, mesmos trailers, mesmo guard, mesmo EVT.
    O que acrescenta é a proveniência e o teto de `epistemic_status`.
    """
    ref = args.ref
    tipo = args.as_type or "source"
    registro = episodico.obter(repo, ref) or {"text": "", "ref": ref}

    if args.into:
        if not ident.eh_humano and eh_protegido(args.into.rstrip("/") + "/x"):
            raise ErroChaos(
                f"`{args.into}` é protected path (CHAOS §4.1): promover para lá é "
                "A4, como escrever lá. A promoção não é atalho de privilégio.",
                "policy")

    fm = entidades.criar(repo, tipo, ident.ator,
                         {"title": (registro.get("text") or ref)[:80]})
    fm["provenance"]["origin"] = "derived"
    fm["provenance"]["source_refs"] = [ref]
    fm["provenance"]["epistemic_status"] = "inference"
    fm["provenance"]["verified_by"] = ""
    corpo = registro.get("text", "")

    destino = Path(args.into) if args.into else entidades.pasta_de(repo, tipo)
    if not destino.is_absolute():
        destino = repo / destino
    path = destino / f"{fm['id']}.md"
    if not ident.eh_humano:
        _recusar_protegidos(repo, ident, [path.relative_to(repo).as_posix()])
    yamlio.escrever(path, fm, corpo)

    _registrar_e_comitar(repo, ident, action="promote", entity_id=fm["id"],
                         mensagem=f"promove {ref} → {fm['id']}")
    saida({"id": fm["id"], "from": ref})


def cmd_vault_import(repo: Path, ident: Identidade, args) -> None:
    """
    §28.1: incremental e sem perda. O relatório lista TODOS os arquivos de
    entrada; o não mapeável vai para `inbox/` como `external_source`; nada na
    origem é apagado ou alterado por inadequação ao schema.
    """
    origem = Path(args.caminho)
    if not origem.is_dir():
        raise ErroChaos(f"`{origem}` não é um diretório", "reference")

    relatorio = []
    for p in sorted(origem.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(origem).as_posix()
        mapeavel = p.suffix.lower() == ".md"
        destino = f"wiki/{rel}" if mapeavel else f"inbox/{p.name}"
        relatorio.append({
            "source": rel,
            "destination": destino,
            "mappable": mapeavel,
            "provenance_origin": "external_source",
        })

    if not args.dry_run:
        for item in relatorio:
            alvo = repo / item["destination"]
            alvo.parent.mkdir(parents=True, exist_ok=True)
            bruto = (origem / item["source"]).read_bytes()
            if item["mappable"]:
                fm = entidades.criar(repo, "document", ident.ator,
                                     {"title": Path(item["source"]).stem})
                fm.pop("_corpo", None)
                fm["provenance"]["origin"] = "external_source"
                alvo = repo / "wiki" / f"{fm['id']}.md"
                yamlio.escrever(alvo, fm, bruto.decode("utf-8", "replace"))
                item["entity_id"] = fm["id"]
            else:
                alvo.write_bytes(bruto)
        ledger.append(repo, actor=ident.ator, surface=ident.surface,
                      action="vault.import", risk_class="A1",
                      summary=f"{len(relatorio)} arquivos")
        commit(repo, ident, f"vault import: {len(relatorio)} arquivos")

    saida({"files": relatorio, "count": len(relatorio), "dry_run": bool(args.dry_run)})


def cmd_repo_migrate(repo: Path, ident: Identidade, args) -> None:
    """
    §28.2: reclassificação é A4 e NÃO é `git mv`. A entidade é COPIADA com o
    mesmo ID; a origem vira read-only e permanece, com todo o histórico. Nenhum
    EVT atravessa a fronteira de classe (§17.5).
    """
    if not ident.eh_humano:
        raise ErroChaos("reclassificação de privacidade é A4 (§28.2)", "policy")

    destino_repo = Path(args.target).resolve()
    if not (destino_repo / "metadata" / "repo.yaml").exists():
        raise ErroChaos(f"`{destino_repo}` não é um repositório CHAOS", "reference")

    path, fm, corpo = entidades.carregar(repo, args.entity)
    origem_id = cfg_repo(repo).get("repo_id", "chaos-origem")
    destino_id = cfg_repo(destino_repo).get("repo_id", "chaos-destino")

    copia = dict(fm)
    copia["migrated_from"] = f"{origem_id}:{fm['id']}"
    copia.pop("migrated_to", None)
    copia["updated_at"] = ids.agora()
    alvo = destino_repo / ids.PASTAS[fm["type"]] / f"{fm['id']}.md"
    yamlio.escrever(alvo, copia, corpo)

    fm["migrated_to"] = f"{destino_id}:{fm['id']}"
    fm["updated_at"] = ids.agora()
    yamlio.escrever(path, fm, corpo)

    # EVT de cada lado, sem cruzar a fronteira (§17.5)
    ledger.append(repo, actor=ident.ator, surface=ident.surface,
                  action="repo.migrate.out", entity_id=fm["id"], risk_class="A4")
    ledger.append(destino_repo, actor=ident.ator, surface=ident.surface,
                  action="repo.migrate.in", entity_id=fm["id"], risk_class="A4")
    commit(repo, ident, f"migra {fm['id']} para {destino_id}")
    gitops.git(destino_repo, "add", "-A")
    gitops.git(destino_repo, "commit", "-q", "-m", f"recebe {fm['id']} de {origem_id}")
    saida({"id": fm["id"], "from": origem_id, "to": destino_id})


def cmd_sync(repo: Path, ident: Identidade, args) -> int:
    """
    §17.3: único caminho de sincronização de agentes. Implementa a tabela de
    precedência e NUNCA deixa marcador de conflito.
    """
    gitops.git(repo, "add", "-A")
    if gitops.arquivos_modificados(repo):
        commit(repo, ident, "sync: estado local")

    fetch = gitops.git(repo, "fetch", "origin")
    if fetch.returncode != 0:
        saida({"synced": False, "reason": "sem remoto alcançável"})
        return 0

    merge = gitops.git(repo, "merge", "--no-edit", "origin/HEAD")
    if merge.returncode == 0:
        saida({"synced": True, "conflicts": []})
        return 0

    conflitados = [l[3:] for l in gitops.git(repo, "status", "--porcelain").stdout.splitlines()
                   if l.startswith(("UU", "AA"))]
    resolvidos, bloqueados = [], []
    for rel in conflitados:
        p = repo / rel
        if _resolver(repo, p, ident):
            resolvidos.append(rel)
        else:
            bloqueados.append(rel)

    gitops.git(repo, "add", "-A")
    gitops.git(repo, "commit", "-q", "--no-edit")
    saida({"synced": True, "resolved": resolvidos, "blocked": bloqueados})
    return 0


def _resolver(repo: Path, path: Path, ident: Identidade) -> bool:
    """
    Precedência de §17.3. Ordem 2 (checkpoint de RUN) NÃO converge sozinha: é
    marcada e espera decisão humana. Ordem 5 (entidades comuns) converge com o
    lado perdedor registrado em `conflicts` — nada é descartado em silêncio.
    """
    texto = path.read_text(encoding="utf-8", errors="replace")
    nosso, deles = _lados(texto)
    if nosso is None:
        return False

    try:
        fm_n = yamlio.ler_texto(nosso)
        fm_d = yamlio.ler_texto(deles)
    except Exception:
        return False

    if fm_n.get("type") == "run":
        # ordem 2: checkpoint é exceção explícita ao last-write-wins
        fm_n["has_conflict"] = True
        fm_n.setdefault("conflicts", []).append(
            {"field": "checkpoint", "theirs": fm_d.get("checkpoint"),
             "ours": fm_n.get("checkpoint"), "detected_at": ids.agora()})
        yamlio.escrever(path, fm_n, "")
        tarefa = fm_n.get("task")
        if tarefa:
            tp = entidades.achar(repo, tarefa)
            if tp:
                tfm, tcorpo = yamlio.ler(tp)
                tfm["status"] = "blocked"
                tfm["blocked_reason"] = "checkpoint_conflict"
                tfm["has_conflict"] = True
                yamlio.escrever(tp, tfm, tcorpo)
        return True

    # ordem 5: converge, e o lado perdedor vira registro, não descarte
    vencedor = fm_n if str(fm_n.get("updated_at", "")) >= str(fm_d.get("updated_at", "")) \
        else fm_d
    perdedor = fm_d if vencedor is fm_n else fm_n
    vencedor.setdefault("conflicts", []).append({
        "field": "entity", "losing_side": {k: perdedor.get(k)
                                           for k in ("updated_at", "updated_by", "priority")},
        "detected_at": ids.agora()})
    yamlio.escrever(path, vencedor, "")
    return True


def _lados(texto: str):
    nosso, deles, modo = [], [], None
    for linha in texto.splitlines():
        if linha.startswith("<<<<<<<"):
            modo = "n"
        elif linha.startswith("======="):
            modo = "d"
        elif linha.startswith(">>>>>>>"):
            modo = None
        elif modo == "n":
            nosso.append(linha)
        elif modo == "d":
            deles.append(linha)
        else:
            nosso.append(linha)
            deles.append(linha)
    if modo is None and not nosso:
        return None, None
    return "\n".join(nosso), "\n".join(deles)


def cmd_conflict(repo: Path, ident: Identidade, args) -> None:
    if args.sub == "list":
        saida([{"id": yamlio.ler(p)[0].get("id"),
                "conflicts": yamlio.ler(p)[0].get("conflicts")}
               for p in entidades.todas(repo) if yamlio.ler(p)[0].get("conflicts")])
        return
    path, fm, corpo = entidades.carregar(repo, args.id)
    fm["conflicts"] = []
    fm["has_conflict"] = False
    yamlio.escrever(path, fm, corpo)
    _registrar_e_comitar(repo, ident, action="conflict.resolve", entity_id=args.id,
                         mensagem=f"resolve conflito de {args.id}")
    saida({"id": args.id, "resolved": True})


def cmd_run(repo: Path, ident: Identidade, args) -> None:
    """`run merge|reset|repair` — §17.3 ordem 2; reset e repair são A4."""
    path, fm, corpo = entidades.carregar(repo, args.id)
    if args.sub in ("reset", "repair") and not ident.eh_humano:
        raise ErroChaos(f"`run {args.sub}` é A4: reescrever o ponteiro de progresso "
                        "é indistinguível de apagar trabalho feito", "policy")
    if args.sub == "merge":
        escolha = args.keep or "local"
        lado = None
        for c in fm.get("conflicts", []):
            if c.get("field") == "checkpoint":
                lado = c.get("theirs") if escolha == "remote" else c.get("ours")
        if lado:
            fm["checkpoint"] = lado
        fm["has_conflict"] = False
        fm["conflicts"] = []
    elif args.sub == "reset":
        fm["checkpoint"] = {}
        fm["status"] = "reset"
    elif args.sub == "repair":
        fm["has_conflict"] = False
    yamlio.escrever(path, fm, corpo)

    tarefa = fm.get("task")
    if tarefa:
        tp = entidades.achar(repo, tarefa)
        if tp:
            tfm, tcorpo = yamlio.ler(tp)
            if tfm.get("blocked_reason") == "checkpoint_conflict":
                tfm["status"] = "todo"
                tfm["blocked_reason"] = ""
                tfm["has_conflict"] = False
                yamlio.escrever(tp, tfm, tcorpo)

    _registrar_e_comitar(repo, ident, action=f"run.{args.sub}", entity_id=args.id,
                         risk="A4" if args.sub in ("reset", "repair") else "A2",
                         mensagem=f"run {args.sub} {args.id}")
    saida({"id": args.id, "action": args.sub, "checkpoint": fm.get("checkpoint")})


# --------------------------------------------------------------------------- #
# argparse                                                                      #
# --------------------------------------------------------------------------- #

def _add_campos(p: argparse.ArgumentParser) -> None:
    p.add_argument("--title")
    p.add_argument("--privacy", choices=["cloud_allowed", "local_only"])
    p.add_argument("--execution", choices=["local", "cloud", "any"])
    p.add_argument("--priority")
    p.add_argument("--project")
    p.add_argument("--area")
    p.add_argument("--parent-task", dest="parent_task")
    p.add_argument("--risk-hint", dest="risk_hint")
    p.add_argument("--model-policy", dest="model_policy")
    p.add_argument("--authority")
    p.add_argument("--valid-from", dest="valid_from")
    p.add_argument("--supersedes")
    p.add_argument("--field", action="append")
    p.add_argument("--due-date", dest="due_date")
    p.add_argument("--evidence")
    p.add_argument("--source-refs", dest="source_refs", action="append")
    p.add_argument("--name")
    p.add_argument("--trigger")
    p.add_argument("--max-risk", dest="max_risk")
    p.add_argument("--maturity")
    p.add_argument("--enabled")
    p.add_argument("--risk")
    p.add_argument("--action", dest="action")
    p.add_argument("--text")


def _propagar_format(parser: argparse.ArgumentParser) -> None:
    """
    `--format` vale em qualquer posição, em qualquer profundidade.

    Uma CLI que aceite a flag só antes do subcomando é armadilha: o usuário a
    escreve no fim, como em toda ferramenta de linha de comando, e recebe um
    erro de uso que não explica nada.
    """
    try:
        parser.add_argument("--format", dest="formato", choices=["json", "text"])
    except argparse.ArgumentError:
        pass
    for acao in parser._actions:
        if isinstance(acao, argparse._SubParsersAction):
            for sub in acao.choices.values():
                _propagar_format(sub)


def construir_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="chaos", description="CHAOS — CLI de §21")
    ap.add_argument("--format", dest="formato", default="json",
                    choices=["json", "text"])
    sub = ap.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("init"); p.add_argument("--privacy-class", dest="privacy_class",
                                               required=True)
    p.add_argument("--owner", default="human:owner")

    sub.add_parser("validate")
    sub.add_parser("status")
    sub.add_parser("health")

    p = sub.add_parser("key"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("new"); q.add_argument("papel")
    q.add_argument("--principal", required=True)
    q.add_argument("--arquivo"); q.add_argument("--sem-frase", dest="sem_frase",
                                                action="store_true")
    q = s.add_parser("register"); q.add_argument("papel"); q.add_argument("arquivo")
    q.add_argument("--principal", required=True)
    q = s.add_parser("verify"); q.add_argument("ref", nargs="?")
    s.add_parser("list")

    p = sub.add_parser("id"); s = p.add_subparsers(dest="sub", required=True)
    n = s.add_parser("new"); n.add_argument("tipo", choices=TIPOS)

    for tipo in TIPOS:
        p = sub.add_parser(tipo)
        s = p.add_subparsers(dest="sub", required=True)
        c = s.add_parser("create"); _add_campos(c)
        u = s.add_parser("update"); u.add_argument("id"); _add_campos(u)
        sh = s.add_parser("show"); sh.add_argument("id")
        s.add_parser("list")
        if tipo == "task":
            cl = s.add_parser("claim"); cl.add_argument("id")
            rl = s.add_parser("release"); rl.add_argument("id")
        if tipo == "inbox":
            # §21: `inbox add` é ingestão externa — mesmo parser do tipo.
            q = s.add_parser("add"); q.add_argument("--text", required=True)
        if tipo == "run":
            # §21: `run` é tipo de entidade E tem operações próprias de §17.3.
            # O mesmo parser serve aos dois, senão argparse recusa o nome.
            for nome in ("merge", "reset", "repair"):
                q = s.add_parser(nome); q.add_argument("id"); q.add_argument("--keep")

    p = sub.add_parser("conflict"); s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("list")
    q = s.add_parser("resolve"); q.add_argument("id"); q.add_argument("--keep")

    p = sub.add_parser("area"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("create"); q.add_argument("slug"); q.add_argument("--title")
    q.add_argument("--owner-agent", dest="owner_agent")
    q = s.add_parser("sync"); q.add_argument("slug", nargs="?")
    q = s.add_parser("show"); q.add_argument("slug")
    s.add_parser("list")

    p = sub.add_parser("context")
    for flag in ("--agent", "--task", "--source", "--executor", "--surface"):
        p.add_argument(flag)
    p.add_argument("--as-of", dest="as_of")
    p.add_argument("--area")

    p = sub.add_parser("search"); p.add_argument("consulta")
    p.add_argument("--as-of", dest="as_of")

    p = sub.add_parser("index"); s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("rebuild")
    p = sub.add_parser("graph"); s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("build")
    q = s.add_parser("neighbors"); q.add_argument("no"); q.add_argument("--predicate")
    q = s.add_parser("path"); q.add_argument("origem"); q.add_argument("destino")
    q = s.add_parser("subtree"); q.add_argument("raiz")
    q.add_argument("--depth", type=int, default=3)

    p = sub.add_parser("commit"); p.add_argument("-m", "--message", dest="message")
    sub.add_parser("sync")

    p = sub.add_parser("audit"); s = p.add_subparsers(dest="sub", required=True)
    a = s.add_parser("append")
    a.add_argument("--action"); a.add_argument("--risk"); a.add_argument("--entity")
    s.add_parser("verify")

    p = sub.add_parser("bootstrap"); s = p.add_subparsers(dest="sub", required=True)
    b = s.add_parser("sync"); b.add_argument("--owner")
    p = sub.add_parser("tooling"); s = p.add_subparsers(dest="sub", required=True)
    t = s.add_parser("update"); t.add_argument("tag")

    p = sub.add_parser("schema"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("migrate"); q.add_argument("--dry-run", dest="dry_run",
                                                action="store_true")

    p = sub.add_parser("repo"); s = p.add_subparsers(dest="sub", required=True)
    m = s.add_parser("migrate")
    m.add_argument("origem"); m.add_argument("destino")
    m.add_argument("--entity", required=True); m.add_argument("--target", required=True)

    p = sub.add_parser("vault"); s = p.add_subparsers(dest="sub", required=True)
    v = s.add_parser("import"); v.add_argument("caminho")
    v.add_argument("--dry-run", dest="dry_run", action="store_true")

    p = sub.add_parser("promote")
    p.add_argument("ref"); p.add_argument("--as", dest="as_type")
    p.add_argument("--into"); p.add_argument("--dry-run", dest="dry_run",
                                             action="store_true")

    p = sub.add_parser("episodic"); s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("status")
    q = s.add_parser("search"); q.add_argument("consulta")

    p = sub.add_parser("onboarding"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("run")
    q.add_argument("--answers", help="arquivo YAML com respostas (modo não interativo)")
    q.add_argument("--non-interactive", dest="nao_interativo", action="store_true")
    q.add_argument("--confirm", action="store_true",
                   help="confirma o relatório e libera a Fase 0")
    s.add_parser("report")
    s.add_parser("questions")

    p = sub.add_parser("pause"); p.add_argument("--reason")
    sub.add_parser("resume")
    sub.add_parser("backup")
    p = sub.add_parser("restore"); p.add_argument("caminho", nargs="?")

    for acao in ap._actions:
        if isinstance(acao, argparse._SubParsersAction):
            for s2 in acao.choices.values():
                _propagar_format(s2)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = construir_parser()
    args = ap.parse_args(argv)
    if getattr(args, "formato", None) is None:
        args.formato = "json"

    if args.comando == "init":
        cmd_init(args)
        return 0

    repo = achar_repo()
    ident = Identidade(repo)

    if args.comando in TIPOS:
        if args.comando == "run" and args.sub in ("merge", "reset", "repair"):
            cmd_run(repo, ident, args)
            return 0
        if args.comando == "inbox" and args.sub == "add":
            cmd_inbox_add(repo, ident, args)
            return 0
        if args.sub == "create":
            cmd_create(repo, ident, args.comando, args)
        elif args.sub == "update":
            cmd_update(repo, ident, args.comando, args)
        elif args.sub == "show":
            cmd_show(repo, ident, args.comando, args)
        elif args.sub == "list":
            cmd_list(repo, ident, args.comando, args)
        elif args.sub in ("claim", "release"):
            raise ErroChaos("claim e release de tarefa são do `order` (§38): "
                            "`order task claim <id>`", "policy")
        return 0

    despacho = {
        "validate": lambda: cmd_validate(repo, ident, args),
        "health": lambda: cmd_health(repo, args),
        "key": lambda: cmd_key(repo, ident, args),
        "status": lambda: cmd_status(repo, args),
        "pause": lambda: cmd_pause(repo, ident, args),
        "resume": lambda: cmd_resume(repo, ident, args),
        "search": lambda: cmd_search(repo, args),
        "context": lambda: cmd_context(repo, ident, args),
        "commit": lambda: cmd_commit(repo, ident, args),
        "sync": lambda: cmd_sync(repo, ident, args),
        "audit": lambda: cmd_audit(repo, ident, args),
        "episodic": lambda: cmd_episodic(repo, args),
        "promote": lambda: cmd_promote(repo, ident, args),
        "conflict": lambda: cmd_conflict(repo, ident, args),
        "area": lambda: cmd_area(repo, ident, args),
    }
    if args.comando in despacho:
        r = despacho[args.comando]()
        return r if isinstance(r, int) else 0

    if args.comando == "id":
        saida({"id": ids.novo_id(args.tipo)}); return 0
    if args.comando == "index":
        cmd_index_rebuild(repo, ident, args); return 0
    if args.comando == "graph":
        if args.sub == "build":
            indice.rebuild(repo); saida({"graph": "graph/graph.json"})
        elif args.sub == "neighbors":
            saida(grafo.vizinhos(repo, args.no, args.predicate or ""))
        elif args.sub == "path":
            saida({"path": grafo.caminho(repo, args.origem, args.destino)})
        else:
            saida(grafo.subarvore(repo, args.raiz, args.depth))
        return 0
    if args.comando == "vault":
        cmd_vault_import(repo, ident, args); return 0
    if args.comando == "repo":
        cmd_repo_migrate(repo, ident, args); return 0
    if args.comando == "tooling":
        cmd_tooling_update(repo, ident, args); return 0
    if args.comando == "bootstrap":
        cmd_bootstrap_sync(repo, ident, args); return 0
    if args.comando == "schema":
        return cmd_schema_migrate(repo, ident, args)
    if args.comando == "onboarding":
        return cmd_onboarding(repo, ident, args)
    if args.comando == "backup":
        alvo = repo.parent / f"{repo.name}-backup.bundle"
        gitops.git(repo, "bundle", "create", str(alvo), "--all")
        saida({"backup": str(alvo)}); return 0
    if args.comando == "restore":
        origem = Path(args.caminho) if args.caminho else None
        if not origem or not origem.exists():
            raise ErroChaos("informe o bundle: `chaos restore <arquivo.bundle>` "
                            "(gerado por `chaos backup`)", "reference")
        p = gitops.git(repo, "bundle", "verify", str(origem))
        if p.returncode != 0:
            raise ErroChaos(f"bundle inválido: {p.stderr.strip()[:200]}", "integrity")
        saida({"bundle": str(origem), "verified": True,
               "restore": f"git clone {origem} <destino> — restaurar POR CIMA de um "
                          "repositório vivo destruiria histórico, então o comando "
                          "verifica e instrui, nunca sobrescreve"})
        return 0

    ap.error(f"comando não implementado: {args.comando}")
    return 2


def executar() -> int:
    try:
        return main()
    except ErroChaos as exc:
        print(f"[{exc.categoria}] {exc}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0
