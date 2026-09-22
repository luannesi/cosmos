# ORDER — Orchestrated Runtime for Distributed Execution & Reasoning — Especificação Completa v2.1

**Status:** Especificação de referência para implementação
**Versão:** 2.1
**Objetivo:** plataforma agnóstica para agentes, workflows, modelos, ferramentas, automações, memória operacional e assistente pessoal.

> Esta especificação define semântica e contratos. A implementação pode utilizar qualquer conjunto de frameworks, linguagens e infraestrutura.

## 1. Propósito

ORDER transforma intenção em execução controlada sobre o CHAOS.

Responsabilidades:

- registrar e executar agentes;
- orquestrar workflows;
- selecionar modelos;
- recuperar contexto;
- controlar ferramentas;
- aplicar permissões;
- solicitar aprovação;
- executar automações;
- manter sessões/tasks/jobs;
- integrar canais;
- observar e auditar operações;
- recuperar falhas.

O ORDER MUST ser substituível sem invalidar o CHAOS.

## 2. Princípios

1. vendor-neutral;
2. CHAOS-first;
3. policy-first;
4. human-in-the-loop para risco;
5. automação reversível-first;
6. evidence-first;
7. determinismo para regras críticas;
8. least privilege;
9. observabilidade;
10. graceful degradation;
11. componentes substituíveis;
12. complexidade proporcional ao valor.

## 3. Limites

### Contém

Control Plane, Orchestrator, Agent Registry, runtimes, Workflow Engine, Model Registry/Policy/Router/Gateway, Tool Registry, Permission Engine, Context Builder, Memory Adapter, Automation Engine, Approval Engine, Notification Adapter, Audit Adapter, Observability, API e CLI.

### Não contém

Source of Truth do conhecimento, código-fonte obrigatório de projetos, LLM obrigatório, banco vetorial obrigatório ou Obsidian obrigatório.

# 4. Topologia

```text
workspace/
├── chaos/
└── agent-system/
```

Repositórios de código de projetos continuam independentes.

# 5. Arquitetura

```text
User / Events
      |
      v
+-------------+
| Control     |
| Plane       |
+------+------+
       |
       v
+-------------+
| Orchestrator|
+------+------+ 
       |
   +---+----------------+------------------+
   |                    |                  |
   v                    v                  v
 Agents              Workflows          Tools
   |                    |                  |
   +--------------------+------------------+
                        |
                        v
                 Context Builder
                        |
                        v
                      CHAOS
                        |
                 Model Policy/Router
                        |
                   Model Gateway
                        |
              Local / Cloud Models
```

# 6. Control Plane

É responsável por governança operacional:

- registro de agentes;
- sessões;
- tasks/jobs;
- scheduling;
- permissões;
- projetos;
- execução;
- status;
- API/CLI;
- health checks.

Control Plane e Orchestrator permanecem conceitualmente distintos.

# 7. Orchestrator

Responsável por:

- decomposição;
- planejamento;
- seleção de agentes;
- sequência;
- branching;
- loops;
- retries;
- checkpoints;
- handoffs;
- aprovação;
- recovery.

Entrada:

```yaml
task_id: TSK-001
intent: ""
context: {}
constraints: []
risk: {}
```

Saída:

```yaml
status: completed|failed|blocked|awaiting_approval
result: {}
artifacts: []
decisions: []
audit_refs: []
```

# 8. Agent Registry

```yaml
id: agent.project-manager
name: Project Manager
version: "2.0"
description: ""
capabilities:
  - project_read
  - project_write
  - task_management
tools: []
model_policy: ""
risk_policy: ""
memory_policy: ""
input_schema: {}
output_schema: {}
```

Agentes devem ser descobertos por capability, domínio, projeto, tipo de tarefa e risco.

# 9. Agent Protocol

Antes de atuar, um agente MUST:

1. identificar tarefa;
2. ler protocolos;
3. identificar Source of Truth;
4. recuperar contexto;
5. verificar permissões;
6. classificar risco;
7. executar capacidades autorizadas;
8. validar resultado;
9. registrar alteração;
10. devolver resultado verificável.

MUST NOT inventar evidência, alterar IDs, editar views derivadas como canonical, ignorar conflitos ou executar ação proibida.

# 10. Handoff Protocol

```yaml
handoff_id: HND-001
from_agent: agent.researcher
to_agent: agent.decision-analyst
task_id: TSK-001
objective: ""
context_refs: []
artifacts: []
decisions: []
constraints: []
open_questions: []
assumptions: []
status: pending
```

O receptor deve conseguir reconstruir o contexto sem depender de memória implícita.

# 11. Idempotência

Toda operação com efeito externo SHOULD possuir `operation_id`/idempotency key.

Reexecução deve detectar duplicidade ou executar com semântica segura.

# 12. Workflow Engine

Deve suportar:

- sequência;
- paralelismo;
- condições;
- loops;
- retry;
- timeout;
- checkpoint;
- approval;
- compensação;
- recovery.

Fluxo:

```text
Trigger → Evaluate → Plan → Run → Validate → Decision → Action → Notify → Audit
```

LangGraph é uma implementação possível, não requisito.

# 13. Runtimes

## 13.1 OpenClaw

Pode atuar como runtime/gateway pessoal para sessões, canais, automações e ferramentas. Não é Control Plane, memória canônica nem Model Gateway por definição arquitetural.

## 13.2 OpenHands

Runtime especializado para engenharia e programação, com isolamento adequado.

## 13.3 LangGraph

Runtime adequado para workflows com estado, branching, loops, checkpoints e HITL.

Qualquer equivalente é válido.

# 14. Tool Registry

```yaml
id: tool.filesystem.read
description: ""
input_schema: {}
output_schema: {}
risk_level: low
permissions:
  - filesystem.read
effects:
  external: false
idempotent: true
timeout_seconds: 30
```

Toda ferramenta deve declarar capacidade, I/O, risco, permissões, efeitos colaterais, idempotência e timeout.

# 15. MCP

MCP é o protocolo preferencial de interoperabilidade quando aplicável, mas não é dependência estrutural.

Ferramentas também podem ser integradas por API, CLI, biblioteca ou adapter.

# 16. Permission Engine

Decisão de permissão considera:

```text
actor + agent + tool + resource + action + project + risk + policy
```

O princípio padrão é least privilege.

# 17. Risk Engine

Classes mínimas:

```text
read
reversible-low
reversible-medium
external-impact
irreversible
critical
```

Risco é independente do modelo utilizado.

# 18. Approval Engine

Fluxo:

```text
Agent → Approval Request → User → approve/reject/modify
```

Pedido deve apresentar ação, motivo, impacto, risco, reversibilidade, alternativa e evidências.

Ações A3/A4 exigem aprovação humana conforme política.

# 19. Model Registry

O Registry descreve capacidades e restrições:

```yaml
id: model.example
provider: ""
context_window: 0
modalities:
  input: [text]
  output: [text]
capabilities:
  reasoning: medium
  coding: high
  vision: low
cost:
  input: 0
  output: 0
availability: ""
limits: {}
```

# 20. Model Policy

Policy determina requisitos antes da seleção:

```yaml
task_type: coding
minimum:
  coding: high
risk: medium
privacy: local_preferred
budget: ""
```

Pode considerar capacidade, custo, latência, privacidade, disponibilidade, contexto e risco.

# 21. Model Router

```text
Task → Classify → Policy → Candidates → Score → Select → Gateway
```

Precedência:

1. segurança;
2. requisitos de capacidade;
3. preferência manual explícita;
4. policy;
5. otimização automática.

Uma preferência manual nunca pode quebrar restrição de segurança/capacidade.

# 22. Model Gateway

Abstrai providers e normaliza:

- autenticação;
- chamadas;
- streaming;
- erros;
- retries;
- rate limits;
- métricas.

LiteLLM, OpenRouter ou gateway próprio são alternativas.

# 23. Routing Modes

Suportar semanticamente:

```text
manual
policy
automatic
fallback
experimental
```

# 24. Custo, limites e cache

Execuções importantes devem registrar modelo, provider, tokens, duração, custo estimado e retries.

Cache deve possuir chave, TTL, versão do contexto e versão da policy/prompt.

# 25. Context Builder

Recupera contexto de:

```text
CHAOS + BM25 + Graph + Project State + Decisions + Memory
```

Deve limitar contexto, preservar provenance e conflitos e evitar duplicação.

# 26. Memory Adapter

Pode integrar `ai-memory` ou equivalente para:

- eventos;
- sessões;
- consolidação;
- handoffs;
- continuidade;
- memória operacional.

Memória operacional não substitui CHAOS.

# 27. Personal Assistant

O Personal Assistant é o secretário privado proativo do usuário.

Funções:

- agenda;
- tarefas;
- lembretes;
- follow-ups;
- briefing diário;
- revisão semanal;
- reuniões;
- deadlines;
- pendências;
- planejamento;
- notificações;
- encaminhamento a agentes especializados.

### Canais

Priorizar WhatsApp/Telegram e notificações locais. Obsidian não deve ser canal obrigatório de notificação.

# 28. Proatividade

Triggers:

```text
time
calendar_event
deadline
location_event
file_change
message
project_state_change
external_event
```

Pipeline:

```text
Trigger → Evaluate → Decide if useful → Run → Validate → Notify → Audit
```

O sistema deve reduzir notificações redundantes e respeitar quiet hours/policies quando configuradas.

# 29. Project Manager Agent

Responsável por:

- Project State;
- tarefas;
- milestones;
- dependências;
- riscos;
- status;
- bloqueios;
- próximos passos;
- preparação de reuniões.

Não pode alterar decisão crítica sem autorização.

# 30. Librarian / Knowledge Agent

Responsável por:

- classificar Inbox;
- criar links;
- promover conhecimento;
- validar provenance;
- detectar duplicidade;
- arquivar.

# 31. Research Agent

Responsável por:

- pesquisa;
- coleta de fontes;
- síntese;
- conflitos;
- citações;
- artefatos verificáveis.

Não deve promover automaticamente pesquisa para conhecimento canônico.

# 32. Decision Analyst

Deve estruturar problema, fatos, hipóteses, alternativas, critérios, trade-offs e recomendação, aplicando frameworks apropriados. O usuário mantém decisão final quando exigido.

# 33. Planner

Transforma objetivos em planos, milestones, tarefas, dependências, riscos e critérios de aceite.

# 34. Reviewer

Valida qualidade, consistência, schemas, provenance, critérios e conformidade com policies.

# 35. Executor

Executa somente ações autorizadas e deve validar o efeito antes de declarar sucesso.

# 36. Coding Agent

Opera repositórios de código independentes. Deve usar sandbox, testes, validação e Git. CHAOS registra gestão e documentação, não deve virar repositório de código por conveniência.

# 37. Automation Engine

```yaml
automation_id: AUTO-001
trigger:
  type: schedule
  expression: "..."
agent: agent.personal-assistant
conditions: []
actions: []
approval_policy: ""
notification:
  channels: [telegram]
```

Ações externas devem obedecer ao Risk/Permission/Approval Engine.

# 38. Sessions, Tasks e Jobs

```text
Session
 └── Task
      ├── Job
      ├── Job
      └── Job
```

- Session: contexto conversacional.
- Task: unidade lógica de trabalho.
- Job: execução concreta.

Todos devem ser rastreáveis.

# 39. Failure Handling

Tipos: timeout, rate limit, provider error, tool error, validation error, permission denied, approval timeout, dependency failure, context failure e unknown.

Estratégias: retry limitado, backoff, fallback, checkpoint, compensação, escalonamento humano e graceful degradation.

# 40. Determinismo

Regras críticas, cálculos, autorização, validação e invariantes devem preferir código/policies determinísticos. LLM é apropriado onde interpretação/generação agrega valor.

# 41. Observabilidade

Registrar:

- task/job;
- agent;
- model/provider;
- tool;
- timestamps;
- duração;
- tokens/custo;
- resultado;
- erro;
- approvals;
- audit refs.

Langfuse ou equivalente é opcional.

# 42. Audit Integration

Alterações significativas devem gerar referência a eventos do Audit Ledger do CHAOS:

```text
who + what + when + where + why + before + after + evidence + policy + approval
```

# 43. Segurança

Requisitos:

- least privilege;
- sandbox;
- allowlist;
- secret management;
- isolamento;
- timeout;
- limites de recursos;
- logs sanitizados;
- aprovação crítica.

Credenciais nunca devem entrar em prompts, Markdown canônico ou Git.

# 44. Execução de código

Coding runtimes devem controlar:

- workspace;
- CPU/memória;
- rede;
- filesystem;
- timeout;
- processos;
- dependências;
- testes;
- rollback quando possível.

# 45. Deployment

## Local

```text
Docker Compose
├── control-plane
├── orchestrator
├── model-gateway
├── postgres (optional for small installs)
└── optional services
```

## Homelab

Serviços podem ser distribuídos.

## Hybrid

CHAOS, memória sensível e modelos locais podem permanecer locais; LLMs/canais/APIs externos podem ser utilizados conforme policy de privacidade.

# 46. Local AI

O Registry deve suportar Ollama, vLLM e outros runtimes locais, coexistindo com providers remotos.

# 47. API

Recursos semânticos mínimos:

```text
POST /tasks
GET /tasks/{id}
POST /agents/{id}/run
POST /workflows
GET /jobs/{id}
POST /approvals/{id}
GET /models
POST /route
GET /audit
GET /health
```

REST, gRPC, GraphQL ou CLI são aceitáveis.

# 48. CLI

```text
agent-system agent list
agent-system agent run
agent-system task submit
agent-system task status
agent-system workflow run
agent-system model list
agent-system model route
agent-system approval list
agent-system approval approve
agent-system audit inspect
agent-system health
```

# 49. Configuração

Precedência geral:

```text
defaults → config → environment → project policy → task policy → explicit user instruction
```

Exceto quando policy de segurança superior impedir.

# 50. Secrets

Usar environment, secret manager, credential store ou vault. Segredos não devem ser versionados.

# 51. Testing

Deve haver:

- unit tests;
- integration tests;
- workflow tests;
- security tests;
- evaluation tests;
- golden tests;
- recovery tests.

# 52. Reprodutibilidade

Execuções importantes devem registrar:

- versão do agente;
- workflow;
- modelo/provider;
- policy;
- prompt/template version;
- contexto;
- ferramentas;
- configuração;
- timestamps;
- artefatos.

# 53. Evaluation

Métricas recomendadas:

- task success rate;
- factuality;
- citation coverage;
- retrieval precision/recall;
- tool success;
- failure rate;
- latency;
- cost;
- approval rate;
- unnecessary-action rate.

Não otimizar apenas qualidade textual.

# 54. Graceful Degradation

- sem LLM remoto → modelo local quando possível;
- sem vector DB → BM25 + grafo;
- sem Obsidian → filesystem/Git/CLI;
- sem MCP → adapters;
- sem LangGraph → workflow equivalente;
- sem OpenClaw → runtime equivalente;
- sem PostgreSQL → storage local em instalações pequenas, preservando contratos.

# 55. MVP

Stack de referência:

```text
Docker
Control Plane
Orchestrator
Agent Registry
LiteLLM
OpenClaw
OpenHands
LangGraph
MCP quando aplicável
CHAOS
Git
Markdown/YAML/CSV
ai-memory
PostgreSQL
BM25
Graphify
```

Inicialmente não obrigatórios: Qdrant, Redis, Langfuse, Voice, WhatsApp, Web UI complexa, Neo4j e blockchain.

# 56. Roadmap

### Fase 1 — Foundation
Control Plane, Registry, Protocol, CHAOS integration, Git, CLI, validation.

### Fase 2 — Memory
Sessions, ai-memory, Context Builder, provenance.

### Fase 3 — Coding
Coding runtime, sandbox, project adapter.

### Fase 4 — Personal Assistant
Schedules, reminders, Telegram/WhatsApp, briefing.

### Fase 5 — Workflow
Checkpoints, HITL, retries e recovery.

### Fase 6 — Observability
Metrics, tracing, audit e cost.

### Fase 7 — Local AI
Ollama com vLLM como alternativa e routing híbrido.

### Fase 8 — Advanced Retrieval
Graph/vector se justificados.

### Fase 9 — Voice
STT/TTS.

### Fase 10 — Optimization
Routing, cache, evaluation e custo.

# 56.1 Política normativa de implementação de tecnologias

ORDER é tecnologicamente agnóstico, mas a implementação de referência deve possuir **ferramentas recomendadas**. Isso resolve a tensão entre "vendor-neutral" e "não deixar a LLM escolher arbitrariamente uma stack".

## 56.1.1 Classificação

Cada capacidade pode ter uma ferramenta:

- **RECOMMENDED** — escolha padrão e primeira opção da implementação;
- **ALTERNATIVE** — substituto compatível;
- **EXPERIMENTAL** — opção ainda não adotada como padrão;
- **NOT REQUIRED** — fora do baseline.

Essa classificação nunca transforma a ferramenta em contrato arquitetural.

## 56.1.2 Comportamento obrigatório da LLM implementadora

Ao implementar ORDER, a LLM deve:

1. identificar a capacidade solicitada;
2. consultar a matriz tecnológica;
3. usar a ferramenta RECOMMENDED por padrão;
4. verificar disponibilidade e compatibilidade;
5. se a recomendada não puder ser utilizada, informar o motivo;
6. apresentar as ALTERNATIVES compatíveis;
7. perguntar ao usuário qual alternativa deseja quando não houver uma política de fallback previamente autorizada;
8. não substituir silenciosamente uma tecnologia relevante;
9. registrar a decisão tecnológica;
10. implementar a tecnologia atrás de uma interface/adaptador;
11. manter os contratos de ORDER independentes da ferramenta escolhida.

### 56.1.3 Fallback previamente autorizado

Uma implantação pode declarar uma política explícita:

```yaml
technology_policy:
  unavailable_recommended:
    action: ask_user
  authorized_fallbacks:
    - capability: local_model_runtime
      from: ollama
      to: vllm
      action: automatic
      require_log: true
```

Somente substituições explicitamente autorizadas podem ocorrer sem nova pergunta ao usuário.

## 56.1.4 Escolha explícita do usuário

Se o usuário escolher uma ALTERNATIVE válida, ORDER deve utilizá-la e registrar:

- capability;
- recommended tool;
- selected tool;
- classification;
- version, quando relevante;
- reason;
- compatibility result;
- date;
- user-selected flag.

A escolha não deve exigir alterações nos contratos de Agent Protocol, Handoff, Workflow, Model Policy, Permission, Approval, Audit ou Context Builder.

## 56.1.5 Contrato acima da ferramenta

```text
ORDER Contract
      |
      +-------------------+
      |                   |
 Recommended          Alternative
 implementation       implementation
      |                   |
      +---------+---------+
                |
             Adapter
                |
        Capability Interface
```

A ferramenta é um binding de implantação. O contrato é o ativo arquitetural.

## 56.1.6 Modelos de IA: nenhuma marca recomendada

ORDER **não recomenda nenhum LLM/provider/model específico**. Não devem ser tratados como ferramentas recomendadas nomes de fornecedores ou produtos de LLM.

A arquitetura deve permanecer:

```text
Task
  ↓
Task Classification
  ↓
Model Policy
  ↓
Model Router
  ↓
Model Gateway
  ↓
Provider / Runtime / Model
```

O Model Registry descreve capacidades, restrições, custo, latência, contexto e modalidades. A seleção concreta é configurável e substituível.

# 57. Matriz tecnológica de referência

As ferramentas abaixo são **bindings de implementação**, não contratos arquiteturais.

| Capacidade | RECOMMENDED | ALTERNATIVES | EXPERIMENTAL / NOT REQUIRED |
|---|---|---|---|
| Runtime pessoal | OpenClaw | runtime pessoal equivalente | outros runtimes |
| Runtime de coding | OpenHands | runtime de engenharia equivalente | outros coding agents |
| Workflow orchestration | LangGraph | motor de workflow equivalente | outros |
| Model Gateway | LiteLLM | OpenRouter ou gateway próprio | outros gateways |
| Interoperabilidade de ferramentas | MCP quando aplicável | APIs, CLI, adapters diretos | protocolos futuros |
| Memória operacional | ai-memory | adapter/implementação compatível | soluções futuras |
| Knowledge UI | Obsidian | VSCode, editor Markdown, UI própria | — |
| Versionamento | Git | outro VCS compatível | — |
| Estado operacional | PostgreSQL | SQLite ou banco relacional compatível | — |
| Busca lexical | BM25 | implementação FTS/BM25 equivalente | — |
| Grafo derivado | Graphify | Neo4j, FalkorDB | outros graph engines |
| Vector retrieval | **não obrigatório** | Qdrant ou vector DB equivalente | — |
| Observabilidade | OpenTelemetry + stack compatível | Langfuse ou stack equivalente | outras plataformas |
| Local model runtime | Ollama | vLLM | outros runtimes |
| Canal de notificação | adapter de canal | Telegram, WhatsApp ou outro canal compatível | novos canais |
| External PM | não recomendado como fonte de verdade | integração via adapter | — |
| Blockchain anchoring | não requerido | serviço de timestamp/âncora externo | blockchain |

## 57.1 Stack de implementação recomendada

Quando o ambiente não impuser restrições, a implementação inicial deve preferir:

```text
ORDER
├── Control Plane / Orchestrator próprio segundo os contratos
├── OpenClaw                  # runtime pessoal
├── OpenHands                 # coding runtime
├── LangGraph                 # workflows complexos
├── LiteLLM                   # Model Gateway
├── MCP                       # interoperabilidade quando aplicável
├── ai-memory                 # memória operacional
├── PostgreSQL                # estado operacional
├── BM25                      # busca lexical
├── Graphify                  # grafo derivado
├── Ollama                    # runtime local de modelos
├── Git                       # versionamento
└── CHAOS                     # conhecimento e estado canônico
```

Isso é uma **stack recomendada**, não uma dependência estrutural. Cada item pode ser substituído por uma alternativa compatível conforme a política da seção 56.1.

## 57.2 O que não é recomendado como requisito inicial

- Qdrant/vector DB sem justificativa mensurável;
- Neo4j/FalkorDB quando Graphify atende ao requisito;
- blockchain como persistência/auditoria primária;
- PM SaaS como fonte de verdade;
- um fornecedor específico de LLM;
- canais específicos como dependência do núcleo;
- Web UI complexa antes de os contratos e workflows estarem estáveis.

# 58. Anti-padrões

Não implementar:

- agente monolítico que faz tudo;
- modelo como controlador de segurança;
- LLM como banco;
- vector DB como única memória;
- runtime como source of truth;
- MCP como dependência arquitetural;
- protocolo preso a provider;
- ação irreversível automática;
- ausência de auditoria;
- retries infinitos;
- workflows sem idempotência;
- acesso irrestrito a ferramentas;
- microserviços excessivos no MVP.

# 59. Critérios de adoção/removal

Uma tecnologia nova deve demonstrar benefício em qualidade, desempenho, segurança, interoperabilidade ou redução de trabalho que justifique custo, complexidade e manutenção.

# 60. Compatibilidade

Implementações diferentes são equivalentes se preservarem:

1. Agent Protocol;
2. Handoff Protocol;
3. workflow semantics;
4. model routing semantics;
5. permission semantics;
6. approval semantics;
7. CHAOS schemas;
8. audit semantics;
9. provenance;
10. idempotency;
11. graceful degradation.

# 61. Acceptance Tests

**AT-01 — Agent registration:** agente é registrado e descoberto por capability.

**AT-02 — Routing:** model compatível com policy é selecionado.

**AT-03 — Safety:** ação irreversível gera approval.

**AT-04 — Manual override:** modelo explicitamente escolhido é respeitado quando permitido.

**AT-05 — Policy precedence:** override não viola segurança/capacidade.

**AT-06 — Handoff:** segundo agente reconstrói contexto do handoff.

**AT-07 — Retry:** falha transitória não duplica operação idempotente.

**AT-08 — Audit:** alteração relevante gera evento.

**AT-09 — CHAOS independence:** funciona sem Obsidian.

**AT-10 — Provider independence:** troca de provider não altera agentes.

**AT-11 — Runtime independence:** troca de runtime preserva contratos.

**AT-12 — Vector independence:** remover vetor não quebra o sistema.

**AT-13 — Human approval:** A3/A4 não executa antes de aprovação.

**AT-14 — Recovery:** workflow interrompido retoma checkpoint ou falha explicitamente.

**AT-15 — Provenance:** respostas derivadas de CHAOS carregam referências.

# 62. Definition of Done

ORDER v2.0 está implementado quando:

- agentes são registráveis;
- tasks/jobs são rastreáveis;
- workflows têm estado;
- routing tem policy;
- providers são abstraídos;
- ferramentas possuem permissões;
- ações críticas exigem aprovação;
- contexto é recuperável;
- memória operacional é separada do source of truth;
- auditoria funciona;
- falhas são recuperáveis;
- execução é observável;
- código pode ser isolado;
- canais são substituíveis;
- nenhum provider é estruturalmente obrigatório;
- acceptance tests passam.

# 63. Golden Architecture

```text
                         USER / EVENTS
                              |
                              v
                    +-------------------+
                    |   Control Plane   |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    |    Orchestrator   |
                    +---------+---------+
                              |
        +---------------------+----------------------+
        |                     |                      |
        v                     v                      v
 Personal Assistant      Project Manager       Specialist Agents
        |                     |                      |
        +---------------------+----------------------+
                              |
                              v
                    +-------------------+
                    | Context Builder   |
                    +---------+---------+
                              |
                +-------------+-------------+
                |             |             |
                v             v             v
              CHAOS         Memory       Retrieval
                |             |             |
                +-------------+-------------+
                              |
                              v
                    +-------------------+
                    |   Model Policy    |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    |    Model Router   |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    |   Model Gateway   |
                    +---------+---------+
                              |
                  Local / Cloud Providers

Agents → Tool Registry → MCP / APIs / CLI / Runtimes
   |             |             |
   +-------------+-------------+
                 |
       Permission / Approval
                 |
           Audit / Observability
```

# 64. Golden Rules

1. CHAOS é a verdade persistente.
2. ORDER é executor/orquestrador.
3. LLM é componente de raciocínio, não autoridade.
4. Model Policy define requisitos.
5. Model Router seleciona dentro das policies.
6. Model Gateway abstrai providers.
7. Override manual respeita segurança.
8. Agentes operam por contratos.
9. Ferramentas declaram risco e efeitos.
10. Ações irreversíveis exigem aprovação.
11. Memória operacional não substitui registros canônicos.
12. Views são regeneráveis.
13. IDs são estáveis.
14. Provenance é obrigatória para informação crítica.
15. Auditoria permite reconstrução.
16. Vector DB é otimização.
17. MCP é interoperabilidade.
18. Obsidian é interface.
19. Blockchain é apenas possível âncora externa.
20. Toda tecnologia deve ser substituível.

# 65. Relação formal

```text
CHAOS
= persistent knowledge + state + provenance + project management

ORDER
= execution + orchestration + intelligence + automation

Project repositories
= source code + engineering history
```

Fluxo principal:

```text
User
 ↓
Personal Assistant
 ↓
Orchestrator
 ↓
Specialist Agent
 ↓
Context Builder
 ↓
CHAOS
 ↓
Model Policy
 ↓
Model Router
 ↓
Model Gateway
 ↓
LLM
 ↓
Tool / Runtime
 ↓
Validation
 ↓
CHAOS update
 ↓
Audit
 ↓
Notification
```

# 66. Substituibilidade

A arquitetura deve permitir substituir individualmente qualquer ferramenta de implementação — incluindo Ollama, vLLM, LiteLLM, OpenRouter, OpenClaw, OpenHands, LangGraph, MCP, Qdrant, Obsidian, PostgreSQL e canais — sem reescrever os contratos centrais. Nenhum LLM/provider específico é recomendado ou estrutural.

O ativo arquitetural principal são protocolos, schemas, estado, políticas, proveniência e interfaces — não uma ferramenta específica.


# 67. Critérios formais de substituição de tecnologia

Uma substituição é considerada compatível quando:

1. preserva a interface da capacidade;
2. preserva entradas e saídas semânticas ou fornece adapter explícito;
3. não altera IDs e schemas do CHAOS;
4. não altera o Agent Protocol;
5. não altera a semântica de permissões e aprovações;
6. não introduz dependência estrutural de fornecedor;
7. possui testes de compatibilidade;
8. possui procedimento de rollback quando aplicável;
9. registra a decisão tecnológica;
10. mantém observabilidade e auditoria equivalentes.

Se algum requisito não puder ser preservado, a substituição deve ser tratada como **mudança arquitetural**, e não como simples troca de ferramenta.

# 68. Regra de implementação final

> **Use a ferramenta RECOMMENDED. Se ela não puder ser usada, não escolha silenciosamente uma ALTERNATIVE: explique a restrição e pergunte ao usuário qual alternativa deseja, salvo quando uma política de fallback previamente autorizada determinar a substituição automática.**

> **Qualquer ferramenta pode ser substituída sem quebrar ORDER, desde que o contrato da capacidade permaneça estável.**

> **Nenhum fornecedor de LLM é recomendado. ORDER seleciona capacidades e usa Model Policy → Model Router → Model Gateway para manter a camada de modelos substituível.**
