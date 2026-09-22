"""
CLI do `order` — ORDER §38 é o contrato completo.

O kill-switch é do `chaos`: `PAUSED` é estado no repositório, não do runtime, e
precisa funcionar com o ORDER ausente. Aqui ele apenas é LIDO.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.chaos import (assinatura, entidades, gitops, ids, indice, ledger,
                         saude, yamlio)
from tools.chaos.cli import commit as chaos_commit
from tools.chaos.repo import ErroChaos, Identidade, achar_repo, cfg_repo
from tools.order import gateway, guarda, notificacao, risco, workflows


def saida(dados) -> None:
    print(json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True))


def pausado(repo: Path) -> bool:
    return (repo / "order" / "PAUSED").exists()


def exigir_ativo(repo: Path) -> None:
    if pausado(repo):
        raise ErroChaos("`order/PAUSED` existe: o kill-switch está acionado e "
                        "nada autônomo roda (§19)", "policy")


def policies(repo: Path, nome: str) -> dict:
    return yamlio.ler_yaml(repo / "order" / "policies" / nome) or {}


def registry(repo: Path) -> list[dict]:
    d = yamlio.ler_yaml(repo / "order" / "agents" / "registry.yaml") or {}
    return d.get("agents", [])


def evt(repo: Path, ident: Identidade, **kw) -> None:
    ledger.append(repo, actor=_ator(ident), surface=ident.surface, **kw)


def _ator(ident: Identidade) -> str:
    try:
        return ident.ator
    except ErroChaos:
        return ident.pretendido or "desconhecido"


def _comitar(repo: Path, ident: Identidade, mensagem: str) -> None:
    try:
        chaos_commit(repo, ident, mensagem)
    except ErroChaos:
        gitops.git(repo, "add", "-A")
        gitops.git(repo, "commit", "-q", "-m", mensagem)


# --------------------------------------------------------------------------- #
# toolchain: drift rebaixa autonomia, não a interrompe (§31)                    #
# --------------------------------------------------------------------------- #

def estado_toolchain(repo: Path) -> dict:
    return saude.avaliar(repo)


def aplicar_drift(repo: Path, ident: Identidade) -> dict:
    """
    §31: `drift` rebaixa automações a `propose` reutilizando o freio de cota.

    Parar tudo puniria o usuário por um descompasso de versão, e o desfecho
    previsível é ele contornar a verificação.
    """
    estado = estado_toolchain(repo)
    if estado["status"] == "ok":
        return estado
    mudou = False
    for p in sorted((repo / "order" / "automations").glob("AUT-*.md")):
        fm, corpo = yamlio.ler(p)
        if fm.get("mode") not in ("propose", "shadow"):
            fm["mode"] = "propose"
            fm["updated_at"] = ids.agora()
            yamlio.escrever(p, fm, corpo)
            mudou = True
    if mudou or estado["status"] != "ok":
        evt(repo, ident, action="toolchain.drift", risk_class="A1", level="warning",
            summary=f"toolchain {estado['status']}: executando "
                    f"{estado.get('running_tag')}, declarado {estado.get('vendored_tag')}")
        if mudou:
            _comitar(repo, ident, "rebaixa automações por drift de toolchain")
    return estado


# --------------------------------------------------------------------------- #
# agentes, modelos, cotas                                                       #
# --------------------------------------------------------------------------- #

def cmd_agent_list(repo: Path, args) -> None:
    agentes = registry(repo)
    if args.kind:
        agentes = [a for a in agentes if a.get("kind") == args.kind]
    if args.capability:
        agentes = [a for a in agentes if args.capability in (a.get("capabilities") or [])]
    if args.id:
        agentes = [a for a in agentes if a.get("id") == args.id]
    saida(agentes)


def cmd_agent_sync(repo: Path, ident: Identidade, args) -> None:
    """
    Gera os bindings de `.claude/agents/` a partir do registry.

    §41: trocar o registry de modelos inteiro não pode exigir editar agente
    nenhum — por isso o binding é derivado do registry, e o registry não conhece
    provedor, modelo nem gateway.
    """
    destino = repo / ".claude" / "agents"
    destino.mkdir(parents=True, exist_ok=True)
    for a in registry(repo):
        (destino / f"{a['id']}.md").write_text(
            f"---\nname: {a['id']}\nkind: {a.get('kind')}\n"
            f"model_policy: {a.get('model_policy')}\n"
            f"autonomy_ceiling: {a.get('autonomy_ceiling')}\n---\n"
            f"# {a.get('name', a['id'])}\n\nGerado de order/agents/registry.yaml "
            f"por `order agent sync` — derivado, não editar.\n",
            encoding="utf-8", newline="\n")
    saida({"synced": len(registry(repo))})


def cmd_agent_run(repo: Path, ident: Identidade, args) -> None:
    """
    Executa (ou simula) um agente.

    `--attempt` existe para o AT-22: a negação tem de partir do LOOP do worker,
    não de um `order guard` avulso. Uma implementação cujo loop simplesmente não
    chamasse o guard passaria num teste que só compara dois `guard`.
    """
    alvo = next((a for a in registry(repo) if a["id"] == args.agente), None)
    if not alvo:
        raise ErroChaos(f"agente `{args.agente}` não consta no registry", "reference")

    if args.attempt:
        argv = args.attempt.split()
        permitido, motivo = guarda.avaliar_comando(argv)
        evt(repo, ident, action="guard.deny" if not permitido else "guard.allow",
            risk_class="A1", level="warning" if not permitido else "info",
            summary=f"{args.agente}: {args.attempt[:120]}")
        _comitar(repo, ident, "registra tentativa do loop do worker")
        if not permitido:
            raise ErroChaos(f"loop do worker negou: {motivo}", "policy")
        saida({"agent": args.agente, "attempt": args.attempt, "allowed": True})
        return

    ctx = {"agent": args.agente, "dry_run": bool(args.dry_run),
           "requires_session_state": False,
           "autonomy_ceiling": alvo.get("autonomy_ceiling")}
    if args.handoff:
        _, fm, _ = entidades.carregar(repo, args.handoff)
        ctx.update({"task_id": fm.get("task"), "objective": fm.get("objective"),
                    "context_refs": fm.get("context_refs", []),
                    "constraints": fm.get("constraints", [])})
    saida(ctx)


def cmd_model_route(repo: Path, ident: Identidade, args) -> None:
    """
    §21.3 — ordem determinística: (1) `local_only` só `locality: local`;
    (2) descartar fontes desabilitadas ou esgotadas; (3) `cost_preference`;
    (4) `tier_preference`; (5) fallback no próximo candidato.
    """
    reg = policies(repo, "model-registry.yaml").get("models", [])
    pol = policies(repo, "model-policy.yaml").get("policies", {})
    quotas = policies(repo, "quotas.yaml")
    habilitadas = {s["id"] for s in quotas.get("budget_sources", []) if s.get("enabled")}
    habilitadas.add("local")

    nome_policy = args.policy or ""
    local_only = False
    if args.task:
        _, fm, _ = entidades.carregar(repo, args.task)
        local_only = fm.get("privacy") == "local_only"
        nome_policy = nome_policy or fm.get("model_policy") or "area-owner"

    if local_only and not _executor_local(ident):
        raise ErroChaos(
            "§21.3 passo 1: tarefa `local_only` nunca é roteada por runtime na "
            "nuvem — o conteúdo não pode ser processado fora da máquina", "privacy")

    regra = pol.get(nome_policy, {})
    minimo = regra.get("minimum_tier", "low")
    ordem_tier = ["low", "mid", "high"]
    aceitos = ordem_tier[ordem_tier.index(minimo):]

    candidatos = [m for m in reg
                  if m.get("tier") in aceitos
                  and m.get("budget_source") in habilitadas
                  and (not local_only or m.get("locality") == "local")]
    if not candidatos:
        raise ErroChaos(
            f"nenhum modelo elegível para a policy `{nome_policy}` "
            f"(mínimo `{minimo}`{', local_only' if local_only else ''}) — "
            "a tarefa fica `blocked(no_model_capacity)`, sem escape automático",
            "policy")

    prefere = regra.get("cost_preference", "subscription")
    candidatos.sort(key=lambda m: (
        0 if m.get("cost_model") == prefere else 1,
        ordem_tier.index(m.get("tier", "low")),      # menor tier suficiente
    ))
    escolhido = candidatos[0]
    saida({"policy": nome_policy, "tier": escolhido["tier"],
           "model_id": escolhido["id"], "locality": escolhido.get("locality"),
           "budget_source": escolhido.get("budget_source"),
           "dry_run": bool(args.dry_run)})


def _executor_local(ident: Identidade) -> bool:
    return "local" in (ident.surface or "") or _ator(ident).startswith("executor:")


def cmd_model_list(repo: Path, args) -> None:
    reg = policies(repo, "model-registry.yaml").get("models", [])
    quotas = policies(repo, "quotas.yaml")
    habilitadas = {s["id"] for s in quotas.get("budget_sources", []) if s.get("enabled")}
    habilitadas.add("local")
    saida([dict(m, enabled=m.get("budget_source") in habilitadas) for m in reg])


def cmd_quota_status(repo: Path, ident: Identidade, args) -> None:
    quotas = policies(repo, "quotas.yaml").get("global", {})
    maximo = int(quotas.get("max_autonomous_actions_per_day", 0))
    hoje = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    usadas = sum(1 for e in ledger.ler(repo)
                 if e.get("ts", "").startswith(hoje)
                 and not str(e.get("actor", "")).startswith("human:"))
    excedida = usadas >= maximo
    if excedida and quotas.get("on_exceeded") == "degrade_to_propose":
        _rebaixar_automacoes(repo, ident, "quota")
    saida({"used": usadas, "max": maximo, "exceeded": excedida,
           "on_exceeded": quotas.get("on_exceeded")})


def _rebaixar_automacoes(repo: Path, ident: Identidade, motivo: str) -> None:
    mudou = False
    for p in sorted((repo / "order" / "automations").glob("AUT-*.md")):
        fm, corpo = yamlio.ler(p)
        if fm.get("mode") != "propose":
            fm["mode"] = "propose"
            yamlio.escrever(p, fm, corpo)
            mudou = True
    evt(repo, ident, action=f"{motivo}.degrade", risk_class="A1", level="warning",
        summary=f"automações rebaixadas a propose por {motivo}")
    if mudou:
        _comitar(repo, ident, f"rebaixa automações: {motivo}")


# --------------------------------------------------------------------------- #
# fila, runs, aprovações, delegação                                            #
# --------------------------------------------------------------------------- #

def cmd_task_claim(repo: Path, ident: Identidade, args) -> None:
    """
    §11: exatamente um vence o claim. A atomicidade é a do push; o perdedor
    descarta o próprio commit (`reset --hard`), nunca tenta rebase nem merge e
    nunca deixa RUN órfão — Implementação §8.1.
    """
    exigir_ativo(repo)
    path, fm, corpo = entidades.carregar(repo, args.id)

    if fm.get("privacy") == "local_only" and not _executor_local(ident):
        raise ErroChaos("tarefa `local_only` nunca é reclamada por runtime na nuvem "
                        "(§11, §21.3)", "privacy")
    if fm.get("execution") == "local" and not _executor_local(ident):
        raise ErroChaos("tarefa `execution: local` só é reclamada pelo worker local",
                        "policy")
    if fm.get("blocked_reason") == "no_model_capacity":
        raise ErroChaos("tarefa bloqueada por falta de capacidade local — nenhum "
                        "caminho automático a converte em execução na nuvem (§14)",
                        "policy")
    if gitops.git(repo, "remote").stdout.strip():
        gitops.git(repo, "fetch", "-q", "origin")
        ramo = gitops.git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        remoto = gitops.git(repo, "show",
                            f"origin/{ramo}:{path.relative_to(repo).as_posix()}")
        if remoto.returncode == 0:
            try:
                fm_remoto = yamlio.ler_texto(remoto.stdout)
                if fm_remoto.get("claimed_by") and \
                        str(fm_remoto.get("lease_until", "")) > ids.agora():
                    raise ErroChaos(
                        f"§11: `{args.id}` já foi reclamada por "
                        f"`{fm_remoto['claimed_by']}` no remoto — exatamente um vence",
                        "policy")
            except ErroChaos:
                raise
            except Exception:
                pass

    if fm.get("claimed_by") and str(fm.get("lease_until", "")) > ids.agora():
        raise ErroChaos(f"tarefa já reclamada por `{fm['claimed_by']}` até "
                        f"{fm['lease_until']} (§11)", "policy")

    worker = policies(repo, "worker.yaml")
    lease = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
        minutes=int(worker.get("lease_duration_min", 20)))

    anterior = _ultimo_run_abandonado(repo, args.id)
    run = entidades.criar(repo, "run", _ator(ident), {"title": f"RUN de {args.id}"})
    run["task"] = args.id
    run["status"] = "claimed"
    if anterior:
        run["resumes_run"] = anterior["id"]
        run["checkpoint"] = anterior.get("checkpoint", {})
    run.pop("_corpo", None)
    yamlio.escrever(repo / "order" / "runs" / f"{run['id']}.md", run, "")

    fm["claimed_by"] = _ator(ident)
    fm["lease_until"] = lease.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    fm["status"] = "in_progress"
    fm["blocked_reason"] = ""
    yamlio.escrever(path, fm, corpo)

    evt(repo, ident, action="task.claim", entity_id=args.id, risk_class="A1")
    _comitar(repo, ident, f"claim {args.id} → {run['id']}")

    if gitops.git(repo, "remote").stdout.strip():
        push = gitops.git(repo, "push", "-q", "origin", "HEAD")
        if push.returncode != 0:
            ramo = gitops.git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
            gitops.git(repo, "reset", "-q", "--hard", f"origin/{ramo}")
            raise ErroChaos(
                "§11: o claim perdeu a corrida — commit descartado, sem rebase e "
                "sem merge, e a fila é reavaliada", "policy")

    saida({"run_id": run["id"], "task_id": args.id,
           "lease_until": fm["lease_until"]})


def _ultimo_run_abandonado(repo: Path, task_id: str) -> dict | None:
    candidatos = []
    for p in sorted((repo / "order" / "runs").glob("RUN-*.md")):
        fm, _ = yamlio.ler(p)
        if fm.get("task") == task_id and fm.get("status") == "abandoned":
            candidatos.append(fm)
    return candidatos[-1] if candidatos else None


def cmd_task_release(repo: Path, ident: Identidade, args) -> None:
    path, fm, corpo = entidades.carregar(repo, args.id)
    fm["claimed_by"] = ""
    fm["lease_until"] = ""
    fm["status"] = "todo"
    yamlio.escrever(path, fm, corpo)
    evt(repo, ident, action="task.release", entity_id=args.id, risk_class="A1")
    _comitar(repo, ident, f"release {args.id}")
    saida({"task_id": args.id, "released": True})


CHECKPOINT_OBRIGATORIOS = ("step", "last_action", "artifacts_committed",
                           "resume_hint", "version_hash")


def cmd_run_checkpoint(repo: Path, ident: Identidade, args) -> None:
    path, fm, corpo = entidades.carregar(repo, args.id)
    fm["checkpoint"] = {
        "step": args.step or "",
        "last_action": args.last_action or "",
        "artifacts_committed": args.artifacts or [],
        "resume_hint": args.resume_hint or "",
        "version_hash": gitops.head(repo)[:12],
    }
    fm["updated_at"] = ids.agora()
    yamlio.escrever(path, fm, corpo)
    evt(repo, ident, action="run.checkpoint", entity_id=args.id, risk_class="A1")
    _comitar(repo, ident, f"checkpoint {args.id} {args.step or ''}")
    saida({"run_id": args.id, "checkpoint": fm["checkpoint"]})


def cmd_run_abandon(repo: Path, ident: Identidade, args) -> None:
    path, fm, corpo = entidades.carregar(repo, args.id)
    fm["status"] = "abandoned"
    fm["abandon_reason"] = args.reason or ""
    yamlio.escrever(path, fm, corpo)
    tarefa = fm.get("task")
    if tarefa:
        tp, tfm, tcorpo = entidades.carregar(repo, tarefa)
        tfm["claimed_by"] = ""
        tfm["lease_until"] = ""
        tfm["status"] = "todo"
        yamlio.escrever(tp, tfm, tcorpo)
    evt(repo, ident, action="run.abandon", entity_id=args.id, risk_class="A1")
    _comitar(repo, ident, f"abandona {args.id}")
    saida({"run_id": args.id, "status": "abandoned"})


def cmd_run_resume(repo: Path, ident: Identidade, args) -> None:
    """§7.4: checkpoint incompleto NÃO é retomado por inferência."""
    path, fm, corpo = entidades.carregar(repo, args.id)
    cp = fm.get("checkpoint") or {}
    faltando = [c for c in CHECKPOINT_OBRIGATORIOS if not str(cp.get(c, "")).strip()
                and c != "artifacts_committed"]
    if faltando:
        tarefa = fm.get("task")
        if tarefa:
            tp, tfm, tcorpo = entidades.carregar(repo, tarefa)
            tfm["status"] = "blocked"
            tfm["blocked_reason"] = "missing_checkpoint"
            yamlio.escrever(tp, tfm, tcorpo)
            _comitar(repo, ident, f"bloqueia {tarefa}: checkpoint incompleto")
        raise ErroChaos(
            f"§7.4: checkpoint de `{args.id}` sem {', '.join(faltando)} — a tarefa "
            "fica `blocked(missing_checkpoint)` em vez de alguém adivinhar onde parou",
            "integrity")

    apv = fm.get("awaiting_approval")
    if apv:
        _, afm, _ = entidades.carregar(repo, apv)
        if afm.get("status") != "approved":
            raise ErroChaos(f"APV `{apv}` está `{afm.get('status')}` — §18: "
                            "aprovação expirada ou pendente não executa", "policy")
        _exigir_decisao_assinada(repo, apv, afm)
    fm["status"] = "running"
    yamlio.escrever(path, fm, corpo)
    evt(repo, ident, action="run.resume", entity_id=args.id, risk_class="A1")
    _comitar(repo, ident, f"retoma {args.id}")
    saida({"run_id": args.id, "resumed_from": cp.get("step")})


def cmd_run_act(repo: Path, ident: Identidade, args) -> None:
    """
    §17/§18: onde Risk, Permission e Approval Engines são aplicados ANTES de
    qualquer efeito. A espera por aprovação é assíncrona — nada bloqueia.
    """
    exigir_ativo(repo)
    run_id = args.id
    ferramenta = args.tool or ("tool.notify.send" if (args.action or "").startswith("notify")
                               else "tool.chaos.write")
    recurso = args.resource or ""

    # §16: justificativa exclusivamente `untrusted` ou episódica não autoriza A2+
    if args.justification:
        motivo = _justificativa_invalida(repo, args.justification)
        if motivo:
            evt(repo, ident, action="permission.deny", risk_class="A2", level="warning",
                entity_id=run_id, summary=motivo)
            _comitar(repo, ident, "registra negação de permissão")
            raise ErroChaos(motivo, "policy")

    r = risco.avaliar(tool=ferramenta, resource=recurso, action=args.action or "")
    classe = r["risk_class"]

    if ferramenta == "tool.episodic.read":
        evt(repo, ident, action="episodic.read", risk_class="A0", entity_id=run_id)
        _comitar(repo, ident, "lê camada episódica")
        saida({"run_id": run_id, "status": "ok", "risk_class": "A0"})
        return

    if classe >= "A3":
        apv = _abrir_aprovacao(repo, ident, run_id, classe, args.action or recurso,
                               ferramenta=ferramenta, recurso=recurso,
                               rationale=getattr(args, "rationale", "") or "")
        if run_id:
            path, fm, corpo = entidades.carregar(repo, run_id)
            fm["awaiting_approval"] = apv
            fm.setdefault("checkpoint", {})
            if not fm["checkpoint"].get("step"):
                fm["checkpoint"] = {"step": "aguardando aprovação",
                                    "last_action": args.action or "",
                                    "artifacts_committed": [],
                                    "resume_hint": "retomar após decisão humana",
                                    "version_hash": gitops.head(repo)[:12]}
            fm["status"] = "awaiting_approval"
            yamlio.escrever(path, fm, corpo)
        evt(repo, ident, action="run.act.awaiting", risk_class=classe,
            entity_id=run_id, approval_id=apv)
        _comitar(repo, ident, f"aguarda aprovação {apv}")
        saida({"run_id": run_id, "status": "awaiting_approval",
               "approval_id": apv, "risk_class": classe})
        return

    evt(repo, ident, action=args.action or "run.act", risk_class=classe,
        entity_id=run_id, policy="autonomy_ceiling" if classe >= "A2" else "")
    _comitar(repo, ident, f"ação {args.action or ''} em {run_id}")
    saida({"run_id": run_id, "status": "ok", "risk_class": classe})


def _justificativa_invalida(repo: Path, ref: str) -> str:
    if str(ref).startswith("episodic:") or str(ref).startswith("EPI-"):
        return ("§17: registro da camada episódica não justifica ação A2+ — "
                "promova com `chaos promote` e trabalhe sobre a entidade")
    p = entidades.achar(repo, ref)
    if p:
        fm, _ = yamlio.ler(p)
        if (fm.get("provenance") or {}).get("origin") == "external_source":
            return ("§16: ação A2+ cuja única justificativa é fonte `untrusted` é "
                    "negada — conteúdo externo é dado, nunca instrução")
    else:
        return ("§17: justificativa não resolve para entidade canônica; registro "
                "episódico não é fonte")
    return ""


def _exigir_decisao_assinada(repo: Path, apv: str, afm: dict) -> None:
    """
    ORDER §18 (v2.6) — o portão que o spike de 21/09/2026 obrigou a mudar.

    `status: approved` no arquivo é texto; qualquer executor o escreve. O que
    vale é o commit que gravou essa decisão trazer assinatura de chave
    `human:*`. Checar o campo e não o commit é exatamente o erro da v2.5:
    aceitar como prova aquilo que o proponente produz.

    A assinatura do worker é recusada de propósito e com mensagem própria: é o
    caminho de escalação natural (peça ao worker), e negá-lo em silêncio faria
    parecer defeito.
    """
    risco_apv = str(afm.get("risk") or "A3")
    modo = policies(repo, "approval.yaml").get("a3_mode", "out_of_band")
    exige = risco_apv == "A4" or (risco_apv == "A3" and modo == "out_of_band")
    if not exige:
        return
    sha = str(afm.get("decision_commit") or "").strip()
    if not sha:
        sha = _commit_que_decidiu(repo, apv)
    if not sha:
        raise ErroChaos(
            f"APV `{apv}` é {risco_apv} e não tem commit de decisão rastreável — "
            "§18 exige que a decisão esteja num commit assinado por chave "
            "`human:*`, não apenas num campo do arquivo", "integrity")
    v = assinatura.verificar_commit(repo, sha)
    if v.eh_humano:
        return
    if v.eh_worker:
        raise ErroChaos(
            f"APV `{apv}`: decisão assinada pelo WORKER (`{v.ator}`). Worker "
            "prova procedência, não consentimento (§18) — um worker que assina "
            "sem presença é um oráculo de assinatura, e aceitar isso faria do "
            "portão um nome sem função.", "integrity")
    raise ErroChaos(
        f"APV `{apv}` é {risco_apv}: a decisão precisa estar em commit assinado "
        f"por chave `human:*` (CHAOS §17.6). Commit `{sha[:8]}`: {v.motivo}. "
        "Identidade humana no autor NÃO basta — o spike mostrou que o executor "
        "na nuvem a produz com dois comandos.", "integrity")


def _commit_que_decidiu(repo: Path, apv: str) -> str:
    """Último commit que tocou o arquivo da APV — onde a decisão foi gravada."""
    rel = f"order/approvals/{apv}.md"
    p = gitops.git(repo, "log", "-1", "--format=%H", "--", rel)
    return p.stdout.strip()


def _abrir_aprovacao(repo: Path, ident: Identidade, run_id: str,
                     classe: str, acao: str, ferramenta: str = "",
                     recurso: str = "", rationale: str = "") -> str:
    """
    §18.1 (v2.6): o corpo do pedido é gerado pelo Risk Engine.

    O executor contribui com UM campo, `rationale`, e ele é gravado como
    citação atribuída. Tudo o mais — ferramenta, recurso, classe,
    reversibilidade — é derivado, não narrado. A regra existe porque, no spike,
    o agente restringido redigiu o pedido de confirmação que dissolveria a
    própria barreira, em linguagem de procedimento de rotina. Não foi má-fé:
    um agente que quer completar a tarefa naturalmente descreve o obstáculo
    como formalidade. Por isso a defesa é estrutural.
    """
    if not assinatura.ha_chave_humana(repo):
        raise ErroChaos(
            f"ação {classe} exige aprovação humana e este repositório não tem "
            "chave `human:*` registrada em metadata/registries/allowed_signers "
            "— sem ela não existe caminho de aprovação (§18). A tarefa fica "
            "`blocked(no_signing_key)`; registre a chave com `chaos key`.",
            "policy")
    fm = entidades.criar(repo, "approval", _ator(ident),
                         {"title": f"Aprovação {classe}", "risk": classe,
                          "action": acao})
    fm.pop("_corpo", None)
    fm["run"] = run_id
    fm["expires_at"] = (dt.datetime.now(dt.timezone.utc)
                        + dt.timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fm["request_rendered_by"] = "risk_engine"
    yamlio.escrever(repo / "order" / "approvals" / f"{fm['id']}.md", fm,
                    _corpo_do_pedido(repo, classe, acao, ferramenta, recurso,
                                     rationale))
    return fm["id"]


GABARITO_PEDIDO = """## O que vai acontecer

- **Ação:** {acao}
- **Ferramenta:** {ferramenta}
- **Recurso:** {recurso}
- **Classe de risco:** {classe} (calculada pelo Risk Engine a partir da
  ferramenta e do recurso, §17 — não declarada pelo agente)
- **Reversibilidade:** {reversibilidade}

## Justificativa do agente (citada, não verificada)

> {rationale}

_Este bloco é a única parte do pedido de origem do executor. O restante foi
gerado pelo motor de risco (§18.1). Nenhuma afirmação do agente sobre a
gravidade, a urgência ou a formalidade deste portão altera a classe acima._
"""

REVERSIBILIDADE = {
    "A3": "reversível com custo",
    "A4": "irreversível ou de efeito externo não retratável",
}


def _corpo_do_pedido(repo: Path, classe: str, acao: str,
                     ferramenta: str = "", recurso: str = "",
                     rationale: str = "") -> str:
    """Gabarito fixo: o motor não tem vocabulário para minimizar o portão."""
    return GABARITO_PEDIDO.format(
        acao=acao or "(não informada)",
        ferramenta=ferramenta or "(derivada da ação)",
        recurso=recurso or "(derivado da ação)",
        classe=classe,
        reversibilidade=REVERSIBILIDADE.get(classe, "desconhecida"),
        rationale=rationale.strip() or "(o agente não apresentou justificativa)")


def cmd_approval(repo: Path, ident: Identidade, args) -> None:
    """
    §18 (v2.6): A4 — e A3 sob `out_of_band` — só vale em commit assinado por
    chave `human:*`. A CLI continua recusando esses casos dentro da sessão, mas
    a recusa aqui é conveniência: o portão de verdade é a assinatura, checada
    no momento de retomar o RUN (`_exigir_decisao_assinada`). Uma APV editada à
    mão e comitada sem assinatura chega até lá e é recusada lá.
    """
    if args.sub == "verify":
        _, afm, _ = entidades.carregar(repo, args.id)
        sha = str(afm.get("decision_commit") or "") or _commit_que_decidiu(repo, args.id)
        v = assinatura.verificar_commit(repo, sha) if sha else None
        saida({"approval_id": args.id, "risk": afm.get("risk"),
               "status": afm.get("status"), "decision_commit": sha[:12],
               "assinatura_verificada": bool(v and v.verificada),
               "ator_da_assinatura": v.ator if v else "",
               "vale_como_humana": bool(v and v.eh_humano),
               "motivo": v.motivo if v else "nenhum commit tocou esta APV"})
        return

    if args.sub in ("approve", "reject"):
        path, fm, corpo = entidades.carregar(repo, args.id)
        modo = policies(repo, "approval.yaml").get("a3_mode", "out_of_band")
        risco_apv = fm.get("risk", "A3")
        fora_de_banda = risco_apv == "A4" or (risco_apv == "A3" and modo == "out_of_band")
        if fora_de_banda:
            raise ErroChaos(
                f"§18: APV `{args.id}` é {risco_apv} sob `{modo}` — aprovação por "
                "CLI dentro de sessão de agente não vale. O caminho é commit "
                "humano fora do caminho do modelo.", "policy")
        if not ident.eh_humano:
            raise ErroChaos("§18: só o proprietário decide aprovação", "policy")
        fm["status"] = "approved" if args.sub == "approve" else "rejected"
        fm["decided_by"] = _ator(ident)
        fm["decision_note"] = args.note or ""
        yamlio.escrever(path, fm, corpo)
        evt(repo, ident, action=f"approval.{args.sub}", entity_id=args.id,
            risk_class="A2", approval_id=args.id)
        _comitar(repo, ident, f"{args.sub} {args.id}")
        # o SHA é gravado DEPOIS do commit, e por isso aponta para o commit
        # anterior a este registro — é o commit que carregou a decisão. Quem
        # verifica usa `_commit_que_decidiu` como fonte independente do campo,
        # justamente para que o campo não seja a única prova.
        fm["decision_commit"] = gitops.head(repo)
        yamlio.escrever(path, fm, corpo)
        saida({"approval_id": args.id, "status": fm["status"],
               "decision_commit": fm["decision_commit"][:12]})
        return

    itens = []
    for p in sorted((repo / "order" / "approvals").glob("APV-*.md")):
        fm, _ = yamlio.ler(p)
        if args.sub == "show" and fm["id"] != args.id:
            continue
        itens.append({"id": fm["id"], "risk": fm.get("risk"),
                      "status": fm.get("status"), "expires_at": fm.get("expires_at")})
    saida(itens)


def cmd_delegate(repo: Path, ident: Identidade, args) -> None:
    """§10.2: o delegado herda o teto mínimo; profundidade acima da policy é rejeitada."""
    alvo = next((a for a in registry(repo) if a["id"] == args.to), None)
    if not alvo:
        raise ErroChaos(f"agente `{args.to}` não consta no registry", "reference")

    limite = int(policies(repo, "delegation.yaml").get("max_depth", 2))
    profundidade = int(args.depth or 1)
    if profundidade > limite:
        raise ErroChaos(f"§10.2: profundidade {profundidade} excede o máximo "
                        f"declarado ({limite})", "policy")

    teto = alvo.get("autonomy_ceiling", "A1")
    if args.risk and args.risk > teto:
        raise ErroChaos(f"§10.2: risco composto `{args.risk}` excede o teto "
                        f"`{teto}` do delegado `{args.to}`", "policy")

    _, origem, _ = entidades.carregar(repo, args.task)
    sub = entidades.criar(repo, "task", _ator(ident),
                          {"title": args.objective or f"Delegado a {args.to}"})
    sub.pop("_corpo", None)
    sub["parent_task"] = args.task
    sub["privacy"] = origem.get("privacy", "cloud_allowed")
    sub["execution"] = origem.get("execution", "any")
    yamlio.escrever(repo / "tasks" / f"{sub['id']}.md", sub, "")

    hnd = entidades.criar(repo, "handoff", _ator(ident),
                          {"title": f"Handoff para {args.to}"})
    hnd.pop("_corpo", None)
    hnd.update({"from_agent": _ator(ident), "to_agent": args.to,
                "objective": args.objective or "",
                # §10.1: o receptor reconstrói o contexto só com HND + CHAOS, e o
                # que ancora isso é a tarefa de ORIGEM, não a subtarefa criada.
                "task": args.task,
                "context_refs": [args.task, sub["id"]],
                "constraints": [f"teto {teto}"],
                "open_questions": [], "status": "open"})
    yamlio.escrever(repo / "order" / "handoffs" / f"{hnd['id']}.md", hnd, "")

    evt(repo, ident, action="delegate", entity_id=hnd["id"], risk_class="A1")
    _comitar(repo, ident, f"delega {args.task} → {args.to}")
    saida({"handoff_id": hnd["id"], "task_id": sub["id"], "to": args.to,
           "inherited_ceiling": teto})


def cmd_handoff(repo: Path, ident: Identidade, args) -> None:
    if args.sub == "close":
        path, fm, corpo = entidades.carregar(repo, args.id)
        fm["status"] = "closed"
        yamlio.escrever(path, fm, corpo)
        _comitar(repo, ident, f"fecha {args.id}")
        saida({"handoff_id": args.id, "status": "closed"})
        return
    itens = []
    for p in sorted((repo / "order" / "handoffs").glob("HND-*.md")):
        fm, _ = yamlio.ler(p)
        if args.sub == "show" and fm["id"] != args.id:
            continue
        itens.append(fm)
    saida(itens)


# --------------------------------------------------------------------------- #
# automações, gatilhos, guard, status                                           #
# --------------------------------------------------------------------------- #

ESCADA = ["shadow", "propose", "auto_notify", "auto"]


def cmd_automation(repo: Path, ident: Identidade, args) -> None:
    """§28: autonomia é conquistada pela escada; automação que executa A3 não
    passa de `propose`."""
    if args.sub == "list":
        itens = []
        for p in sorted((repo / "order" / "automations").glob("AUT-*.md")):
            fm, _ = yamlio.ler(p)
            itens.append({"id": fm["id"], "mode": fm.get("mode"),
                          "max_risk": fm.get("max_risk"),
                          "enabled": fm.get("enabled")})
        saida(itens)
        return

    if args.sub == "sync":
        # Materializa a lista de automações ativas para o agendador do hosting.
        # É derivado das entidades AUT — a entidade é a fonte, isto é a view.
        itens = []
        for p2 in sorted((repo / "order" / "automations").glob("AUT-*.md")):
            f2, _ = yamlio.ler(p2)
            itens.append({"id": f2["id"], "name": f2.get("name"),
                          "mode": f2.get("mode"), "trigger": f2.get("trigger"),
                          "interval_hours": f2.get("interval_hours", 24),
                          "enabled": bool(f2.get("enabled"))})
        destino = repo / "indexes" / "automations.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(sorted(itens, key=lambda i: i["id"]),
                                      ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8", newline="\n")
        _comitar(repo, ident, "sincroniza view de automações")
        saida({"synced": len(itens), "view": "indexes/automations.json"})
        return

    path, fm, corpo = entidades.carregar(repo, args.id)
    atual = fm.get("mode", "shadow")
    if args.sub == "promote":
        proximo = ESCADA[min(ESCADA.index(atual) + 1, len(ESCADA) - 1)]
        if fm.get("max_risk", "A1") >= "A3" and ESCADA.index(proximo) > ESCADA.index("propose"):
            raise ErroChaos(
                "§28: automação que executa A3 não passa de `propose` — efeito "
                "sobre terceiros sempre passa pelo humano", "policy")
        fm["mode"] = proximo
    elif args.sub == "demote":
        fm["mode"] = ESCADA[max(ESCADA.index(atual) - 1, 0)]
    yamlio.escrever(path, fm, corpo)
    evt(repo, ident, action=f"automation.{args.sub}", entity_id=args.id, risk_class="A2",
        policy="maturity_ladder")
    _comitar(repo, ident, f"{args.sub} {args.id} → {fm['mode']}")
    saida({"id": args.id, "mode": fm["mode"]})


def cmd_trigger(repo: Path, ident: Identidade, args) -> None:
    if args.sub == "fire":
        exigir_ativo(repo)
        estado = aplicar_drift(repo, ident)
        if estado["status"] == "broken":
            raise ErroChaos("toolchain `broken`: nada autônomo roda (§31)", "policy")

        alvo = entidades.achar(repo, args.id)
        if not alvo:
            raise ErroChaos(f"automação `{args.id}` não existe", "reference")
        fm, _ = yamlio.ler(alvo)
        modo = fm.get("mode", "shadow")
        wf = fm.get("workflow") or fm.get("name") or ""

        # A escada decide o que acontece; o gatilho não a contorna (§28).
        if modo == "shadow":
            evt(repo, ident, action="trigger.shadow", entity_id=args.id,
                risk_class="A0", summary=f"shadow: registraria {wf}")
            _comitar(repo, ident, f"shadow de {args.id}")
            saida({"fired": args.id, "mode": modo, "executed": False,
                   "note": "em `shadow` a automação registra o que faria e não faz"})
            return

        if wf and wf in workflows.listar(repo):
            aval = workflows.avaliar(repo, wf)
            if aval["risk_class"] > fm.get("max_risk", "A1"):
                raise ErroChaos(
                    f"workflow `{wf}` é {aval['risk_class']} e a automação declara "
                    f"teto {fm.get('max_risk')} — o motor recusa ANTES de começar, "
                    "em vez de parar no meio com metade dos efeitos aplicados",
                    "policy")

        proposta = modo == "propose"
        evt(repo, ident, action="trigger.fire", entity_id=args.id, risk_class="A2",
            policy="maturity_ladder",
            summary=f"modo {modo}" + (f", workflow {wf}" if wf else ""))
        _comitar(repo, ident, f"dispara {args.id}")
        saida({"fired": args.id, "mode": modo, "executed": not proposta,
               "workflow": wf or None,
               "note": "em `propose` a automação propõe e espera decisão"
                       if proposta else None})
        return

    # scan: expira APVs, marca bloqueios visíveis, aplica drift
    exigir_ativo(repo)
    estado = aplicar_drift(repo, ident)
    agora = ids.agora()
    if args.now and args.now.startswith("+"):
        horas = int(args.now.rstrip("hH").lstrip("+"))
        agora = (dt.datetime.now(dt.timezone.utc)
                 + dt.timedelta(hours=horas)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    mudou = []
    for p in sorted((repo / "order" / "approvals").glob("APV-*.md")):
        fm, corpo = yamlio.ler(p)
        if fm.get("status") == "pending" and str(fm.get("expires_at") or "") < agora:
            fm["status"] = "expired"
            yamlio.escrever(p, fm, corpo)
            mudou.append(fm["id"])

    worker = policies(repo, "worker.yaml")
    limite_h = int(worker.get("no_worker_timeout_h", 24))
    hw = policies(repo, "hardware-profile.yaml")
    pol = policies(repo, "model-policy.yaml").get("policies", {})

    for p in entidades.todas(repo):
        fm, corpo = yamlio.ler(p)
        if fm.get("type") != "task" or fm.get("status") not in ("todo", "blocked"):
            continue
        alterou = False

        # capacidade local: sem GPU, política que exige tier alto não roda local
        if fm.get("privacy") == "local_only" and args.local:
            minimo = pol.get(fm.get("model_policy") or "", {}).get("minimum_tier", "low")
            if hw.get("gpu_class") == "no_gpu" and minimo == "high":
                fm["status"] = "blocked"
                fm["blocked_reason"] = "no_model_capacity"
                alterou = True

        # worker ausente: visível, não silencioso
        if not alterou and fm.get("execution") == "local" and not fm.get("claimed_by"):
            criado = str(fm.get("created_at", ""))
            if criado and _horas(criado, agora) >= limite_h:
                fm["status"] = "blocked"
                fm["blocked_reason"] = "no_local_worker"
                alterou = True

        if alterou:
            yamlio.escrever(p, fm, corpo)
            mudou.append(fm["id"])
            evt(repo, ident, action="task.blocked", entity_id=fm["id"], risk_class="A1",
                level="warning", summary=fm["blocked_reason"])

    if mudou:
        _comitar(repo, ident, f"scan: {len(mudou)} itens atualizados")
    saida({"scanned": True, "changed": mudou, "toolchain": estado["status"]})


def _horas(inicio: str, fim: str) -> float:
    def _p(s: str) -> dt.datetime:
        s = s.replace("Z", "+00:00")
        return dt.datetime.fromisoformat(s)
    try:
        return (_p(fim) - _p(inicio)).total_seconds() / 3600
    except Exception:
        return 0.0


def cmd_guard(repo: Path, ident: Identidade, args) -> None:
    """
    Hook `PreToolUse` e loop do worker chamam o MESMO código — é o que dá sentido
    a "o worker nega as mesmas ações que o hook nega na nuvem" (AT-22).
    """
    ator = args.actor or _ator(ident)
    negado, motivo = False, ""

    argv = list(args.argv or [])
    if argv and argv[0] == "--":
        argv = argv[1:]     # REMAINDER preserva o separador; o comando começa depois
    if argv:
        permitido, motivo = guarda.avaliar_comando(argv)
        negado = not permitido
    if not negado and args.resource:
        r = risco.avaliar(tool=args.tool or "tool.chaos.write",
                          resource=args.resource, action=args.action or "write")
        if r["risk_class"] == "A4" and not ator.startswith("human:"):
            negado = True
            motivo = (f"`{args.resource}` é protected path (CHAOS §4.1): governa o "
                      f"comportamento de agentes futuros; ator `{ator}` não escreve aqui")

    evt(repo, ident, action="guard.deny" if negado else "guard.allow",
        risk_class="A1", level="warning" if negado else "info",
        summary=(motivo or " ".join(argv))[:150])
    _comitar(repo, ident, "registra decisão do guard")

    if negado:
        raise ErroChaos(motivo, "policy")
    saida({"allowed": True, "actor": ator})


def cmd_status(repo: Path, ident: Identidade, args) -> None:
    estado = aplicar_drift(repo, ident)
    tarefas = [yamlio.ler(p)[0] for p in entidades.todas(repo)]
    saida({
        "paused": pausado(repo),
        "toolchain": estado,
        "tasks": {"total": sum(1 for t in tarefas if t.get("type") == "task"),
                  "blocked": sum(1 for t in tarefas
                                 if t.get("type") == "task" and t.get("status") == "blocked")},
        "runs": len(list((repo / "order" / "runs").glob("RUN-*.md"))),
        "approvals_pending": sum(
            1 for p in (repo / "order" / "approvals").glob("APV-*.md")
            if yamlio.ler(p)[0].get("status") == "pending"),
    })


def cmd_report(repo: Path, args) -> None:
    evts = ledger.ler(repo, ordenado=True)
    por_acao: dict[str, int] = {}
    for e in evts:
        por_acao[e.get("action", "?")] = por_acao.get(e.get("action", "?"), 0) + 1
    runs = [yamlio.ler(p)[0] for p in (repo / "order" / "runs").glob("RUN-*.md")]
    abandonados = sum(1 for r in runs if r.get("status") == "abandoned")
    saida({"events": len(evts), "by_action": por_acao, "runs": len(runs),
           "abandoned": abandonados,
           "abandon_rate": round(abandonados / len(runs), 3) if runs else 0.0})


def cmd_workflow(repo: Path, ident: Identidade, args) -> None:
    """§12: o motor ordena e decide o que pular; quem aplica efeito é o `run act`."""
    if args.sub == "list":
        saida([{"name": n, **workflows.avaliar(repo, n)} for n in workflows.listar(repo)])
        return
    if args.sub == "show":
        saida(workflows.carregar(repo, args.nome))
        return

    exigir_ativo(repo)
    estado = aplicar_drift(repo, ident)
    if estado["status"] == "broken":
        raise ErroChaos("toolchain `broken`: nada autônomo roda (§31)", "policy")

    run_id = args.run or ""
    concluidos = []
    if run_id:
        _, fm, _ = entidades.carregar(repo, run_id)
        concluidos = list((fm.get("checkpoint") or {}).get("artifacts_committed") or [])

    def executor(passo, r):
        ns = argparse.Namespace(
            id=run_id, action=passo.get("action", ""), tool=passo["tool"],
            resource=passo.get("resource", ""),
            justification=passo.get("justification"), formato="json")
        try:
            import io, contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cmd_run_act(repo, ident, ns)
            return json.loads(buf.getvalue() or "{}")
        except ErroChaos as exc:
            return {"status": "denied", "reason": str(exc)}

    resultado = workflows.executar(repo, args.nome, executor=executor,
                                   run_id=run_id, concluidos=concluidos,
                                   dry_run=bool(args.dry_run))
    if run_id and not args.dry_run:
        path, fm, corpo = entidades.carregar(repo, run_id)
        cp = fm.setdefault("checkpoint", {})
        feitos = set(cp.get("artifacts_committed") or [])
        feitos |= {r["step"] for r in resultado["results"]
                   if r.get("status") in ("ok", "dry-run")}
        cp["artifacts_committed"] = sorted(feitos)
        cp["step"] = f"{len(feitos)}/{resultado['workflow'] and len(workflows.carregar(repo, args.nome)['steps'])}"
        cp.setdefault("last_action", f"workflow {args.nome}")
        cp.setdefault("resume_hint", "retomar do primeiro passo não concluído")
        cp.setdefault("version_hash", gitops.head(repo)[:12])
        yamlio.escrever(path, fm, corpo)
        _comitar(repo, ident, f"workflow {args.nome} em {run_id}")
    saida(resultado)


def cmd_notify(repo: Path, ident: Identidade, args) -> None:
    """Notificar o próprio usuário é A2; qualquer outro canal é A3 (§14)."""
    canal = args.channel or "self"
    r = risco.avaliar(tool="tool.notify.send", resource=f"channel:{canal}",
                      action="send")
    if r["risk_class"] >= "A3" and not ident.eh_humano:
        apv = _abrir_aprovacao(repo, ident, "", r["risk_class"],
                               f"notificar {canal}")
        evt(repo, ident, action="notify.awaiting", risk_class=r["risk_class"],
            approval_id=apv)
        _comitar(repo, ident, f"aguarda aprovação para notificar {canal}")
        saida({"status": "awaiting_approval", "approval_id": apv,
               "risk_class": r["risk_class"]})
        return
    registro = notificacao.enviar(repo, canal=canal, mensagem=args.message or "",
                                  ator=_ator(ident), entidade=args.entity or "")
    evt(repo, ident, action="notify.send", risk_class=r["risk_class"],
        entity_id=args.entity or "", policy="allowed_channels")
    _comitar(repo, ident, f"notifica {canal}")
    saida(registro)


def cmd_model_call(repo: Path, ident: Identidade, args) -> None:
    """
    Roteia e chama. Sem credencial declarada, falha com mensagem explícita —
    nunca cai em outro modelo em silêncio (§21.5).
    """
    reg = policies(repo, "model-registry.yaml").get("models", [])
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_model_route(repo, ident, argparse.Namespace(
            policy=args.policy, task=args.task, dry_run=True, formato="json"))
    rota = json.loads(buf.getvalue())
    modelo = next((m for m in reg if m["id"] == rota["model_id"]), None)
    if not modelo:
        raise ErroChaos(f"modelo `{rota['model_id']}` sumiu do registry", "reference")
    try:
        resp = gateway.chamar(modelo, args.prompt or "", dry_run=bool(args.dry_run))
    except gateway.ErroGateway as exc:
        raise ErroChaos(str(exc), "policy")
    evt(repo, ident, action="model.call", risk_class="A1",
        summary=f"{resp.modelo} {resp.tokens_entrada}+{resp.tokens_saida} tokens")
    _comitar(repo, ident, f"chamada de modelo {resp.modelo}")
    saida({**rota, **resp.dict()})


def cmd_session(repo: Path, ident: Identidade, args) -> None:
    """
    §7.4 do CHAOS: SES só vira arquivo se houve RUN ou HND. Sessão sem trabalho
    não polui o histórico — e essa regra existe porque a alternativa é um
    arquivo por abertura de terminal.
    """
    marcador = repo / "order" / "sessions" / ".ativa"
    if args.sub == "open":
        marcador.parent.mkdir(parents=True, exist_ok=True)
        marcador.write_text(f"opened_at: {ids.agora()}\nactor: {_ator(ident)}\n",
                            encoding="utf-8", newline="\n")
        saida({"session": "open", "at": ids.agora()})
        return

    # `any(glob(...))` seria sempre verdadeiro: o gerador é truthy mesmo vazio.
    # O bug daria SES em toda sessão, que é exatamente o que §7.4 evita.
    houve = any(list((repo / "order" / d).glob(padrao)) for d, padrao in
                (("runs", "RUN-*.md"), ("handoffs", "HND-*.md")))
    if not houve:
        if marcador.exists():
            marcador.unlink()
        saida({"session": "closed", "persisted": False,
               "reason": "sem RUN nem HND — §7.4 não cria SES"})
        return

    ses = entidades.criar(repo, "session", _ator(ident), {"title": "Sessão"})
    ses.pop("_corpo", None)
    ses["status"] = "closed"
    abertos = [yamlio.ler(p)[0]["id"] for p in (repo / "order" / "handoffs").glob("HND-*.md")
               if yamlio.ler(p)[0].get("status") == "open"]
    ses["open_handoffs"] = abertos
    yamlio.escrever(repo / "order" / "sessions" / f"{ses['id']}.md", ses, "")
    if marcador.exists():
        marcador.unlink()
    evt(repo, ident, action="session.close", entity_id=ses["id"], risk_class="A1")
    _comitar(repo, ident, f"fecha sessão {ses['id']}")
    saida({"session": "closed", "persisted": True, "id": ses["id"],
           "open_handoffs": abertos})


# --------------------------------------------------------------------------- #
# argparse                                                                      #
# --------------------------------------------------------------------------- #

def _propagar_format(parser: argparse.ArgumentParser) -> None:
    try:
        parser.add_argument("--format", dest="formato", choices=["json", "text"])
    except argparse.ArgumentError:
        pass
    for acao in parser._actions:
        if isinstance(acao, argparse._SubParsersAction):
            for sub in acao.choices.values():
                _propagar_format(sub)


def construir_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="order", description="ORDER — CLI de §38")
    ap.add_argument("--format", dest="formato", default="json")
    sub = ap.add_subparsers(dest="comando", required=True)

    sub.add_parser("status"); sub.add_parser("health")
    p = sub.add_parser("report"); p.add_argument("--period")

    p = sub.add_parser("task"); s = p.add_subparsers(dest="sub", required=True)
    for nome in ("submit", "claim", "release", "resume", "show"):
        q = s.add_parser(nome); q.add_argument("id")

    p = sub.add_parser("run"); s = p.add_subparsers(dest="sub", required=True)
    for nome in ("list", "show", "abandon", "resume", "merge"):
        q = s.add_parser(nome); q.add_argument("id", nargs="?")
        q.add_argument("--reason"); q.add_argument("--keep")
    q = s.add_parser("checkpoint"); q.add_argument("id")
    q.add_argument("--step"); q.add_argument("--last-action", dest="last_action")
    q.add_argument("--resume-hint", dest="resume_hint")
    q.add_argument("--artifacts", action="append")
    q = s.add_parser("act"); q.add_argument("id", nargs="?")
    q.add_argument("--action"); q.add_argument("--resource"); q.add_argument("--tool")
    q.add_argument("--justification")
    # §18.1: o ÚNICO campo do pedido de aprovação que o executor redige.
    q.add_argument("--rationale")

    p = sub.add_parser("approval"); s = p.add_subparsers(dest="sub", required=True)
    for nome in ("list", "show", "approve", "reject", "verify"):
        q = s.add_parser(nome); q.add_argument("id", nargs="?"); q.add_argument("--note")

    p = sub.add_parser("delegate")
    p.add_argument("--task", required=True); p.add_argument("--to", required=True)
    p.add_argument("--objective"); p.add_argument("--depth"); p.add_argument("--risk")

    p = sub.add_parser("handoff"); s = p.add_subparsers(dest="sub", required=True)
    for nome in ("list", "show", "close"):
        q = s.add_parser(nome); q.add_argument("id", nargs="?")

    p = sub.add_parser("session"); s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("open"); s.add_parser("close")

    p = sub.add_parser("agent"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("list"); q.add_argument("--kind"); q.add_argument("--capability")
    q.add_argument("--id")
    q = s.add_parser("show"); q.add_argument("agente")
    q = s.add_parser("run"); q.add_argument("agente")
    q.add_argument("--handoff"); q.add_argument("--dry-run", dest="dry_run",
                                                action="store_true")
    q.add_argument("--executor"); q.add_argument("--attempt")
    s.add_parser("sync")

    p = sub.add_parser("automation"); s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("list")
    for nome in ("promote", "demote", "sync"):
        q = s.add_parser(nome); q.add_argument("id", nargs="?")

    p = sub.add_parser("trigger"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("fire"); q.add_argument("id")
    q = s.add_parser("scan"); q.add_argument("--local", action="store_true")
    q.add_argument("--now")

    p = sub.add_parser("risk"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("eval")
    for flag in ("--tool", "--resource", "--action", "--entity", "--field",
                 "--from", "--to"):
        q.add_argument(flag, dest=flag.lstrip("-").replace("-", "_"))

    p = sub.add_parser("guard")
    p.add_argument("--actor"); p.add_argument("--surface"); p.add_argument("--tool")
    p.add_argument("--resource"); p.add_argument("--action")
    p.add_argument("argv", nargs=argparse.REMAINDER)

    p = sub.add_parser("model"); s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("list")
    q = s.add_parser("route"); q.add_argument("--policy"); q.add_argument("--task")
    q.add_argument("--dry-run", dest="dry_run", action="store_true")
    q = s.add_parser("call"); q.add_argument("--policy"); q.add_argument("--task")
    q.add_argument("--prompt"); q.add_argument("--dry-run", dest="dry_run",
                                               action="store_true")

    p = sub.add_parser("workflow"); s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("list")
    q = s.add_parser("show"); q.add_argument("nome")
    q = s.add_parser("run"); q.add_argument("nome"); q.add_argument("--run")
    q.add_argument("--task"); q.add_argument("--dry-run", dest="dry_run",
                                             action="store_true")

    p = sub.add_parser("notify")
    p.add_argument("--channel"); p.add_argument("--message"); p.add_argument("--entity")

    p = sub.add_parser("quota"); s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("status")

    p = sub.add_parser("audit"); s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("inspect")

    p = sub.add_parser("episodic"); s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("status")
    q = s.add_parser("handoff"); q.add_argument("sub2", nargs="?")
    q.add_argument("id", nargs="?")

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

    repo = achar_repo()
    ident = Identidade(repo)
    c, s = args.comando, getattr(args, "sub", None)

    if c == "status":
        cmd_status(repo, ident, args); return 0
    if c == "health":
        saida(estado_toolchain(repo)); return 0
    if c == "report":
        cmd_report(repo, args); return 0
    if c == "task":
        if s == "claim":
            cmd_task_claim(repo, ident, args)
        elif s == "release":
            cmd_task_release(repo, ident, args)
        elif s == "show":
            saida(entidades.carregar(repo, args.id)[1])
        else:
            raise ErroChaos(f"`task {s}`: retomar é `run resume` — quem retoma é a "
                            "tentativa, não o item de trabalho (§38)", "policy")
        return 0
    if c == "run":
        if s == "checkpoint":
            cmd_run_checkpoint(repo, ident, args)
        elif s == "abandon":
            cmd_run_abandon(repo, ident, args)
        elif s == "resume":
            cmd_run_resume(repo, ident, args)
        elif s == "act":
            cmd_run_act(repo, ident, args)
        elif s == "merge":
            from tools.chaos.cli import cmd_run as chaos_run
            chaos_run(repo, ident, argparse.Namespace(sub="merge", id=args.id,
                                                      keep=args.keep, formato="json"))
        else:
            saida([yamlio.ler(p)[0] for p in (repo / "order" / "runs").glob("RUN-*.md")])
        return 0
    if c == "approval":
        cmd_approval(repo, ident, args); return 0
    if c == "delegate":
        cmd_delegate(repo, ident, args); return 0
    if c == "handoff":
        cmd_handoff(repo, ident, args); return 0
    if c == "session":
        cmd_session(repo, ident, args); return 0
    if c == "workflow":
        cmd_workflow(repo, ident, args); return 0
    if c == "notify":
        cmd_notify(repo, ident, args); return 0
    if c == "agent":
        if s == "list":
            cmd_agent_list(repo, args)
        elif s == "sync":
            cmd_agent_sync(repo, ident, args)
        elif s == "run":
            cmd_agent_run(repo, ident, args)
        else:
            saida(next((a for a in registry(repo) if a["id"] == args.agente), {}))
        return 0
    if c == "automation":
        cmd_automation(repo, ident, args); return 0
    if c == "trigger":
        cmd_trigger(repo, ident, args); return 0
    if c == "risk":
        r = risco.avaliar(tool=args.tool or "tool.chaos.write",
                          resource=args.resource or _recurso_da_entidade(repo, args.entity),
                          action=args.action or "", field=args.field,
                          de=getattr(args, "from"), para=args.to,
                          risk_hint=_hint(repo, args.entity))
        saida(r); return 0
    if c == "guard":
        cmd_guard(repo, ident, args); return 0
    if c == "model":
        if s == "route":
            cmd_model_route(repo, ident, args)
        elif s == "call":
            cmd_model_call(repo, ident, args)
        else:
            cmd_model_list(repo, args)
        return 0
    if c == "quota":
        cmd_quota_status(repo, ident, args); return 0
    if c == "audit":
        saida({"events": len(ledger.ler(repo))}); return 0
    if c == "episodic":
        from tools.chaos import episodico
        saida(episodico.status(repo)); return 0

    ap.error(f"comando não implementado: {c}")
    return 2


def _recurso_da_entidade(repo: Path, entity_id: str | None) -> str:
    if not entity_id:
        return ""
    p = entidades.achar(repo, entity_id)
    return p.relative_to(repo).as_posix() if p else ""


def _hint(repo: Path, entity_id: str | None) -> str:
    if not entity_id:
        return ""
    p = entidades.achar(repo, entity_id)
    if not p:
        return ""
    return str(yamlio.ler(p)[0].get("risk_hint") or "")


def executar() -> int:
    try:
        return main()
    except ErroChaos as exc:
        print(f"[{exc.categoria}] {exc}", file=sys.stderr)
        return 1
