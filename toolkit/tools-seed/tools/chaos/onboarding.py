"""
Onboarding Protocol (Implementação §3) — obrigatório antes da Fase 0.

Duas regras governam este módulo e valem a pena estar no topo:

1. **Nada tem default silencioso.** Onde há default, ele é MOSTRADO e aceito
   explicitamente. Por isso cada pergunta declara `default` e o relatório
   registra se a resposta foi digitada ou aceita — a diferença importa quando,
   seis meses depois, alguém perguntar por que a cota é 50.

2. **Nada é assumido do histórico do usuário.** Nem de perfil, nem de memória,
   nem de outra implantação. Uma resposta só existe se foi dada agora.

O produto é `reports/onboarding-<data>.md` com cada resposta e o arquivo que a
materializou. A Fase 0 só começa depois que o usuário confirma esse relatório.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import areas, ids, layout, yamlio
from .repo import ErroChaos


@dataclass
class Pergunta:
    chave: str
    texto: str
    destino: str
    default: object = None          # None = resposta obrigatória, sem default
    opcoes: list[str] = field(default_factory=list)
    lista: bool = False             # resposta é lista separada por vírgula
    bool_: bool = False
    bloco: str = ""

    def formatar(self) -> str:
        partes = [self.texto]
        if self.opcoes:
            partes.append(f"[{' | '.join(self.opcoes)}]")
        if self.default is not None:
            partes.append(f"(default mostrado: {self.default})")
        else:
            partes.append("(sem default — resposta obrigatória)")
        return " ".join(partes)


PERGUNTAS: list[Pergunta] = [
    # ---- §3.1 identidade e superfícies ----
    Pergunta("owner", "Identificador do proprietário", "metadata/repo.yaml, AGENTS.md",
             default="human:owner", bloco="3.1 Identidade e superfícies"),
    Pergunta("language", "Idioma de trabalho", "AGENTS.md", default="pt-BR",
             bloco="3.1 Identidade e superfícies"),
    Pergunta("timezone", "Fuso horário", "order/policies/quotas.yaml",
             default="America/Sao_Paulo", bloco="3.1 Identidade e superfícies"),
    Pergunta("quiet_hours", "Horário de silêncio (HH:MM-HH:MM)",
             "order/policies/quotas.yaml", default="22:00-07:00",
             bloco="3.1 Identidade e superfícies"),
    Pergunta("surfaces", "Superfícies que usará", "AGENTS.md, hooks", lista=True,
             default="claude-code-cloud,claude-code-local,desktop,mobile",
             bloco="3.1 Identidade e superfícies"),
    Pergunta("host_os", "Sistema operacional da máquina local",
             "order/policies/worker.yaml", opcoes=["windows", "macos", "linux"],
             default="windows", bloco="3.1 Identidade e superfícies"),
    Pergunta("human_email", "E-mail Git do humano (identidade própria)",
             "metadata/registries/executors.yaml", default=None,
             bloco="3.1 Identidade e superfícies"),
    Pergunta("worker_email", "E-mail Git do worker local (conta de serviço ou deploy key)",
             "metadata/registries/executors.yaml", default=None,
             bloco="3.1 Identidade e superfícies"),
    Pergunta("cloud_email", "E-mail Git do runtime na nuvem (app do Claude Code)",
             "metadata/registries/executors.yaml", default=None,
             bloco="3.1 Identidade e superfícies"),
    # ---- §3.1 (v1.4) autenticação e chaves — o que o spike obrigou ----
    #
    # Dois achados do spike de 21/09/2026 viraram perguntas. O primeiro é
    # banal e custou uma sessão: numa instalação limpa do Git for Windows não
    # há credential.helper, a autenticação por senha não existe mais no
    # GitHub, e o primeiro push falha com um erro que não parece de
    # configuração. O Onboarding presumia que o Git alcançava o remoto.
    Pergunta("git_auth_ok",
             "A autenticação Git desta máquina já foi verificada? "
             "(`git config --global credential.helper` responde e um clone de "
             "teste conclui)",
             "verificação do Onboarding", bool_=True, default=None,
             bloco="3.1 Identidade e superfícies"),
    # O segundo é a raiz de confiança inteira (CHAOS §17.6).
    Pergunta("human_signing_principal",
             "Principal da chave de assinatura HUMANA (o e-mail no allowed_signers)",
             "metadata/registries/allowed_signers", default=None,
             bloco="3.1 Identidade e superfícies"),
    Pergunta("worker_signing_principal",
             "Principal da chave de assinatura do WORKER (procedência, não consentimento)",
             "metadata/registries/allowed_signers", default=None,
             bloco="3.1 Identidade e superfícies"),
    Pergunta("segunda_chave_humana",
             "Existe uma SEGUNDA chave humana, em outra máquina ou mídia? "
             "Sem ela, perder a máquina significa nunca mais aprovar A4 — "
             "registrar nova chave exige assinatura da que se perdeu",
             "metadata/registries/allowed_signers", bool_=True, default=None,
             bloco="3.1 Identidade e superfícies"),

    # ---- §3.2 repositórios e classes ----
    Pergunta("privacy_classes", "Quais contextos de vida separar (classes de privacidade)",
             "metadata/registries/privacy-classes.yaml", lista=True, default=None,
             bloco="3.2 Repositórios e classes de privacidade"),
    Pergunta("remote", "Remoto deste repositório (vazio = local-only)",
             "metadata/repo.yaml.remote", default="",
             bloco="3.2 Repositórios e classes de privacidade"),
    Pergunta("default_privacy", "Privacidade padrão das entidades desta classe",
             "metadata/repo.yaml.default_privacy",
             opcoes=["cloud_allowed", "local_only"], default="cloud_allowed",
             bloco="3.2 Repositórios e classes de privacidade"),
    Pergunta("views_builder", "Quem comita views derivadas",
             "metadata/repo.yaml.views_builder", opcoes=["hosting", "local_worker"],
             default="local_worker", bloco="3.2 Repositórios e classes de privacidade"),
    Pergunta("allowed_channels", "Canais em que este repositório pode notificar",
             "metadata/repo.yaml.allowed_channels", lista=True, default="self",
             bloco="3.2 Repositórios e classes de privacidade"),
    Pergunta("episodic", "Ativar a camada episódica nesta classe",
             "metadata/repo.yaml.episodic, .ai-memory.toml", bool_=True, default=True,
             bloco="3.2 Repositórios e classes de privacidade"),
    Pergunta("capture_ignore", "Caminhos que NUNCA podem ser capturados",
             ".ai-memory.toml [capture] ignore_paths", lista=True,
             default="metadata/**,order/policies/**",
             bloco="3.2 Repositórios e classes de privacidade"),

    # ---- §3.3 áreas, equipe e Assistente ----
    Pergunta("assistant_name", "Nome do Assistente Pessoal (agente obrigatório)",
             "order/agents/registry.yaml", default="Assistente Pessoal",
             bloco="3.3 Áreas, equipe e Assistente Pessoal"),
    Pergunta("areas", "Áreas de responsabilidade (slugs; sugerir 2 a 4 no MVP)",
             "areas/<slug>/state.md, order/agents/registry.yaml", lista=True,
             default=None, bloco="3.3 Áreas, equipe e Assistente Pessoal"),
    Pergunta("functionals", "Especialistas funcionais a ativar",
             "order/agents/registry.yaml", lista=True,
             default="researcher,planner,reviewer,librarian",
             bloco="3.3 Áreas, equipe e Assistente Pessoal"),

    # ---- §3.4 modelos, assinaturas e hardware ----
    Pergunta("budget_sources", "Assinaturas/planos de IA que você possui",
             "order/policies/quotas.yaml.budget_sources", lista=True, default=None,
             bloco="3.4 Modelos, assinaturas e hardware"),
    Pergunta("enable_pay_per_use", "Habilitar alguma fonte paga por uso",
             "order/policies/quotas.yaml", bool_=True, default=False,
             bloco="3.4 Modelos, assinaturas e hardware"),
    Pergunta("gpu_class", "Hardware local: GPU e VRAM",
             "order/policies/hardware-profile.yaml",
             opcoes=["no_gpu", "gpu_8_16gb", "gpu_24gb_plus"], default="no_gpu",
             bloco="3.4 Modelos, assinaturas e hardware"),
    Pergunta("local_models", "Modelos locais instalados ou a instalar",
             "order/policies/model-registry.yaml", lista=True, default="",
             bloco="3.4 Modelos, assinaturas e hardware"),

    # ---- §3.5 cotas e proatividade ----
    Pergunta("max_actions", "Máximo de ações autônomas por dia",
             "order/policies/quotas.yaml", default=50,
             bloco="3.5 Cotas e proatividade"),
    Pergunta("max_notifications", "Máximo de notificações por dia",
             "order/policies/quotas.yaml", default=20,
             bloco="3.5 Cotas e proatividade"),
    Pergunta("on_exceeded", "Comportamento ao exceder a cota",
             "order/policies/quotas.yaml.on_exceeded",
             opcoes=["degrade_to_propose", "pause"], default="degrade_to_propose",
             bloco="3.5 Cotas e proatividade"),
    Pergunta("scan_hours", "Frequência do `order trigger scan` na nuvem (horas)",
             "order/automations/AUT-scan.md", default=4,
             bloco="3.5 Cotas e proatividade"),
    Pergunta("automations", "Automações iniciais (todas nascem em `shadow`)",
             "order/automations/AUT-*.md", lista=True, default="briefing-diario",
             bloco="3.5 Cotas e proatividade"),
]


def _normalizar(p: Pergunta, bruto: str):
    bruto = (bruto or "").strip()
    if not bruto:
        if p.default is None:
            raise ErroChaos(f"`{p.chave}` é obrigatória e não tem default (§3)", "schema")
        return p.default, "default aceito"
    if p.bool_:
        return bruto.lower() in ("s", "sim", "y", "yes", "true", "1"), "digitado"
    if p.lista:
        return [x.strip() for x in bruto.split(",") if x.strip()], "digitado"
    if isinstance(p.default, int):
        return int(bruto), "digitado"
    if p.opcoes and bruto not in p.opcoes:
        raise ErroChaos(f"`{bruto}` não é opção válida para `{p.chave}` "
                        f"({' | '.join(p.opcoes)})", "schema")
    return bruto, "digitado"


def coletar(respostas_arquivo: Path | None, interativo: bool) -> dict:
    prefixadas = yamlio.ler_yaml(respostas_arquivo) if respostas_arquivo else None
    prefixadas = prefixadas or {}
    coletadas: dict[str, dict] = {}

    bloco_atual = ""
    for p in PERGUNTAS:
        if p.bloco != bloco_atual and interativo:
            bloco_atual = p.bloco
            print(f"\n— {bloco_atual} —", file=sys.stderr)
        if p.chave in prefixadas:
            valor = prefixadas[p.chave]
            if p.lista and isinstance(valor, str):
                valor = [x.strip() for x in valor.split(",") if x.strip()]
            origem = "arquivo de respostas"
        elif interativo:
            try:
                bruto = input(f"  {p.formatar()}\n  > ")
            except EOFError:
                bruto = ""
            valor, origem = _normalizar(p, bruto)
        else:
            if p.default is None:
                raise ErroChaos(
                    f"§3: `{p.chave}` não tem default e não veio no arquivo de "
                    f"respostas — nenhuma resposta pode ser assumida", "schema")
            valor, origem = p.default, "default aceito"
            if p.lista and isinstance(valor, str):
                valor = [x.strip() for x in valor.split(",") if x.strip()]
        coletadas[p.chave] = {"valor": valor, "origem": origem,
                              "destino": p.destino, "pergunta": p.texto,
                              "bloco": p.bloco}
    return coletadas


def materializar(repo: Path, r: dict, ator: str) -> list[str]:
    """Grava cada resposta no arquivo que a sustenta. Devolve o que tocou."""
    def v(chave):
        return r[chave]["valor"]

    tocados = []
    classe = yamlio.ler_yaml(repo / "metadata" / "repo.yaml").get("privacy_class", "demo")

    cfg = yamlio.ler_yaml(repo / "metadata" / "repo.yaml") or {}
    cfg.update({"remote": v("remote"), "default_privacy": v("default_privacy"),
                "views_builder": v("views_builder"),
                "allowed_channels": v("allowed_channels"),
                "episodic": bool(v("episodic"))})
    yamlio.escrever_yaml(repo / "metadata" / "repo.yaml", cfg)
    tocados.append("metadata/repo.yaml")

    yamlio.escrever_yaml(repo / "metadata" / "registries" / "privacy-classes.yaml",
                         {"classes": v("privacy_classes")})
    tocados.append("metadata/registries/privacy-classes.yaml")

    yamlio.escrever_yaml(repo / "metadata" / "registries" / "executors.yaml", {
        "executors": [
            {"id": v("owner"), "kind": "human", "git_identity": v("human_email"),
             "signing_principal": v("human_signing_principal") or v("human_email"),
             "allowed_actors": [v("owner")]},
            {"id": "executor:local_worker", "kind": "executor",
             "git_identity": v("worker_email"),
             "signing_principal": v("worker_signing_principal") or v("worker_email"),
             "allowed_actors": ["executor:local_worker", "agent:*"]},
            {"id": "cloud:claude-code", "kind": "executor",
             "git_identity": v("cloud_email"),
             "allowed_actors": ["cloud:claude-code", "agent:*"]},
        ]})
    tocados.append("metadata/registries/executors.yaml")

    fontes = [{"id": s, "enabled": True, "cost_model": "subscription"}
              for s in v("budget_sources")]
    if v("enable_pay_per_use"):
        fontes.append({"id": "pay-per-use", "enabled": True,
                       "cost_model": "pay_per_use"})
    fontes.append({"id": "local", "enabled": True, "cost_model": "free"})
    yamlio.escrever_yaml(repo / "order" / "policies" / "quotas.yaml", {
        "global": {"max_autonomous_actions_per_day": int(v("max_actions")),
                   "max_notifications_per_day": int(v("max_notifications")),
                   "on_exceeded": v("on_exceeded"),
                   "quiet_hours": v("quiet_hours"), "timezone": v("timezone")},
        "budget_sources": fontes})
    tocados.append("order/policies/quotas.yaml")

    yamlio.escrever_yaml(repo / "order" / "policies" / "hardware-profile.yaml",
                         {"gpu_class": v("gpu_class")})
    tocados.append("order/policies/hardware-profile.yaml")

    worker = yamlio.ler_yaml(repo / "order" / "policies" / "worker.yaml") or {}
    worker["host_os"] = v("host_os")
    yamlio.escrever_yaml(repo / "order" / "policies" / "worker.yaml", worker)
    tocados.append("order/policies/worker.yaml")

    # modelos locais declarados entram como locality: local, cost_model: free
    reg = yamlio.ler_yaml(repo / "order" / "policies" / "model-registry.yaml") or {}
    modelos = [m for m in reg.get("models", []) if m.get("locality") != "local"]
    for i, nome in enumerate(v("local_models")):
        modelos.append({"id": nome, "locality": "local",
                        "tier": "mid" if i == 0 else "low",
                        "cost_model": "free", "budget_source": "local"})
    if not any(m.get("locality") == "local" for m in modelos):
        modelos.append({"id": "tier-low-local", "locality": "local", "tier": "low",
                        "cost_model": "free", "budget_source": "local"})
    for fonte in v("budget_sources"):
        for tier in ("high", "mid"):
            modelos.append({"id": f"{fonte}-{tier}", "locality": "remote",
                            "tier": tier, "cost_model": "subscription",
                            "budget_source": fonte})
    yamlio.escrever_yaml(repo / "order" / "policies" / "model-registry.yaml",
                         {"models": modelos})
    tocados.append("order/policies/model-registry.yaml")

    # equipe: Assistente obrigatório + áreas + funcionais escolhidos
    agentes = [{"id": "agent.fn.assistant", "kind": "assistant",
                "name": v("assistant_name"), "autonomy_ceiling": "A2",
                "model_policy": "assistant",
                "capabilities": ["triage", "schedule", "notify", "delegate", "brief"]}]
    catalogo = {a["id"].split(".")[-1]: a for a in layout.REGISTRY_AGENTES["agents"]
                if a["kind"] == "functional"}
    for nome in v("functionals"):
        if nome in catalogo:
            agentes.append(catalogo[nome])
    for slug in v("areas"):
        agentes.append({"id": f"agent.area.{slug}", "kind": "area",
                        "name": f"Área {slug}", "area": slug,
                        "autonomy_ceiling": "A2", "model_policy": "area-owner",
                        "capabilities": ["maintain_state", "prioritize", "delegate"]})
    yamlio.escrever_yaml(repo / "order" / "agents" / "registry.yaml", {"agents": agentes})
    tocados.append("order/agents/registry.yaml")

    for slug in v("areas"):
        if not areas.caminho(repo, slug).exists():
            areas.criar(repo, slug, slug, ator)
            tocados.append(f"areas/{slug}/state.md")

    # automações: todas nascem em shadow, inclusive o scan
    for nome in list(v("automations")) + [f"scan-{v('scan_hours')}h"]:
        aut = ids.novo_id("automation")
        yamlio.escrever(repo / "order" / "automations" / f"{aut}.md", {
            "id": aut, "type": "automation", "schema_version": "2.5",
            "title": nome, "name": nome, "status": "registered",
            "trigger": "time", "mode": "shadow", "max_risk": "A1",
            "enabled": False, "quota": 0,
            "interval_hours": int(v("scan_hours")) if nome.startswith("scan-") else 24,
            "created_at": ids.agora(), "updated_at": ids.agora(),
            "created_by": ator, "updated_by": ator, "authority": "active",
            "valid_from": "", "valid_to": "", "relations": [], "conflicts": [],
            "provenance": {"origin": "human", "source_refs": [],
                           "confidence": "unknown", "epistemic_status": "unknown",
                           "verified_at": "", "verified_by": ""},
        }, "")
        tocados.append(f"order/automations/{aut}.md")

    if v("episodic"):
        (repo / ".ai-memory.toml").write_text(
            "# Marcador de escopo da camada episódica (CHAOS §4.2).\n"
            "# PROTECTED PATH: declara a fronteira de privacidade da captura.\n"
            f'project = "chaos-{classe}"\n\n[capture]\nignore_paths = [\n'
            + "".join(f'  "{c}",\n' for c in v("capture_ignore"))
            + "]\n", encoding="utf-8", newline="\n")
        tocados.append(".ai-memory.toml")

    layout.escrever_agents_md(repo, classe, v("owner"))
    tocados += ["AGENTS.md", "CLAUDE.md"]
    return tocados


def relatorio(repo: Path, r: dict, tocados: list[str]) -> Path:
    linhas = ["# Relatório de Onboarding",
              f"\n**Data:** {ids.agora()[:10]}  ",
              f"**Repositório:** {repo.name}\n",
              "> A Fase 0 só começa depois que você confirmar este relatório.",
              "> Nenhuma resposta abaixo foi assumida de histórico, perfil ou outra",
              "> implantação: ou foi digitada agora, ou é um default que foi mostrado",
              "> e aceito — e a coluna *origem* diz qual dos dois.\n"]
    bloco = ""
    for chave, d in r.items():
        if d["bloco"] != bloco:
            bloco = d["bloco"]
            linhas += [f"\n## {bloco}\n",
                       "| Pergunta | Resposta | Origem | Materializada em |",
                       "|---|---|---|---|"]
        valor = d["valor"]
        if isinstance(valor, list):
            valor = ", ".join(str(x) for x in valor) or "(vazio)"
        linhas.append(f"| {d['pergunta']} | `{valor}` | {d['origem']} | `{d['destino']}` |")

    linhas += ["\n## Arquivos escritos\n"]
    linhas += [f"- `{t}`" for t in sorted(set(tocados))]
    linhas += ["\n## Próximo passo\n",
               "Confirme este relatório e rode `chaos validate` e `chaos health`. "
               "A Fase 0 começa com a suíte de aceitação como portão.\n",
               "\n> **Pendências que este Onboarding não resolve:** o spike de "
               "identidade (Tutorial Parte 3) e a decisão sobre o repositório "
               "sensível continuam bloqueando o que depende delas.\n"]

    destino = repo / "reports" / f"onboarding-{ids.agora()[:10]}.md"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8", newline="\n")
    return destino
