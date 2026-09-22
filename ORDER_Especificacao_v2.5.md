# ORDER — Orchestrated Runtime for Distributed Execution & Reasoning — Especificação Completa v2.5

**Status:** Especificação de referência para implementação
**Versão:** 2.5 (supersede v2.4)
**Data:** 2026-09-20
**Documentos irmãos:** CHAOS v2.5 · Implementação Claude-Nativa v1.3

> Esta especificação define semântica e contratos. A implementação pode usar qualquer conjunto de frameworks, linguagens e infraestrutura. A Implementação Claude-Nativa v1 é o binding de referência (Perfil A); o Perfil B (auto-hospedado) preserva os mesmos contratos.

---

## 0.0 Changelog v2.4 → v2.5 (divergência de toolchain)

| # | Mudança | Motivo |
|---|---|---|
| 1 | §31: **divergência de toolchain** (`chaos health` = `drift`, CHAOS §21.1) entra na lista de falhas tratadas — rebaixa automações a `propose`, gera EVT e aparece no briefing; `broken` para tudo que é autônomo | §39 promete que cada RUN registra as versões de ferramenta usadas, e isso era verdade só por acidente: nada verificava que o binário em execução era o vendorizado. Um RUN registrando versão que não agiu é pior que não registrar |
| 2 | §33: `order status` reporta o estado de saúde do toolchain | Estado que rebaixa autonomia e não aparece no painel é estado que o usuário descobre pelo sintoma |
| 3 | AT-29 novo | Regra normativa sem teste |
| 4 | §21.3: `minimum_tier` é **piso**, e o roteador escolhe o **menor tier que o satisfaz** | Descoberto ao implementar: a regra dizia "aplicar `tier_preference`" sem dizer em que direção. Preferir o maior gastaria capacidade cara em trabalho barato — uma policy `classify` com piso `low` servida por `mid` é desperdício silencioso |
| 6 | §38: `workflow`, `notify` e `model call` declarados | §3 diz que o ORDER **contém** Workflow Engine, Notification Adapter e Model Gateway, e §38 não dava comando a nenhum dos três. É o defeito das oito operações fantasma da 9ª rodada pelo avesso: motor sem superfície é motor que ninguém invoca nem inspeciona |
| 5 | §10.1: o HND referencia a **tarefa de origem**; a subtarefa criada vai em `context_refs` | O receptor reconstrói contexto a partir do HND, e o que ancora a reconstrução é a tarefa que motivou a delegação |

**Por que rebaixar em vez de parar.** `drift` não corrompe nada: o repositório continua legível e o humano continua trabalhando. Parar tudo seria punir o usuário por um descompasso de versão, e o desfecho previsível é ele contornar a verificação. Rebaixar a `propose` usa o mecanismo que já existe para cota excedida (§20) e tem a propriedade certa: o sistema continua útil, mas nada acontece sozinho enquanto a reprodutibilidade não estiver restabelecida.

## 0.0 Changelog v2.3 → v2.4 (adoção da camada episódica)

| # | Mudança | Motivo |
|---|---|---|
| 1 | §24 reescrita: a camada episódica (CHAOS §4.2) passa de NOT REQUIRED a **RECOMMENDED no Perfil A**, implementada por `ai-memory`, e o modelo de memória passa a ter três camadas nomeadas | A regra "memória de runtime é cache, nunca fonte" continuava correta e sem ocupante decente: sobrava a memória do Claude Code, que morre com a sessão e não é inspecionável. O ocupante muda; a regra, não |
| 2 | §14: `tool.episodic.read` (A0) e `tool.chaos.promote` declarados no Tool Registry | Ler a camada episódica e promover dela para o canônico são ações que o `guard` precisa reconhecer; ação não declarada é ação sem classe de risco |
| 3 | §17: promoção é **escrita comum** e recebe a classe da entidade que cria; ler episódico nunca eleva teto | Sem isto, "promover" viraria o caminho barato para escrever o que a escrita direta não permitiria |
| 4 | §23: o Context Builder entrega `episodic` em bloco separado, jamais elegível como evidência | Fundir observação de sessão com fato canônico é a falha que a separação de stores existe para evitar; se o contrato de contexto não a mantém, o store separado não adianta |
| 5 | §40: degradação declarada para a ausência da camada episódica | Componente novo sem linha de degradação vira dependência estrutural por omissão |
| 6 | §41: linhas de memória episódica, índice derivado e handoff entre CLIs | — |
| 7 | AT-27 e AT-28 novos; anti-padrões e Golden Rules ampliados | Regras novas sem teste |

## 0.1 Changelog v2.2 → v2.3 (análise adversarial — rodadas 2 a 9)

| # | Mudança | Motivo |
|---|---|---|
| 1 | Task Queue: claim nunca é rebaseado; push rejeitado → fetch, descartar claim, reavaliar; commits sempre na branch principal | R1 |
| 2 | Aprovação A4 exclusivamente fora do caminho do modelo (commit humano sem trailer) — E1-a | R3 |
| 3 | Quota Engine: cada `budget_source` declara a unidade que consegue medir (`runs`, `sessions`, `tokens`, `usd`) | R4 |
| 4 | Trailers `Actor:`/`Surface:` obrigatórios em commits de agente | R3 |
| 5 | Runs em `shadow` aparecem no briefing com proposta de promoção | menor |
| 6 | SES só como arquivo se houve RUN/HND (E4-a) | menor |
| 7 | Kill-switch: `guard` faz `fetch` de `PAUSED` no máximo a cada N minutos (default 5) antes de ações A1+ | menor |
| 8 | Bash de agentes restrito a allowlist de comandos aplicada por hook | R7 |
| 9 | AT-18 a AT-20 novos | — |
| 10 | (3ª rodada) `git commit`/`git push` removidos da allowlist de agentes: commits só via `chaos commit`/`chaos sync`, que injetam trailers antes do commit | R10 — trailer não pode ser injetado depois do commit |
| 11 | (3ª rodada) Protected paths incluem o próprio mecanismo de enforcement (`.claude/**`, `tools/**`, `.github/**`) | R9 |
| 12 | (3ª rodada) Worker local executa o mesmo `guard` em processo, sobre o mesmo Tool Registry | R15 |
| 13 | (3ª rodada) Risco residual documentado: aprovação A3 por CLI em sessão interativa induzida por injeção de prompt (§18) | R12 |
| 14 | (3ª rodada) AT-21, AT-22 novos | — |
| 15 | (F1-c) Política `a3_mode` em `order/policies/approval.yaml`; valor inicial `out_of_band` (A3 aprovada como A4); modo `cli` e `code` só por decisão do usuário na Fase 4 da Implementação, com métricas | F1 |
| 16 | (5ª rodada) §11 `local_only` sem worker disponível vira `blocked(no_local_worker)` em vez de esperar indefinidamente; §10.2 delegação herda o risco da subtarefa, não só o ato de delegar | Deadlock e escapatória de teto de autonomia |
| 17 | (6ª rodada) §8.3 registro do Assistente; §21.2 policy `assistant` — sem ela `order agent sync` não resolveria o `model:` de um agente obrigatório | Assistente exigido pelo §25 sem policy correspondente |
| 18 | (6ª rodada — **correção**) Removida a regra "worker é o único `events_appender`": o ledger é multi-escritor pelo adapter, com `merge=union`; a exclusividade do repositório é a do `views_builder` | Contradizia CHAOS §17.1 e deixava sessões na nuvem sem auditoria |
| 19 | (7ª rodada) §14 `by_field` no Tool Registry e §17 no cálculo: rebaixar `privacy`, `privacy_class` ou `execution` é **A4**; elevar continua A1 | Pelo cálculo por caminho o rebaixamento dava A1, abrindo caminho de escalação a partir de uma fila bloqueada |
| 20 | (7ª rodada) AT-08 exige checkpoint completo para retomada; AT-23 e AT-24 novos | Regras sem teste |
| 21 | (8ª rodada) §11: removida a combinação `local_only` + `execution: any`, que o schema do CHAOS proíbe (§8.3); worker indisponível vira `blocked(no_local_worker)` por `no_worker_timeout_h`, e o bloqueio é limpo quando um worker reclama | A regra da 6ª rodada descrevia um estado que o validador rejeita |
| 22 | (8ª rodada) AT-25 novo; §45 deixa de fixar faixa numérica de ATs | Regra sem teste; portão de conformidade que se quebra ao crescer a suíte |
| 23 | (9ª rodada) §38 passa a ser a CLI completa e única: acrescenta `run checkpoint\|act`, `risk eval`, `guard`, `delegate`, `session`, `trigger`, `quota status`, `report`, `agent sync`; kill-switch fica no `chaos`; `run claim` e `task resume` eliminados | ORDER §38 e Implementação §11 declaravam 22 comandos cada, só 10 em comum; e 8 operações exigidas pelos AT — incluindo `run checkpoint`, de que todo o contrato de retomada depende — não existiam em nenhuma lista |
| 24 | (9ª rodada) §16 enumera os casos mínimos de negação do guard | AT-22 exigia "a mesma suíte de casos" que a spec não definia |
| 25 | (9ª rodada) AT-12, AT-13, AT-14 ganham escopo complementar ao do CHAOS; AT-13 dividido (determinístico no AT, comportamento em eval); AT-16 vira ausência de acoplamento; AT-18 passa a cobrir o perdedor da corrida | Três AT duplicavam os do CHAOS e já haviam divergido; AT-16 era insatisfazível sem duas implementações; AT-18 era AT-07 repetido |
| 26 | (10ª rodada) §38 ganha `automation sync`, usado pela Implementação §5.2 e não declarado; `agents sync` renomeado para `agent sync` em todas as referências | Comando fantasma e seis referências órfãs deixadas pela reconciliação da 9ª rodada |
| 27 | (11ª rodada) §14: `order/automations/**`, `order/agents/**` e `AGENTS.md` ganham entrada `by_resource` A4; §16 alinha a lista de protected paths ao critério de CHAOS §4.1 | AUT é entidade CHAOS, logo alcançável por `chaos automation update`: um agente A2 promovia a própria automação a `auto` e elevava o teto dela — cada passo legítimo, risco calculado A1 |
| 28 | (11ª rodada) AT-26 novo; AT-08, AT-17 e AT-22 corrigidos — AT-22 passa a exercitar o loop do worker em vez de comparar duas invocações de `order guard` | Três testes passavam vacuamente: uma implementação cujo worker não chamasse o guard ficava verde |
| 29 | (12ª rodada) §16: casos mínimos do guard reorganizados **por família de comando, não por plataforma**, com colunas POSIX e Windows (`powershell -Command`, `-EncodedCommand`, `cmd /c`, `Out-File`, `Set-Content`, `Add-Content`) e família nova `shell aninhado`; declarado o critério (*escreve arquivo ou executa código sem passar pelo CLI*) | A lista era inteiramente POSIX: no Windows um agente a contornava inteira com uma linha de PowerShell. E negar por plataforma hospedeira abriria a outra metade numa máquina com Git Bash ou pwsh instalado |

---

## 1. Propósito

ORDER transforma intenção em execução controlada sobre o CHAOS. Responsabilidades: registrar e executar agentes; orquestrar workflows; selecionar modelos; recuperar contexto; controlar ferramentas; aplicar permissões; calcular risco; solicitar aprovação; executar automações por gatilho; manter sessões, tasks, runs; integrar canais; observar e auditar; recuperar falhas; **respeitar o kill-switch e as cotas**.

ORDER **MUST** ser substituível sem invalidar o CHAOS. Todo estado de que o ORDER precisa para retomar trabalho **MUST** estar persistido em `order/` do CHAOS.

## 2. Princípios

vendor-neutral · CHAOS-first · policy-first · human-in-the-loop por risco · reversível-first · evidence-first · determinismo para regras críticas · least privilege · observabilidade · degradação graciosa · componentes substituíveis · complexidade proporcional ao valor · **interrompível a qualquer momento** · **autonomia conquistada, não concedida** (escada de maturidade).

## 3. Limites

**Contém:** Control Plane, Orchestrator, Agent Registry, Delegation Protocol, Task Queue, Trigger Engine, Workflow Engine, Model Registry/Policy/Router/Gateway, Tool Registry, Permission Engine, Risk Engine, Approval Engine, Quota Engine, Kill-switch, Context Builder, Notification Adapter, Audit Adapter, Observability, API e CLI.

**Não contém:** source of truth do conhecimento; código-fonte obrigatório; LLM obrigatório; banco vetorial obrigatório; Obsidian obrigatório; banco de dados obrigatório.

## 4. Topologia e runtime híbrido

```text
                 ┌──────────────────────────────┐
                 │  chaos-<classe-1> / chaos-<classe-n>   │  (Git remoto)
                 │  order/  = fila + runs + apv   │
                 └───────┬──────────────┬─────────┘
                         │              │
        ┌────────────────┴───┐    ┌─────┴──────────────────┐
        │ RUNTIME NUVEM      │    │ WORKER LOCAL           │
        │ (primário)         │    │ (secundário)           │
        │ sessões Claude Code│    │ Python + Model Gateway │
        │ tarefas agendadas  │    │ (LiteLLM → Ollama +    │
        │ Claude Mobile/Web  │    │  remotos declarados) │
        │ execution: cloud|any    │ execution: local|any   │
        │ privacy: cloud_allowed  │ privacy: qualquer      │
        └────────────────────┘    └────────────────────────┘
```

Ao lado dos repositórios CHAOS há o **repositório episódico** por classe de privacidade (CHAOS §4.2), escrito pela camada episódica e lido por ambos os runtimes. Ele não é source of truth, não recebe entidade canônica e não participa da fila: é continuidade, não estado operacional.

Ambos os runtimes obedecem ao mesmo Task Queue Protocol (§11), leem o mesmo `PAUSED`, escrevem os mesmos RUN/EVT e passam pelo mesmo `guard` (na nuvem como hook; no worker, em processo, no loop de chamada de ferramentas, sobre o mesmo Tool Registry). Nenhum dos dois é source of truth. O worker (`executor:local_worker`) é também o **executor de retomada** (pode assumir qualquer RUN com lease expirado cuja tarefa tenha `execution: any`) e o único caminho para `privacy: local_only` e para modelos locais. Ambos acrescentam EVT ao mesmo ledger pelo adapter (§16).

## 5. Arquitetura

```text
User / Triggers
      │
      ▼
Control Plane ── Kill-switch ── Quota Engine
      │
      ▼
Orchestrator ── Task Queue ── Delegation
      │
   ┌──┴────────────┬──────────────┐
   ▼               ▼              ▼
Area Agents   Functional Agents  Tools (Tool Registry)
   └──────────────┬───────────────┘
                  ▼
           Context Builder ──► CHAOS
                  ▼
   Risk Engine → Permission Engine → Approval Engine
                  ▼
   Model Policy → Model Router (provedor, tier) → Model Gateway
                  ▼
           Run Ledger + Audit + Notification
```

## 6. Control Plane

Governança operacional: registro de agentes; sessões; tasks/runs; scheduling; permissões; projetos; execução; status; API/CLI; health. **Antes de qualquer despacho, o Control Plane MUST verificar `order/PAUSED` e as cotas (§20).**

## 7. Orchestrator

Decomposição; planejamento; seleção de agente por área e capability; sequência; branching; loops; retries; checkpoints; handoffs; aprovação; recovery.

Entrada: `task_id, intent, context, constraints`. Saída: `status: completed|failed|blocked|awaiting_approval|checkpointed`, `result`, `artifacts`, `decisions`, `run_id`, `audit_refs`.

## 8. Equipe de agentes — modelo em matriz

### 8.1 Dois eixos

**Agentes de área (donos):** um por área do usuário (CHAOS `areas/`). Cada um detém o Área State, conhece os projetos e rotinas da área, recebe gatilhos da área, decide o que fazer e **delega** a especialistas funcionais. É o único agente que pode alterar o Área State e priorizar tarefas da área.

**Agentes funcionais (especialistas compartilhados):** executam capacidades sem dono de domínio — Researcher, Planner, Reviewer, Coder, Librarian, Decision Analyst. Não têm área; recebem trabalho por delegação e devolvem por handoff.

**Assistente Pessoal (chefe de gabinete):** único agente transversal. Interface primária com o usuário, triagem do inbox, agenda, briefing diário/semanal, follow-ups e roteamento para o agente de área correto. Não executa trabalho de área; encaminha.

### 8.2 Definição das áreas

Esta especificação **não fixa áreas**. As áreas, seus nomes e o repositório (classe de privacidade) de cada uma são obtidos do usuário na implantação pelo Onboarding Protocol (Implementação Claude-Nativa §3) e registradas em `areas/<slug>/` e em `order/agents/registry.yaml`. Um agente de área pertence a exatamente um repositório. Novas áreas podem ser criadas a qualquer momento por ação humana (A1 no CHAOS; criar o agente correspondente é A4 porque altera o registry, um protected path).

### 8.3 Agent Registry

```yaml
id: agent.area.<slug>
kind: area | functional | assistant
name: "Dono — <Nome da área>"
version: "2.2"
repo_id: chaos-<classe>
area_id: AREA-<slug>
capabilities: [area_state.write, task.write, task.prioritize, delegate]
tools: [chaos.read, chaos.write, chaos.search, notify.user]
model_policy: area-owner
autonomy_ceiling: A2          # teto absoluto de risco que este agente pode executar sem humano
delegates_to: [agent.fn.researcher, agent.fn.planner, agent.fn.reviewer, agent.fn.coder]
input_schema: {}
output_schema: {}
```

```yaml
id: agent.fn.researcher
kind: functional
capabilities: [research, source.collect, synthesis, citation]
tools: [chaos.read, chaos.search, web.search, web.fetch]
model_policy: reasoning
autonomy_ceiling: A1          # só escreve rascunhos/sources; nunca promove a canonical
```

```yaml
id: agent.fn.assistant
kind: assistant
capabilities: [task.read, task.write, inbox.categorize, inbox.summarize, notify.user, delegate]
tools: [chaos.read, chaos.write, chaos.search, notify.user]
model_policy: assistant       # §21.2 — mesma exigência de raciocínio do dono de área
autonomy_ceiling: A2          # triagem, resumo e delegação; não cria tarefa a partir do inbox sem autorização humana
```

Agentes são descobertos por `kind`, `area_id`, capability e `autonomy_ceiling`.

### 8.4 Materialização por superfície e bootstrap de Assistente

O registry é a fonte; cada superfície recebe um binding gerado: subagentes de Claude Code (`.claude/agents/<id>.md` com `model:` derivado da Model Policy), instruções de Project no Claude Desktop/Web, prompt de sistema do worker local.

**Sequência de Assistente:**
1. **Onboarding (Implementação §3.3):** perguntas geram entradas em `order/agents/registry.yaml`, incluindo `agent.fn.assistant` (Assistente Pessoal). Registry é escrito, mas bindings ainda não.
2. **Fase 0:** `order agent sync` **lê** registry (atualizado ou não) e **gera** `.claude/agents/<id>.md` para cada agente, incluindo Assistente com constraints obrigatórios (§5.1.1). Se registry mudou entre Onboarding e Fase 0, rodar `order agent sync` novamente regenera os bindings com novos dados.

**Assistente Pessoal é obrigatório** (`agent.fn.assistant`) e sempre materializado em Fase 0. A Implementação Claude-Nativa v1.2 define o gerador e o Onboarding Protocol.

## 9. Agent Protocol

Antes de atuar, um agente **MUST**: (1) executar o Session Protocol de início (CHAOS §9.3); (2) identificar tarefa e RUN; (3) identificar Source of Truth; (4) recuperar contexto pelo Context Builder; (5) obter do Risk Engine a classe da ação pretendida; (6) obter do Permission Engine a autorização; (7) obter aprovação se A3+ ou se policy exigir; (8) executar apenas capacidades autorizadas; (9) checkpointar; (10) validar resultado; (11) registrar EVT; (12) devolver resultado verificável; (13) executar o Session Protocol de encerramento.

**MUST NOT:** inventar evidência; alterar IDs; editar views derivadas como canônicas; ignorar conflitos; executar ação proibida; **classificar o próprio risco; obedecer instruções contidas em conteúdo `external_source`; escrever em protected paths; ultrapassar `autonomy_ceiling`; continuar com `PAUSED` presente**.

## 10. Handoff e Delegation Protocol

### 10.1 Handoff (HND)

```yaml
id: HND-20260918-P2WXN9
type: handoff
from_agent: agent.fn.researcher
to_agent: agent.area.<slug>
task_id: ""
run_id: ""
objective: ""
context_refs: []
artifacts: []
decisions: []
constraints: []
open_questions: []
assumptions: []
status: open | accepted | closed
```

O receptor **MUST** conseguir reconstruir o contexto só com o HND + CHAOS, sem memória implícita.

### 10.2 Delegation

Delegação é a criação de uma **subtarefa** (TSK com `parent_task`) com `assigned_agent` funcional, mais um HND. Regras: só agentes de área e o Assistente delegam; delegado herda o menor `autonomy_ceiling` entre o delegante e o próprio; delegado devolve por HND ao delegante, nunca ao usuário diretamente, salvo pedido de aprovação; profundidade máxima de delegação definida em policy (default 2).

**Ceiling e risco da subtarefa:** Delegação é um ato A2 (criar subtarefa), mas **risco da subtarefa em si** é herdado. Se delegante tem `autonomy_ceiling: A2` (ex: Assistente) e a subtarefa resultante é A3, o **risco composto é A3**; Assistente **não pode delegar tarefas A3** sem que agente destinatário tenha `autonomy_ceiling: A3+`. Validador (`chaos validate`) rejeita delegação que viola isto com mensagem clara: "Delegação de RUN-X para agent Y não permitida: risco composto A3 > ceiling A2."

## 11. Task Queue Protocol

Uma tarefa está **disponível** quando `status ∈ {ready, in_progress}`, `has_conflict: false`, e (`claimed_by` vazio **ou** `lease_until < agora`).

1. **Claim:** executor faz `fetch` e confirma que a tarefa continua disponível; escreve `claimed_by`, `lease_until = agora + lease` (default 30 min), cria RUN `claimed`, comita **na branch principal** e faz push **sem rebase automático**. Push rejeitado (non-fast-forward) significa que outro executor venceu: o executor **MUST** descartar o commit de claim (`reset --hard` para o remoto), nunca tentar rebase/merge do claim, e reavaliar a fila. Um claim em branch não existe para a fila.
2. **Heartbeat:** renovar `lease_until` a cada checkpoint ou a cada metade do lease.
3. **Checkpoint:** atualizar `RUN.checkpoint` e comitar artefatos parciais.
4. **Release:** ao concluir, `claimed_by` vazio, RUN `completed`, tarefa `review` ou `done`.
5. **Abandon:** lease expirado → qualquer executor elegível pode marcar RUN anterior `abandoned` e reclamar. O novo RUN referencia o anterior em `resumes_run`.

Elegibilidade: `execution: cloud` só runtime nuvem; `local` só worker local; `any` ambos. `privacy: local_only` implica `execution: local` por invariante de schema (CHAOS §8.3) — não existe tarefa `local_only` elegível à nuvem, e o validador rejeita a combinação.

**Worker indisponível.** Uma tarefa `execution: local` sem worker disponível fica na fila indefinidamente, o que é correto mas invisível. Decorrido `no_worker_timeout_h` (default 24, em `order/policies/worker.yaml`) desde que a tarefa ficou pronta sem nenhum claim, ela recebe `blocked(no_local_worker)` (§8.3 do CHAOS) e aparece no briefing. Nada escala sozinho: as saídas são ligar o worker, cancelar a tarefa, ou rebaixar a privacidade — esta última A4, porque muda `privacy` **e** `execution` juntos (§14), e nenhum agente a aprova em sessão.

O bloqueio é sinalização, não estado terminal: assim que um worker elegível aparece e reclama a tarefa, `status` volta a `in_progress` e `blocked_reason` é limpo.

## 12. Workflow Engine

Suporta sequência, paralelismo, condições, loops, retry, timeout, checkpoint, approval, compensação, recovery. Fluxo: `Trigger → Evaluate → Plan → Run → Validate → Decision → Action → Notify → Audit`. Definições em `workflows/*.yaml`, interpretadas por um runner determinístico; LangGraph é binding alternativo do Perfil B.

## 13. Runtimes

**Perfil A:** sessões Claude Code (nuvem e local), tarefas agendadas do Claude, worker local Python. **Perfil B:** OpenClaw (runtime pessoal/canais), OpenHands (coding), LangGraph (workflows). Nenhum é Control Plane, memória canônica ou Model Gateway por definição.

## 14. Tool Registry

Toda ferramenta declara capacidade, I/O, **classe de risco por ação e recurso**, permissões, efeitos, idempotência e timeout.

```yaml
id: tool.chaos.write
input_schema: {}
output_schema: {}
risk:
  default: A1
  by_resource:
    "metadata/policies/**": A4
    "order/policies/**": A4
    "order/agents/**": A4
    "order/automations/**": A4   # maturidade, teto e cota do que roda sozinho
    "AGENTS.md": A4              # bootstrap canônico de toda sessão futura
    "metadata/schemas/**": A4    # decidem se uma policy é válida
    "workflows/**": A4           # o corpo do que uma automação executa
    "order/PAUSED": A4
    "audit/**": A4            # só append via adapter próprio
    "indexes/**": A1
  by_field:                   # o campo escrito, não só o caminho
    "privacy: local_only → cloud_allowed": A4   # divulgação irreversível
    "privacy_class (qualquer mudança)": A4
    "execution: local → cloud|any": A4          # idem: decide onde o conteúdo é processado
permissions: [chaos.write]
effects: { external: false }
idempotent: true
timeout_seconds: 30
```

**Rebaixamento de privacidade é A4**, sempre, em qualquer superfície. O cálculo por caminho não bastaria: o arquivo é uma entidade comum e daria `default: A1`. A razão é que A1 significa "reversível por Git", e Git reverte o **arquivo**, não o **efeito** — uma vez que o conteúdo foi enviado a um provedor, reverter o commit não o traz de volta. Elevar a privacidade (`cloud_allowed → local_only`) permanece A1: restringir não divulga nada.

Isto fecha um caminho de escalação que o resto do modelo não cobriria: uma tarefa bloqueada por falta de capacidade local (Implementação §6.3) é exatamente a situação em que "só mude a privacidade dela" parece a saída óbvia, inclusive para um agente sob injeção de prompt. Com A4, a saída exige commit humano fora do caminho do modelo, como qualquer alteração de policy.

```yaml
id: tool.episodic.read
risk:
  default: A0                 # leitura; nunca eleva teto de nada
permissions: [episodic.read]
effects: { external: false }
idempotent: true
```

```yaml
id: tool.chaos.promote        # CHAOS §21 — episódico → canônico
risk:
  default: A1                 # é escrita comum; herda by_resource/by_field de tool.chaos.write
permissions: [chaos.write]
effects: { external: false }
idempotent: false
```

**Promover não é um privilégio.** `tool.chaos.promote` recebe exatamente a classe de risco que a escrita equivalente receberia pelo recurso e pelo campo — se o alvo for protected path, é A4; se rebaixar privacidade, é A4. Fosse a promoção uma classe própria e mais branda, ela seria o caminho barato para escrever aquilo que a escrita direta recusa, e a camada episódica — que ninguém classifica na entrada — viraria a antessala da escalação.

```yaml
id: tool.notify.send
risk:
  default: A3
  by_resource:
    "channel:self": A2        # notificar o próprio usuário
    "channel:*": A3
```

## 15. MCP e interoperabilidade

MCP é protocolo preferencial **quando disponível**; não é dependência estrutural. No Perfil A com restrição corporativa de conectores, integrações usam CLI, API, biblioteca e adapters.

## 16. Permission Engine

Decisão: `actor + agent + tool + resource + action + repo_id + risk_class + policy → allow | deny | require_approval`.

Regras fixas (não configuráveis por policy):
- ator `agent:*` **MUST NOT** escrever em protected paths — a lista é derivada do critério de CHAOS §4.1 (*todo arquivo que governa o comportamento de agentes futuros*) e inclui `metadata/policies/**`, `metadata/registries/**`, `order/policies/**`, `order/agents/**`, **`order/automations/**`**, `order/PAUSED`, **`AGENTS.md`**, **`metadata/schemas/**`** e **`workflows/**`** nem editar `audit/events.jsonl` **diretamente**: o ledger é append-only e só o adapter `chaos audit append` acrescenta linhas (nenhum ator escreve o arquivo com Write/Edit, `>>` ou editor);
- `audit/events.jsonl` é **multi-escritor por construção**: toda superfície que age (sessão na nuvem, worker local) acrescenta seus próprios EVT pelo adapter, e a concorrência é resolvida por `merge=union` (CHAOS §17.1) — **não** existe executor exclusivo do ledger. A exclusividade que existe no sistema é a do `views_builder` (`indexes/`, `graph/`), não a do audit. A automação do hosting **lê** o ledger para relatório e não acrescenta EVT;
- ator `agent:*` **MUST NOT** conceder permissão a si ou a outro agente;
- ator `agent:*` só executa comandos de shell presentes na allowlist do agente (default: `chaos`, `order`, `git` restrito a `status/log/diff/show`, leitura de arquivos). **`git commit`, `git push`, `git rebase`, `git merge` e `git reset` não são permitidos a agentes**: commits e sincronização passam por `chaos commit` e `chaos sync`, que injetam os trailers, aplicam a política de merge e recusam protected paths. Interpretadores (`python -c`, `node -e`), redirecionamentos e editores são negados;

  **Casos mínimos de negação.** A allowlist é *default-deny*: o que não está nela não roda. Esta tabela não é o mecanismo — é o **conjunto mínimo de casos** que AT-20 e AT-22 exercitam, e é o que dá sentido a "a mesma suíte de casos" do AT-22. Uma implementação que negue menos que isto não é conforme.

  A lista é organizada por **família de comando, não por plataforma**, e **MUST** ser negada inteira em qualquer host. A razão é concreta: um Windows com Git Bash instalado executa `sed -i` e `tee`; um Linux com PowerShell instalado executa `Set-Content`. Enumerar por sistema operacional deixaria metade da superfície aberta na máquina que tivesse os dois shells — que é o caso comum de quem usa Git no Windows.

  | Família | POSIX | Windows | Motivo |
  |---|---|---|---|
  | interpretador | `python -c`, `node -e`, `perl -e`, `ruby -e` | `powershell -Command`, `powershell -EncodedCommand`, `pwsh -c`, `cmd /c`, `wscript`, `cscript` | contorna o CLI e o EVT |
  | redirecionamento | `echo … > / >> arquivo` | `> / >>` do `cmd`, `Out-File`, `Set-Content`, `Add-Content` | escreve entidade sem validação |
  | editor em lugar | `vim`, `sed -i`, `tee`, `ed` | `notepad`, `Set-Content`, `Add-Content`, `Edit-File` | mesma razão do redirecionamento |
  | `git` de escrita | `commit`, `push`, `rebase`, `merge`, `reset`, `checkout --`, `restore` | idênticos | trailer não pode ser injetado depois |
  | protected path | escrita em `order/policies/**`, `order/automations/**`, `AGENTS.md`, `.claude/**`, `order/PAUSED` | idênticos | §16, regra fixa |
  | `audit/` direto | escrita em `audit/events.jsonl` fora do adapter | idem | ledger só cresce por `chaos audit append` |
  | shell aninhado | `bash -c`, `sh -c`, `zsh -c`, `env` | `cmd /c`, `powershell -File`, `start` | reintroduz tudo acima por dentro |

  **Critério, para quando surgir um caso novo:** é negado todo comando que **escreva arquivo ou execute código arbitrário sem passar pelo CLI**. Um binário que satisfaça o critério e não esteja na tabela é um defeito da tabela, não uma permissão — mesma regra dos protected paths (CHAOS §4.1). A tabela cresce com o ambiente; o critério não muda.

- protected paths incluem o próprio enforcement (`.claude/**`, `tools/**`, `.github/**`, `.gitattributes`, `CLAUDE.md`); um agente **MUST NOT** alterar hooks, permissões, CLI ou workflows — pede via tarefa A4;
- ação com `risk_class > autonomy_ceiling` do agente → `require_approval`, nunca `allow`;
- `privacy_class: work` → `deny` para qualquer canal ou ação externa não listado em `repo.yaml.allowed_channels`.

## 17. Risk Engine

Adota a taxonomia única A0–A4 (CHAOS §12). Cálculo **determinístico**:

```text
risk = max( tool.risk[by_resource(recurso)] ,
            tool.risk[by_field(campo, valor_antigo → valor_novo)] ,
            action_modifier(ação) ,
            entity.risk_hint ,
            decision_mapping(consequence, reversible) )
```

- o resultado nunca é menor que o declarado no Tool Registry para o recurso;
- `risk_hint` só eleva;
- o LLM **não participa** do cálculo; um agente pode *propor* elevação, nunca redução;
- toda avaliação é registrada no RUN (`risk_class`) e no EVT;
- **ler a camada episódica é A0 e não altera nada**: não eleva teto, não satisfaz requisito de evidência e não muda a classe da ação que vier depois. Uma ação A2+ cuja única justificativa seja registro episódico é negada pelo Permission Engine, como já ocorre com fonte `untrusted` (§16, AT-13).

## 18. Approval Engine

Aprovador único: o proprietário do sistema (`human:<owner>`, identificado na implantação). Fluxo: `Agente → APV (order/approvals/) → notificação → usuário aprova ou rejeita (modificar é rejeitar e abrir nova APV, CHAOS §7.4) → RUN continua ou encerra`.

- A3 → aprovação obrigatória; A4 → aprovação obrigatória **com** `decision_note` não vazio e registro EVT;
- APV expira em `expires_at` (default 24 h; automações podem definir menos); expirado = **não executa**, nunca "aprovado por silêncio";
- o pedido apresenta ação, motivo, impacto, risco, reversibilidade, alternativa e evidências;
- **A3:** o modo de aprovação é definido por `order/policies/approval.yaml → a3_mode`:
  - `out_of_band` (**valor inicial obrigatório**): igual a A4 — só por commit humano fora do caminho do modelo;
  - `code`: a APV recebe um código de 6 caracteres visível apenas no briefing/notificação (fora do contexto de qualquer agente); `order approval approve` exige o código;
  - `cli`: `order approval approve --note` em sessão interativa basta;
  - `per_area`: cada agente de área declara um dos três no registry.
  Mudar `a3_mode` é A4 (protected path) e só ocorre pela decisão da Fase 4 da Implementação Claude-Nativa (§13), com métricas em mãos.
- **A4:** aprovação **MUST** ocorrer fora do caminho do modelo — o usuário edita a APV num editor ou na interface web do hosting e o commit resultante não carrega trailer de agente. Uma APV A4 aprovada por CLI dentro de uma sessão de agente é inválida e o validador a rejeita (protege contra injeção de prompt que induza o modelo a "aprovar");
- a espera é **assíncrona**: o RUN fica `awaiting_approval` com checkpoint; nenhum processo bloqueia esperando.

**Risco residual (documentado):** nos modos `cli` e `per_area` com `cli`, uma injeção de prompt pode induzir o modelo a executar `order approval approve` numa APV A3 sem que o humano tenha pedido. Com o valor inicial `out_of_band` esse vetor não existe; ele só é aberto se o usuário escolher `cli` na decisão da Fase 4 (Implementação §13), à luz de `reversal rate`, aprovações não reconhecidas e warnings `untrusted`. Mitigações quando aberto: ID exato + `--note`; EVT e notificação imediata; A3 reversível por definição; reavaliação a cada relatório em que o limiar da opção vigente seja ultrapassado.

## 19. Kill-switch e Run Ledger

- **Kill-switch:** existência de `order/PAUSED` (conteúdo livre: motivo, autor, data). O `guard` verifica o arquivo local antes de toda ação A1+ e faz `fetch` do remoto no máximo a cada N minutos (default 5) para não depender do próximo pull. Efeito: nenhum trigger dispara; nenhuma tarefa é reclamada; RUNs em andamento checkpointam e param no próximo passo; sessões humanas continuam podendo instruir ações explicitamente. Criar/remover `PAUSED` é A4 e só humano faz. `chaos pause | resume` na CLI.
- **Run Ledger:** `order/runs/` é a lista viva do que está rodando, onde, desde quando e em que passo. `order status` **MUST** listar runs ativos, leases, custos acumulados e aprovações pendentes.

## 20. Quota Engine

Policies em `order/policies/quotas.yaml`:

```yaml
budget_sources:                      # declaradas na implantação a partir das assinaturas do usuário
  - id: <assinatura-1>
    cost_model: subscription         # subscription | free | pay_per_use
    measures: runs|sessions|tokens|usd   # a unidade que ESTA fonte consegue medir
    limit: { unit: <mesma de measures>, per: day|week|month, value: 0 }
    enabled: true
  - id: <provedor-local>
    cost_model: free
global:
  max_autonomous_actions_per_day: 0    # valores definidos na implantação
  max_notifications_per_day: 0
  quiet_hours: { start: "", end: "", tz: "<timezone do usuário>" }
per_agent: {}
per_automation: {}
on_exceeded: degrade_to_propose   # ou pause
```

Regras: cada fonte é contabilizada na unidade que consegue medir — sessões sob assinatura que não expõem tokens contam `runs`/`sessions`; gateways locais contam `tokens`/`usd`; o Quota Engine nunca inventa custo em dólares para fonte que não o mede. O Router **MUST NOT** usar uma `budget_source` com `enabled: false` ou com limite esgotado; `pay_per_use` só existe se o usuário a declarar explicitamente. Quando uma cota é excedida, o Control Plane rebaixa o modo das automações afetadas para `propose` até o reset e registra EVT. Consumo é estimado pelo Model Gateway e acumulado nos RUNs e por `budget_source`. Valores concretos são preenchidos no Onboarding Protocol, nunca fixados nesta especificação.

## 21. Model Registry, Policy, Router e Gateway

### 21.1 Registry

Descreve capacidades, contexto, modalidades, disponibilidade, `locality: cloud | local`, `budget_source` (ORDER §20) com seu `cost_model`, e `privacy_ok: [<classes>]`. O registry é preenchido na implantação **apenas com o que o usuário efetivamente possui** (assinaturas, planos gratuitos, modelos locais).

### 21.2 Policy

```yaml
assistant:   { minimum: { reasoning: high },   privacy: per_repo, tier_preference: [high, mid], cost_preference: [subscription, free] }
area-owner:  { minimum: { reasoning: high },   privacy: per_repo, tier_preference: [high, mid], cost_preference: [subscription, free] }
reasoning:   { minimum: { reasoning: high },   tier_preference: [high],      cost_preference: [subscription, free] }
routine:     { minimum: { reasoning: medium }, tier_preference: [mid, low],  cost_preference: [free, subscription] }
classify:    { minimum: { reasoning: low },    tier_preference: [low],       cost_preference: [free, subscription] }
coding:      { minimum: { coding: high },      tier_preference: [high, mid], cost_preference: [subscription, free] }
local_only:  { locality: local }
```

`assistant` é exigido porque o Assistente é obrigatório (§25) e todo agente do registry precisa de `model_policy` resolvível — sem ela, `order agent sync` não consegue gerar o binding. O patamar é o mesmo do dono de área: o Assistente decide delegações e faz triagem de conteúdo `external_source`, onde raciocínio fraco vira vetor de manipulação, não apenas resposta ruim.

### 21.3 Router — dois níveis

**Nível 1 — provedor/fonte de orçamento:** `Task → privacy (repo, tarefa) → locality → budget_sources habilitadas e com saldo → cost_preference da policy → provedores elegíveis`. Ordem padrão de preferência: `subscription` (já pago) → `free` → `pay_per_use` (só se habilitado). No runtime nuvem do Perfil A há um único provedor; no worker local o Gateway roteia entre todos os provedores declarados (remotos e locais).

**Nível 2 — tier:** dentro do provedor, `policy.tier_preference × custo × disponibilidade → modelo`. É o nível ativo em todo o MVP. No Claude Code, o binding é o campo `model:` do subagente.

Precedência: segurança/privacidade > requisitos de capacidade > preferência manual explícita > policy > otimização. Preferência manual nunca quebra segurança.

### 21.4 Gateway

Normaliza autenticação, chamadas, streaming, erros, retries, rate limits, métricas e **estimativa de custo** (alimenta Quota Engine). Perfil A nuvem: gateway implícito do Claude Code. Perfil A worker local: LiteLLM. Perfil B: LiteLLM ou OpenRouter.

### 21.5 Modos de roteamento

`manual`, `policy`, `automatic`, `fallback`, `experimental`.

## 22. Custo, limites e cache

Execuções registram modelo, provedor, tokens, duração, custo estimado, retries. Cache tem chave, TTL, versão do contexto e da policy/prompt.

## 23. Context Builder

Consome CHAOS §16. Além das regras do CHAOS: injeta `AGENTS.md`, o Área/Project State e os HND abertos no início de todo contexto de agente; marca `untrusted`; nunca cruza `privacy_class`; entrega os registros da camada episódica no bloco `episodic`, **sempre separado de `entities`** e sob orçamento de tokens próprio, para que continuidade nunca dispute espaço com evidência.

O bloco `episodic` serve a uma pergunta só: *o que já foi tentado sobre isto*. Ele **MUST NOT** ser citado como fonte, **MUST NOT** preencher `source_refs` e **MUST NOT** fundamentar ação A2+ (§17). Um agente que precise de um fato observado ali abre a promoção (CHAOS §21) e trabalha sobre a entidade resultante.

## 24. Memória operacional

A memória do sistema tem **três camadas nomeadas**, com autoridades distintas:

| Camada | Onde vive | Autoridade | Quem escreve |
|---|---|---|---|
| Operacional | `order/` do CHAOS — RUN, SES, HND | estado durável de execução; verdade sobre o que está em andamento | executores, via `chaos commit`, com risco classificado |
| Canônica | entidades CHAOS | a verdade do acervo | humano e agentes, pelo caminho governado |
| Episódica | repositório episódico (CHAOS §4.2) | **nenhuma** — continuidade e busca, nunca fato | a camada episódica, automaticamente, sem passar pelo `guard` |

Toda memória operacional do ORDER é arquivo em `order/` (RUN, SES, HND): nenhuma sessão é portadora única de estado. A camada episódica é **RECOMMENDED no Perfil A** (§41), implementada por `ai-memory` (Implementação §17), e resolve o que a memória nativa de runtime resolvia mal — continuidade entre sessões, entre máquinas e entre CLIs de fornecedores diferentes — sem herdar o defeito dela.

A regra que governava a memória nativa continua valendo, e agora com ocupante melhor: **qualquer fato durável MUST ser promovido a entidade CHAOS** (`chaos promote`). Memória nativa de runtime (a do Claude Code, a de um Project) permanece cache de conveniência e não é elegível nem para o papel episódico, porque não é inspecionável, não é versionada e não sobrevive à troca de fornecedor.

A camada é opcional em sentido verificável: sua ausência não altera nenhum Acceptance Test (CHAOS AT-34) e está declarada em §40.

## 25. Assistente Pessoal (chefe de gabinete)

Funções: triagem do inbox e roteamento por área; agenda; lembretes; follow-ups; briefing diário e revisão semanal (gerados a partir dos Área States); deadlines; pendências de aprovação; notificações consolidadas. Canais: Claude Mobile/Web/Desktop (Perfil A, sempre); Telegram (fase posterior); nunca Obsidian como canal obrigatório. `autonomy_ceiling: A2`.

## 26. Agentes funcionais

- **Researcher:** pesquisa, fontes, síntese, conflitos, citações; teto A1; nunca promove a canonical.
- **Planner:** objetivos → milestones, tarefas, dependências, riscos, critérios; teto A1.
- **Reviewer:** qualidade, consistência, schemas, provenance, policies; teto A1; único que pode marcar `review → done` além do humano.
- **Coder:** opera repositórios de código em sandbox, com testes e Git; commit em repo de código é A3 (exige aprovação) salvo policy por repositório; teto A3 com aprovação.
- **Librarian:** classifica inbox, cria links, valida provenance, detecta duplicidade, arquiva; teto A1; promoção a `canonical` exige `verified_by`.
- **Decision Analyst:** estrutura problema, alternativas, critérios, trade-offs, recomendação; escreve DEC `proposed|analyzed`; usuário decide.

## 27. Agentes de área

Responsáveis por: Área State; priorização; projetos da área; tarefas, milestones, dependências, riscos; bloqueios; próximos passos; preparação de reuniões; **receber gatilhos e decidir o que delegar**. Não alteram decisão A3+ sem aprovação. Teto A2.

## 28. Trigger Engine e escada de maturidade

### 28.1 Modos de operação (visão)

`manual` (usuário pede) · `assisted` (sistema identifica e pede orientação) · `proactive` (condição inicia, sistema propõe/executa conforme maturidade) · `autonomous` (executa dentro de limites sem intervenção).

### 28.2 Gatilhos

`time`, `calendar_event`, `deadline`, `file_change`, `inbox_item`, `message`, `project_state_change`, `approval_decided`, `lease_expired`, `external_event`.

### 28.3 Pipeline

```text
Trigger → Dedup (chave: automation_id + evento + janela) → Kill-switch? → Quota? →
Evaluate (agente de área decide utilidade; A0) → Mode gate (§28.4) → Run → Validate → Notify → Audit
```

### 28.4 Escada de maturidade (por automação)

| Nível | Comportamento | Promoção |
|---|---|---|
| `shadow` | avalia e registra o que faria em um RUN `mode: shadow`; não age; o briefing seguinte lista os runs shadow com "teria feito X — promover?" | após N execuções com avaliação humana positiva (default N=5) |
| `propose` | cria proposta (tarefa/rascunho) e pede ok | após N aprovações consecutivas sem modificação |
| `auto_notify` | executa e notifica depois | após N execuções sem reversão |
| `auto` | executa silenciosamente; aparece no briefing | — |

Regras: automação nasce em `shadow`; promoção é ação humana (A4, edita `order/automations/AUT-*.md`); rebaixamento é automático a qualquer falha, reversão ou cota excedida; **ações A3+ nunca passam de `propose`**; A0/A1 podem chegar a `auto`; A2 pode chegar a `auto_notify`.

## 29. Automation (AUT)

```yaml
id: AUT-20260918-B7NC5D
type: automation
name: "Briefing diário"
owner_agent: agent.assistant
repo_id: chaos-<classe>
trigger: { type: time, expression: "0 7 * * 1-5", tz: "<timezone do usuário>" }
conditions: []
action: { workflow: wf.daily-briefing }
max_risk: A2
maturity: propose
promotion: { n_required: 5, n_current: 0, history: [] }
quota: { max_usd_per_run: 0.30 }
notification: { channels: [claude_chat], on: [proposed, completed, failed] }
enabled: true
```

## 30. Sessions, Tasks e Runs

`Session (SES) → Task (TSK) → Run (RUN)`. Sessão: contexto de trabalho em uma superfície. Tarefa: unidade lógica. Run: execução concreta, com checkpoint. Todos rastreáveis e persistidos em CHAOS; uma sessão sem RUN nem HND existe apenas como par de EVT (`session_open`/`session_close`).

## 31. Failure Handling

Tipos: timeout, rate limit, provider error, tool error, validation error, permission denied, approval expired, dependency failure, context failure, lease lost, **toolchain drift**, unknown. Estratégias: retry limitado com backoff; fallback de tier/provedor conforme policy; checkpoint e abandon para retomada por outro executor; compensação; escalonamento humano; degradação de maturidade.

**Divergência de toolchain.** Quando `chaos health` (CHAOS §21.1) reporta `drift` — o binário em execução não é o da tag vendorizada — as automações são rebaixadas a `propose`, um EVT de nível `warning` é gravado e o estado aparece no briefing e em `order status` (§33). RUNs em andamento terminam; nenhum novo claim autônomo ocorre até o alinhamento. Com `broken`, nada autônomo roda, como sob `PAUSED`.

O rebaixamento reutiliza deliberadamente o caminho de cota excedida (§20) em vez de criar um segundo mecanismo de freio: um sistema com duas formas diferentes de "quase parado" tem duas formas de falhar ao voltar. E o alinhamento é humano por construção, porque `chaos tooling update` escreve em protected path.

## 32. Determinismo

Regras críticas — risco, permissão, cotas, validação, kill-switch, elegibilidade de fila, promoção de maturidade — são código e policies, nunca LLM. LLM é apropriado em interpretação, geração, avaliação de utilidade e planejamento.

## 33. Observabilidade

Por RUN: task, agent, executor, modelo/provedor/tier, ferramentas, timestamps, duração, tokens/custo, resultado, erro, aprovações, EVT refs. `order status` reporta também o estado de saúde do toolchain (`ok｜drift｜broken`, CHAOS §21.1) e, em `drift`, as duas versões em conflito. `order status` e `order report --period` são obrigatórios; OpenTelemetry/Langfuse são opcionais (Perfil B).

## 34. Audit Integration

Toda ação A1+ gera EVT em `audit/events.jsonl` com `who + what + when + where(surface) + why(policy) + before + after + evidence + approval`. A2+ **MUST** referenciar `approval_id` ou policy dispensante. Todo commit de agente carrega trailers `Actor: agent:<id>` e `Surface: <x>` (CHAOS §17.1).

## 35. Segurança

Least privilege; sandbox para código; allowlist de ferramentas por agente; secret management fora do Git e fora de prompts; isolamento; timeouts; limites de recursos; logs sanitizados; aprovação crítica; protected paths; conteúdo externo como dado; separação `personal`/`work`.

## 36. Execução de código

Coding runtime controla workspace, CPU/memória, rede, filesystem, timeout, processos, dependências, testes e rollback. Commit em repositório de código é A3 por padrão.

## 37. Configuração

Precedência: `defaults → config → environment → repo policy → automation policy → task policy → instrução explícita do usuário`, exceto quando policy de segurança superior impedir. Policies vivem em protected paths.

## 38. API e CLI

API mínima: `/tasks /tasks/{id}/claim /runs /approvals /agents /automations /models /route /audit /status /health /pause /resume`.

CLI — **este é o contrato completo**. Um binding (Implementação §11) pode acrescentar comandos próprios do seu perfil, mas **MUST NOT** declarar lista paralela nem renomear estes:

```text
order status | health | report
order task   submit|claim|release|resume|show <id>
order run    list|show|checkpoint|act|abandon|resume|merge <id>
order approval list|show|approve|reject <id> [--note]
order delegate --task <id> --to <agent> --objective <texto>
order handoff  list|show|close <id>
order session  open|close
order agent    list|show|run|sync
order automation list|promote|demote|sync <id>
order trigger  fire|scan
order risk     eval
order guard    [--] <comando>
order model    list|route|call
order workflow list|show|run <nome> [--run <RUN>] [--dry-run]
order notify   --channel <c> --message <m>
order quota    status
order audit    inspect
order episodic status | handoff list|accept <id>
```

Três esclarecimentos que a divisão anterior deixava em aberto:

- **O kill-switch é do `chaos`, não do `order`.** `PAUSED` é estado no repositório, não do runtime, e precisa funcionar com o ORDER ausente (AT-09 do CHAOS). `chaos pause|resume` é o único caminho; `order` apenas **lê**.
- **Claim é da tarefa, resultado é o RUN.** `order task claim <TSK>` devolve o `run_id`; não existe `run claim`. Retomar é `run resume` (continua a execução) — `task resume` não existe, porque quem retoma é a tentativa, não o item de trabalho.
- **`order episodic` observa; `chaos promote` é quem traz para dentro.** O `order` consulta o estado da camada episódica e aceita o handoff de sessão que ela oferece (CHAOS §4.2); promover um fato observado para entidade canônica é da CLI do `chaos`, porque o produto é uma entidade CHAOS. Nenhuma das duas escreve na camada episódica: quem escreve nela é o componente que a implementa.
- **Entidades nascem pelo `chaos`, maturidade é do `order`.** AUT, APV e HND são entidades CHAOS (§7.3): criam-se com `chaos <tipo> create`. O ORDER as promove, aprova, expira e fecha — nunca as cria do nada, exceto APV emitida pelo Approval Engine em resposta a `run act` que exceda o teto.

`run checkpoint` e `run act` são os dois primitivos de execução: o primeiro grava o checkpoint de §7.4 do CHAOS — sem ele o contrato de retomada não tem operação que o produza —; o segundo é onde Risk Engine, Permission Engine e Approval Engine são aplicados antes de qualquer efeito.

## 39. Testing e Evaluation

Unit, integration, workflow, security, golden, recovery e **evaluation** (task success, factuality, citation coverage, retrieval precision/recall, tool success, failure rate, latency, cost, approval rate, **unnecessary-action rate, reversal rate**). Reprodutibilidade: cada RUN registra versões de agente, workflow, modelo, policy, prompt, contexto, ferramentas e configuração.

## 40. Graceful Degradation

Sem runtime nuvem → worker local assume `any`; sem worker local → tarefas `local` esperam; sem provedor remoto → Ollama para `local`; sem vetor → BM25 + grafo; sem Obsidian → Git/CLI/Claude; sem MCP → adapters; sem LangGraph → runner próprio; sem canal externo → notificação em `order/` e no próximo briefing; **sem camada episódica → `context.episodic` vazio, busca por BM25 e grafo, handoff entre sessões pelos HND do `order/` como antes** — nenhum comando falha e nenhum AT muda de resultado.

## 41. Matriz tecnológica — dois perfis

| Capacidade | Perfil A — Claude-nativo (MVP) | Perfil B — auto-hospedado |
|---|---|---|
| Runtime primário | sessões Claude Code (nuvem) + tarefas agendadas Claude | OpenClaw |
| Runtime secundário / retomada | worker local Python | idem |
| Runtime de coding | Claude Code | OpenHands |
| Workflow engine | subagentes + hooks Claude Code + runner YAML próprio | LangGraph |
| Model Gateway (nuvem) | implícito (provedor único) | LiteLLM / OpenRouter |
| Model Gateway (local) | LiteLLM → provedores remotos declarados + Ollama | LiteLLM |
| Modelos locais | Ollama | Ollama / vLLM |
| Memória operacional | arquivos `order/` | arquivos `order/` |
| Memória episódica | `ai-memory` (RECOMMENDED) — captura de sessão sem LLM, busca híbrida, handoff entre CLIs | `ai-memory` / nenhuma |
| Índice derivado | SQLite reconstruível (CHAOS §15) | SQLite / PostgreSQL |
| Handoff entre CLIs de fornecedores diferentes | camada episódica; HND do `order/` como piso | HND do `order/` |
| Estado operacional | arquivos | SQLite / PostgreSQL |
| Interoperabilidade | CLI, API, adapters (MCP quando permitido) | MCP |
| Canais | Claude Mobile/Web/Desktop; canal externo à escolha (fase 4) | Telegram/WhatsApp via OpenClaw |
| Observabilidade | `order status`, EVT | OpenTelemetry, Langfuse |
| Versionamento | Git (hosting à escolha do usuário) | Git |

Nenhum LLM/provider é RECOMMENDED; o binding Anthropic do Perfil A é registrado como `TEC-...`. Cada item é substituível conforme CHAOS §27.2; a troca de perfil não altera contratos.

## 42. Anti-padrões

Agente monolítico; modelo como controlador de segurança; LLM como banco; vector DB como única memória; runtime como source of truth; MCP como dependência; protocolo preso a provider; ação irreversível automática; ausência de auditoria; retries infinitos; workflows sem idempotência; acesso irrestrito a ferramentas; microserviços no MVP; **risco auto-declarado; espera bloqueante por aprovação; "aprovado por silêncio"; flag de pular aprovação; automação nascendo em `auto`; agente escrevendo policies; estado só em memória de sessão; fila sem lease**; **camada episódica como fonte; promoção como atalho de privilégio; contexto que funde observação e evidência**.

## 43. Compatibilidade

Implementações são equivalentes se preservarem: Agent Protocol; Handoff/Delegation; Task Queue Protocol; workflow semantics; routing em dois níveis; permission e risk semantics (A0–A4); approval semantics; escada de maturidade; CHAOS schemas; audit; provenance; idempotência; kill-switch; cotas; graceful degradation.

## 44. Acceptance Tests

- **AT-01 Registration:** agente registrado e descoberto por `kind`, área e capability.
- **AT-02 Routing tier:** tier compatível com policy é selecionado.
- **AT-03 Routing provider:** tarefa `local_only` nunca é enviada a provedor remoto; nenhuma chamada usa `budget_source` desabilitada ou esgotada.
- **AT-04 Deterministic risk:** mesma ação/recurso → mesma classe, independentemente do texto da tarefa; `risk_hint` menor é ignorado.
- **AT-05 Approval:** A3 gera APV e o RUN fica `awaiting_approval` sem processo bloqueado; APV expirado não executa.
- **AT-06 Handoff:** segundo agente reconstrói contexto só com HND + CHAOS.
- **AT-07 Queue:** dois executores tentando o mesmo claim → exatamente um vence.
- **AT-08 Resume:** lease expirado → outro executor retoma do checkpoint, desde que o checkpoint tenha todos os campos obrigatórios (CHAOS §7.4); checkpoint incompleto → `blocked(missing_checkpoint)`, nunca retomada por inferência.
- **AT-09 Kill-switch:** com `PAUSED`, triggers não disparam e claims não ocorrem.
- **AT-10 Quota:** cota diária excedida → automações rebaixadas a `propose`.
- **AT-11 Maturity:** automação nova está em `shadow`; A3 nunca chega a `auto_notify`.
- **AT-12 Protected paths (motor):** o Permission Engine nega escrita de `agent:*` em `policies/` e **registra a tentativa** em EVT. Complementa CHAOS AT-15, que verifica as três **camadas** (hook, validador, CODEOWNERS); aqui verifica-se a decisão e o registro, não o enforcement em camadas.
- **AT-13 Untrusted (determinístico):** o Permission Engine **nega** ação A2+ de um RUN cuja única justificativa seja fonte `untrusted`, e a tentativa gera EVT com warning. A resistência do **modelo** a instrução embutida é eval (CHAOS §30.1), fora da DoD: portão binário não pode depender de resultado probabilístico.
- **AT-14 Privacy (endereçamento):** entidade de uma `privacy_class` não é sequer endereçável a partir de outra — `order task claim` de ID de outra classe falha, e o contexto montado nunca a contém. Complementa CHAOS AT-14, que verifica o Context Builder.
- **AT-15 Delegation:** delegado herda teto mínimo; profundidade > policy é rejeitada.
- **AT-16 Provider/runtime independence (ausência de acoplamento):** nenhum identificador de provedor, modelo, gateway ou runtime aparece no registry de agentes ou no frontmatter de qualquer entidade; substituir `model-registry.yaml` inteiro por outro conjunto de modelos não exige editar nenhum agente nem nenhuma entidade. Formulado como ausência de acoplamento porque "trocar de perfil preserva contratos" só seria observável com duas implementações completas — e um portão que ninguém consegue executar passa por omissão.
- **AT-17 Audit:** toda ação A1+ tem EVT; A2+ referencia approval ou policy.
- **AT-18 Claim race — o perdedor (v2.3):** no arranjo do AT-07, o executor que **perde** descarta o próprio commit de claim (`reset --hard` para o remoto), não tenta rebase nem merge, não deixa marcador de conflito nem RUN órfão, e reavalia a fila. AT-07 verifica que há exatamente um vencedor; este verifica o que acontece com o outro, que é onde a Implementação §8.1 é específica.
- **AT-19 Out-of-band (v2.3):** `order approval approve` numa APV A4 — e numa APV A3 com `a3_mode: out_of_band` — dentro de sessão de agente falha; commit humano aprovando é aceito. Com `a3_mode: code`, aprovação sem o código falha.
- **AT-20 Shell allowlist (v2.3):** `python -c` executado por agente para editar entidade é negado e registrado em EVT.
- **AT-21 Commit path (v2.3):** `git commit` direto por agente é negado; `chaos commit` produz commit com trailers e recusa protected paths.
- **AT-22 Worker guard (v2.3):** o worker local nega em processo as mesmas ações que o hook nega na nuvem (mesma suíte de casos).
- **AT-23 Risco por campo (v2.3):** escrever `privacy: local_only → cloud_allowed` numa entidade comum é classificado **A4**, não A1, embora o caminho do arquivo só declare `default: A1`; a mesma escrita na direção inversa é A1. Idem para `execution: local → cloud|any` e para qualquer mudança de `privacy_class`.
- **AT-24 Bloqueio sem escape (v2.3):** tarefa `local_only` sem capacidade local fica `blocked(no_model_capacity)`; nenhum caminho automático a converte em execução na nuvem — nem rebaixando privacidade, nem trocando `execution`, nem por aprovação A3 em sessão.
- **AT-25 Worker ausente (v2.3):** tarefa `execution: local` pronta e sem nenhum claim por mais de `no_worker_timeout_h` recebe `blocked(no_local_worker)` e aparece no briefing; ao subir um worker elegível, ele a reclama e `blocked_reason` é limpo. Em nenhum momento a tarefa é oferecida ao runtime nuvem.
- **AT-26 Maturidade não sobe pela entidade (v2.3):** AUT é entidade CHAOS, logo alcançável por `chaos automation update`. Um agente alterando `maturity`, `max_risk`, `enabled` ou `quota` de uma AUT é **negado** — `order/automations/**` é protected path (CHAOS §4.1) e A4 por recurso (§14). AT-11 exercita o caminho `order automation promote`; este exercita o caminho que o contornava.

- **AT-27 Episódico não é evidência (v2.4):** um RUN cuja única justificativa para ação A2+ seja um registro do bloco `episodic` é **negado** pelo Permission Engine e a tentativa gera EVT; `context.episodic` nunca aparece dentro de `context.entities` nem preenche `source_refs`; ler a camada episódica não altera a classe de risco da ação seguinte. Após `chaos promote`, a ação com a mesma justificativa — agora entidade canônica — é avaliada normalmente.
- **AT-28 Promoção sem privilégio (v2.4):** `chaos promote` cujo alvo seja protected path é **A4** e recusado em sessão de agente; promoção que rebaixaria `privacy` é A4; promoção comum é A1 e produz EVT como qualquer escrita. Não existe caminho em que promover escreva algo que `chaos <tipo> create` recusaria.

- **AT-29 Divergência de toolchain (v2.5):** com `chaos health` reportando `drift`, automações em `auto` são rebaixadas a `propose`, nenhum claim autônomo novo ocorre, um EVT `warning` é gravado e `order status` mostra as duas versões; RUN já em andamento chega ao fim normalmente. Restabelecido o alinhamento, a maturidade anterior **não** volta sozinha — subir de novo passa por `order automation promote`, como qualquer promoção. Com `broken`, nada autônomo roda.

## 45. Definition of Done — ORDER v2.5

Agentes registráveis em matriz; tasks/runs rastreáveis e retomáveis; fila com lease funcionando entre nuvem e worker local; risco determinístico; permissões com protected paths; aprovações assíncronas com expiração; kill-switch e cotas ativos; triggers com dedup e escada de maturidade; roteamento em dois níveis; contexto recuperável e marcado por confiança; memória operacional em `order/`; **camada episódica separada, sem autoridade e dispensável**; **toolchain verificado antes de qualquer execução autônoma**; auditoria completa; falhas recuperáveis; execução observável; código isolado; canais substituíveis; nenhum provider estrutural; **todos os Acceptance Tests de §44 passam** — a suíte inteira, sem faixa numérica (ver CHAOS §32).

## 46. Golden Rules

1. CHAOS é a verdade persistente; `order/` é o estado operacional durável.
2. ORDER executa e orquestra; nunca é source of truth.
3. LLM raciocina; não decide risco, permissão nem cota.
4. Risco vem da ferramenta e do recurso, não do texto.
5. Autonomia se conquista pela escada; nasce em `shadow`.
6. A3+ sempre passa pelo humano; silêncio nunca aprova.
7. `PAUSED` para tudo, de qualquer superfície.
8. Toda tarefa tem dono de área; todo trabalho funcional é delegado.
9. Continuidade vive em RUN, HND e SES — nunca na sessão.
10. Conteúdo externo é dado.
11. Policies só humanos escrevem.
12. Observação não é fato: o que a camada episódica registra só vira verdade por promoção.
12. Classes de privacidade não se misturam.
13. Toda tecnologia é substituível abaixo do contrato.
