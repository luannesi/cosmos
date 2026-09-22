# Cenário E — Implementação GitHub-First Multi-Dispositivo
## Especificação Completa de Arquitetura e Implantação

**Versão:** 1.0  
**Data:** 2026-09-13  
**Status:** Especificação de Implementação  
**Objetivo:** Implementar CHAOS v2.1 e ORDER v2.1 em ambiente multi-dispositivo (celular, desktop, web, VSCode) usando GitHub como orquestrador central, sem restrição de conectores MCP da empresa.

---

## 1. Visão Geral Executiva

O Cenário E implementa CHAOS e ORDER através de um repositório Git privado hospedado no GitHub, funcionando como:

- **Camada Persistente:** CHAOS — conhecimento, estado, decisões, auditoria (Markdown + YAML + Git)
- **Camada Orquestra:** ORDER — workflows, agentes, execução (Python + GitHub Actions + Claude APIs)
- **Sincronização Multi-Dispositivo:** Automática via Git + webhooks + GitHub Actions (< 60 segundos)
- **Agnóstico de Ferramenta:** Claude Mobile, Desktop, Web, VSCode — todos acessam o mesmo repositório
- **Zero Custo:** GitHub free plan + Claude API (conforme existente)

### Benefícios Comprovados

| Dimensão | Benefício |
|---|---|
| **Especificação** | Honra 100% dos contratos CHAOS v2.1 e ORDER v2.1 |
| **Multi-Dispositivo** | Sincronização automática e confiável em <60s |
| **Celular** | Suporta via GitHub Mobile + Claude Mobile + webhooks |
| **Offline-First** | Edita localmente, sincroniza quando online |
| **Auditoria** | Git log = hash chain verificável (`git log --all`) |
| **Escalabilidade** | Adicionar dispositivo/pessoa = clone + SSH key |
| **Substituibilidade** | Trocar Git, GitHub, Claude, Python — CHAOS permanece |
| **Sem MCP Externo** | Funciona dentro restrição de segurança da empresa |

---

## 2. Topologia de Repositórios

```text
github.com/seu-usuario/workspace (PRIVATE)
│
├── chaos/                         # Conhecimento, estado, decisões, auditoria
│   ├── README.md
│   ├── inbox/                     # Captura bruta
│   ├── wiki/                      # Conhecimento consolidado
│   ├── areas/                     # Áreas de conhecimento (PARA)
│   ├── resources/                 # Recursos (PARA)
│   ├── projects/                  # Projetos temporários
│   │   ├── PRJ-001.yaml
│   │   ├── PRJ-001/
│   │   │   ├── README.md
│   │   │   ├── tasks/
│   │   │   ├── decisions/
│   │   │   └── artifacts/
│   │   └── ...
│   ├── tasks/                     # Tarefas globais
│   │   └── TSK-*.yaml
│   ├── milestones/                # Milestones
│   │   └── MS-*.yaml
│   ├── risks/                     # Riscos e mitigação
│   │   └── RSK-*.yaml
│   ├── decisions/                 # Decisões formalizadas
│   │   └── DEC-*.yaml
│   ├── dependencies/              # Dependências entre entidades
│   │   └── DEP-*.yaml
│   ├── deliverables/              # Entregas
│   │   └── DLV-*.yaml
│   ├── meetings/                  # Atas de reunião
│   │   └── MTG-*.yaml
│   ├── sources/                   # Fontes primárias
│   │   └── SRC-*.yaml
│   ├── metadata/                  # Schemas, registries, policies
│   │   ├── schemas/
│   │   │   ├── chaos.schema.json
│   │   │   ├── agent.schema.json
│   │   │   └── ...
│   │   ├── registries/
│   │   │   └── registry.yaml      # Índice de entidades
│   │   └── policies/
│   │       └── approval.yaml
│   ├── indexes/                   # Indexes derivados (REGENERÁVEIS)
│   │   ├── by-project.md
│   │   ├── by-status.md
│   │   ├── full-text.json
│   │   └── graph.json
│   ├── graph/                     # Representação de grafo
│   │   └── graph.graphml          # Ou GraphML/JSON
│   ├── audit/                     # Auditoria e logs
│   │   ├── changes.log            # Changelog automático
│   │   └── validations.log        # Validações CI/CD
│   └── archive/                   # Conteúdo inativo
│       └── ...
│
├── agent-system/                  # Orquestração e execução (ORDER)
│   ├── README.md
│   ├── agents/                    # Definições de agentes
│   │   ├── agents.yaml            # Registry
│   │   ├── project-manager/
│   │   ├── researcher/
│   │   ├── decision-analyst/
│   │   └── ...
│   ├── workflows/                 # Definições de workflow
│   │   ├── workflows.yaml         # Registry
│   │   ├── task-execution.yaml
│   │   ├── decision-making.yaml
│   │   └── ...
│   ├── policies/                  # Políticas de execução
│   │   ├── model-policy.yaml      # Seleção de modelos
│   │   ├── risk-policy.yaml       # Classificação de risco
│   │   ├── approval-policy.yaml   # Aprovações
│   │   └── permission-policy.yaml # Permissões
│   ├── scripts/                   # Executáveis Python
│   │   ├── executor.py            # Main orchestrator
│   │   ├── validator.py           # Valida CHAOS
│   │   ├── indexer.py             # Reconstrói indexes
│   │   ├── model-router.py        # Seleciona modelo
│   │   ├── approval-handler.py    # Processa aprovações
│   │   └── webhook-handler.py     # Recebe webhooks
│   ├── tools/                     # Ferramenta registry
│   │   ├── tools.yaml
│   │   ├── file_system.py
│   │   ├── claude_api.py
│   │   └── ...
│   ├── requirements.txt           # Python dependencies
│   ├── .github/workflows/         # GitHub Actions
│   │   ├── validate-chaos.yaml    # Valida schemas a cada 30 min
│   │   ├── rebuild-indexes.yaml   # Reconstrói indexes
│   │   ├── audit-log.yaml         # Escreve audit.log
│   │   └── notify.yaml            # Envia notificações
│   ├── hooks/                     # Git hooks
│   │   ├── post-merge             # Rebuild indexes + validate
│   │   └── pre-commit             # Lint YAML + schemas
│   └── tests/                     # Testes de validação
│       └── test_schemas.py
│
└── README.md                      # Root — como começar

```

### Separação de Responsabilidades

| Diretório | Proprietário | Lê | Escreve | Síncrono | Frequência |
|---|---|---|---|---|---|
| `chaos/` | Humanos + Agentes | Agentes, Humanos | Agentes via ORDER | Não | Real-time |
| `chaos/indexes/` | GitHub Actions | Tudo | GitHub Actions | Não | 30 min |
| `chaos/audit/` | GitHub Actions | Tudo | GitHub Actions | Não | A cada commit |
| `agent-system/` | Infraestrutura | GitHub Actions | Operadores | Sim | Manual |
| `.github/workflows/` | DevOps | GitHub Actions | DevOps | Sim | Manual |

---

## 3. Fluxo de Dados Multi-Dispositivo

### 3.1 Fluxo Completo: Celular → Execução → Desktop → Sincronização

```
┌─────────────────────────────────────────────────────────────────────┐
│ CELULAR (Claude Mobile + GitHub Mobile App)                         │
├─────────────────────────────────────────────────────────────────────┤
│ 1. Usuário escreve em Claude Mobile: "Cria tarefa X do projeto Y"   │
│ 2. Claude gera proposta de TSK em YAML (estrutura CHAOS)            │
│ 3. Usuário aprova e copia (ou clica link) → GitHub Mobile           │
│ 4. GitHub Mobile abre formulário para criar arquivo                 │
│ 5. Usuário edita e comita em chaos/tasks/TSK-NNN.yaml               │
│ 6. Git push para origin/main (webhook configurado)                  │
└──────────────────┬────────────────────────────────────────────────┘
                   │
                   ├─→ WEBHOOK GITHUB → servidor de eventos
                   │
          ┌────────v────────────────────────────────────────┐
          │ GITHUB ACTIONS (CI/CD Automation)              │
          ├────────────────────────────────────────────────┤
          │ 1. Trigger: push em chaos/tasks/*.yaml         │
          │ 2. Job: validate-chaos                         │
          │    - Validar schema JSON contra arquivo YAML   │
          │    - Verificar IDs únicos e imutáveis          │
          │    - Detectar conflitos em dependências        │
          │ 3. Se validação falhar: reject commit + notify │
          │ 4. Se passar: Auto-commit indexação            │
          │    - rebuild-indexes.yaml roda                 │
          │    - Escreve chaos/indexes/by-status.md        │
          │    - Escreve chaos/indexes/graph.json          │
          │    - Escreve chaos/audit/changes.log           │
          │ 5. Push automático: chaos/indexes/* + audit/*  │
          └────────┬─────────────────────────────────────┘
                   │
          ┌────────v──────────────────────────────────┐
          │ WEBHOOK → EXECUTOR (Python + Claude)     │
          ├──────────────────────────────────────────┤
          │ 1. Escuta: chaos/tasks/TSK-NNN.yaml      │
          │ 2. Parse YAML → Python dict              │
          │ 3. Lê Order de execução do workflow:     │
          │    (chaos/projects/PRJ-YYY/workflow.yaml)│
          │ 4. Inicia job:                            │
          │    executor.py --task=TSK-NNN           │
          └────────┬──────────────────────────────────┘
                   │
          ┌────────v──────────────────────────────────┐
          │ EXECUTOR (pode rodar desktop/VSCode/cloud)│
          ├──────────────────────────────────────────┤
          │ 1. Lê TSK-NNN.yaml (contexto completo)   │
          │ 2. Classifica risco via risk-policy.yaml │
          │ 3. Seleciona modelo via model-policy +   │
          │    model-router.py                       │
          │ 4. Se risco alto: cria DEC-XXX.yaml      │
          │    com pedido de aprovação (HITL)        │
          │ 5. Se risco baixo: executa com Claude    │
          │ 6. Escreve resultado em:                 │
          │    chaos/projects/PRJ-YYY/results/      │
          └────────┬──────────────────────────────────┘
                   │
┌──────────────────v─────────────────────────────────┐
│ DESKTOP (VSCode + Claude Desktop)                 │
├────────────────────────────────────────────────────┤
│ 1. File watcher detecta mudança em chaos/         │
│ 2. VSCode recarrega e mostra novo task/result     │
│ 3. Usuário desktop lê contexto (índices)          │
│ 4. Se HITL necessária: aprova/rejeita DEC         │
│ 5. Git pull automático (opcional: post-merge hook)│
│ 6. Índices e audit logs já regenerados            │
└────────────────────────────────────────────────────┘
```

**Tempo Total:** ~45–60 segundos do celular até visibilidade no desktop.

### 3.2 Fases de Sincronização

| Fase | Evento | Duração | Estado |
|---|---|---|---|
| **P1** | Celular git push | <5s | TSK criada em origin |
| **P2** | GitHub recebe + webhook | <2s | Evento enfileirado |
| **P3** | GitHub Actions CI | <10s | Validação + indexação |
| **P4** | Auto-commit de indexes | <5s | Indexes atualizadas em origin |
| **P5** | Desktop git pull | <5s | Indexes visíveis no VSCode |
| **P6** | Executor detecta nova tarefa | <5s | Job iniciado |
| **P7** | Executor executa + escreve resultado | <20s | Resultado em chaos/projects/.../results/ |
| **P8** | Git auto-commit (hook) | <5s | Resultado commitado em origin |
| **Total** | Celular → Desktop vê resultado | **45–60s** | Sincronizado globalmente |

---

## 4. CHAOS — Implementação Camada de Conhecimento

### 4.1 PMMS (Project Management Markdown Schema)

Toda entidade CHAOS MUST conter:

```yaml
# chaos/tasks/TSK-001.yaml
id: "TSK-001"
type: "task"
schema_version: "2.0"
created_at: "2026-09-13T10:00:00Z"
updated_at: "2026-09-13T10:00:00Z"
created_by: "claude@workspace"
updated_by: "claude@workspace"

# Conteúdo
title: "Implementar autenticação OAuth2"
description: |
  Adicionar suporte OAuth2 para Google e GitHub
  como alternativa ao login baseado em email.
project: "PRJ-001"
area: "security"
status: "in_progress"
priority: "high"

# Rastreabilidade
depends_on:
  - "TSK-002"
  - "DEP-015"
blocks:
  - "TSK-003"
  - "MS-001"

# Risco e aprovação
risk_level: "reversible-medium"
requires_approval: false
approval_id: ~

# Esforço e deadline
effort_hours: 16
assigned_to: []
deadline: "2026-09-25"

# Decisão relacionada
related_decision: "DEC-042"

# Artefatos
artifacts:
  - "chaos/projects/PRJ-001/design/oauth2-flow.md"
  - "chaos/projects/PRJ-001/specs/oauth2-api.yaml"

# Conflito (não pode ser descartado silenciosamente)
has_conflict: false
conflicts: []

# Tags e categorização
tags:
  - "security"
  - "external-integration"
  - "phase-2"

# Observações
notes: |
  - Usar biblioteca PyOAuth2 v5.2+
  - Testar com Google + GitHub (não apenas um)
  - Incluir fallback para auth baseada em email
```

**Invariantes:**
- `id` é imutável e nunca reutilizado
- `created_at` não muda
- `updated_at` = timestamp do último push
- `schema_version` permite evolução
- `created_by`/`updated_by` rastreiam origem
- Conflitos (`has_conflict: true`) bloqueiam auto-execução
- `risk_level` governa aprovação necessária

### 4.2 Decisões Formais (DEC)

```yaml
# chaos/decisions/DEC-042.yaml
id: "DEC-042"
type: "decision"
schema_version: "2.0"
created_at: "2026-09-12T14:30:00Z"
title: "Autenticação: OAuth2 vs JWT+Custom"

# Contexto
context: |
  Sistema precisa suportar login de múltiplos provedores
  (Google, GitHub, Microsoft) mantendo fallback local.

# Alternativas analisadas
alternatives:
  - name: "Option A: OAuth2 (Google/GitHub/Microsoft SDKs)"
    pros:
      - "Externalize segurança para provedores"
      - "Suporte multi-provider nativo"
      - "Menos manutenção de credenciais"
    cons:
      - "Depende disponibilidade de provedores"
      - "Latência de rede aumenta login"
    risk: "low"
    estimate_effort_hours: 16

  - name: "Option B: JWT + Custom Middleware"
    pros:
      - "Controle total de segurança"
      - "Melhor performance (cache local)"
      - "Funciona offline com token armazenado"
    cons:
      - "Manutenção complexa de chaves"
      - "Risco de vazamento de JWT"
    risk: "reversible-high"
    estimate_effort_hours: 24

  - name: "Option C: Hybrid (OAuth2 + JWT cache)"
    pros:
      - "Combina benefícios de A e B"
      - "Fallback automático"
    cons:
      - "Complexidade ainda maior"
    risk: "reversible-medium"
    estimate_effort_hours: 28

# Critérios de decisão
criteria:
  - name: "Segurança"
    weight: 0.35
  - name: "Manutenibilidade"
    weight: 0.30
  - name: "Performance"
    weight: 0.20
  - name: "Esforço"
    weight: 0.15

# Scoring
scores:
  option_a: 8.5
  option_b: 7.2
  option_c: 8.1

# Decisão tomada
chosen_option: "Option A"
rationale: |
  OAuth2 oferece melhor balanço entre segurança delegada
  e baixa manutenção. Provedores (Google/GitHub/Microsoft)
  já enfrentam escalabilidade e segurança, liberando-nos
  para focar em UX.
  
  JWT cache é postergado para v2.0 se performance exigir.

approved_by: "usuario@empresa"
approved_at: "2026-09-12T16:00:00Z"

# Rastreamento
related_tasks:
  - "TSK-001"
  - "TSK-002"
related_risks:
  - "RSK-042"

# Reversibilidade
reversible: true
rollback_plan: |
  Se OAuth2 falhar ou provedores saírem,
  implementar fallback JWT em <= 8h.

status: "approved"
```

### 4.3 Riscos (RSK)

```yaml
# chaos/risks/RSK-042.yaml
id: "RSK-042"
type: "risk"
schema_version: "2.0"
created_at: "2026-09-10T09:00:00Z"
title: "Risco: Google/GitHub OAuth outdisponível"

description: |
  Se provedores OAuth2 ficarem indisponíveis, usuários não conseguem fazer login.
  
probability: "low"
impact: "critical"
risk_level: "external-impact"

# Mitigação
mitigations:
  - name: "Fallback JWT"
    status: "planned"
    effort_hours: 8
    related_task: "TSK-025"
    
  - name: "Cache de tokens (24h TTL)"
    status: "in_progress"
    effort_hours: 4
    related_task: "TSK-026"
    
  - name: "Status page + alertas"
    status: "pending"
    effort_hours: 2
    related_task: "TSK-027"

# Triggering
triggers:
  - "Google services unavailable (status.google.com)"
  - "GitHub OAuth service down"
  - "Network latency > 5s"

# Responsabilidade
owner: "tech-lead@empresa"
last_reviewed: "2026-09-12T14:00:00Z"

related_decision: "DEC-042"
related_project: "PRJ-001"
```

### 4.4 Dependências (DEP)

```yaml
# chaos/dependencies/DEP-015.yaml
id: "DEP-015"
type: "dependency"
schema_version: "2.0"
created_at: "2026-09-10T10:00:00Z"

# Entidades relacionadas
from_entity: "TSK-002"  # Setup API Gateway
from_type: "task"

to_entity: "TSK-001"    # Implementar OAuth2
to_type: "task"

# Tipo de dependência
dependency_type: "blocks"  # TSK-002 bloqueia TSK-001
description: |
  OAuth2 requer API Gateway configurado para rotear
  chamadas de callback dos provedores.

# Risco de violação
risk_if_violated: "OAuth2 não consegue receber callbacks"
severity: "critical"

# Status
status: "open"
estimated_unblock_date: "2026-09-18"

related_project: "PRJ-001"
```

### 4.5 Audit Log (Automático via GitHub Actions)

```text
# chaos/audit/changes.log
# Regenerado a cada 30 minutos via GitHub Actions

2026-09-13T10:45:00Z | COMMIT | abc1234 | TSK-001 created | alice@workspace
2026-09-13T10:45:10Z | ACTION | validate-chaos | ✓ PASS schema | github-actions
2026-09-13T10:45:15Z | ACTION | rebuild-indexes | indexes updated | github-actions
2026-09-13T10:46:00Z | COMMIT | def5678 | DEC-042 approved | bob@workspace
2026-09-13T10:46:10Z | ACTION | validate-chaos | ✓ PASS schema | github-actions
2026-09-13T10:46:15Z | ACTION | rebuild-indexes | indexes updated | github-actions
2026-09-13T10:50:30Z | JOB | executor.py | TSK-001 execution started | executor
2026-09-13T10:51:15Z | JOB | executor.py | TSK-001 executed (status: in_progress) | executor
2026-09-13T10:51:20Z | COMMIT | ghi9012 | TSK-001 result committed | executor
...
```

**Garantias:**
- Cada linha = evento verificável
- `git log --all` = hash chain (não precisa blockchain)
- Imutável (commit já feito não pode ser alterado)
- Auditor pode reconstruir estado completo de qualquer ponto no tempo

### 4.6 Indexes (Deriváveis, Regeneráveis)

```markdown
# chaos/indexes/by-status.md
# Gerado automaticamente a cada 30 minutos

## ✅ Completed (5)
- TSK-001: Autenticação SSH
- TSK-015: Validação de email
- TSK-028: Deploy para produção
- DLV-002: Relatório Q3
- MS-001: Alpha release

## 🔄 In Progress (8)
- TSK-002: Setup API Gateway (Alice, 60% → deadline 2026-09-18)
- TSK-003: Testes OAuth2 (Bob, 30% → deadline 2026-09-25)
- TSK-025: Fallback JWT (Carlos, 15% → deadline 2026-09-22)
...

## ⏳ Todo (12)
- TSK-026: Cache de tokens
- TSK-027: Status page
...

## 🚫 Blocked (2)
- TSK-004: Integração Stripe (bloqueado por: TSK-002)
- TSK-005: Configurar webhook (bloqueado por: DEP-015)

---

*Última atualização: 2026-09-13T11:00:00Z via GitHub Actions*
```

**Propriedade crítica:** Indexes podem ser deletados e regenerados sem perda de dados. Source of Truth permanece em arquivos `.yaml` canônicos.

---

## 5. ORDER — Implementação Camada de Orquestração

### 5.1 Agent Registry

```yaml
# agent-system/agents/agents.yaml
version: "2.0"
agents:
  - id: "agent.project-manager"
    name: "Project Manager"
    version: "2.0"
    description: "Gerencia projetos, tarefas, dependências e timelines"
    
    capabilities:
      - "project.read"
      - "project.write"
      - "task.read"
      - "task.write"
      - "milestone.read"
      - "dependency.read"
      - "risk.read"
    
    tools:
      - "read_yaml"
      - "write_yaml"
      - "validate_schema"
      - "git_commit"
    
    model_policy: "default"  # Referência a policy
    risk_policy: "standard"  # Risco baixo/médio
    approval_policy: "low-barrier"
    
    input_schema:
      type: "object"
      properties:
        action: 
          type: "string"
          enum: ["create_project", "create_task", "update_status", "add_dependency"]
        project_id: { type: "string" }
        task_id: { type: "string" }
        data: { type: "object" }
      required: ["action"]
    
    output_schema:
      type: "object"
      properties:
        status: { type: "string", enum: ["success", "failed", "blocked"] }
        result: { type: "object" }
        artifact_ids: { type: "array", items: { type: "string" } }

  - id: "agent.researcher"
    name: "Researcher"
    version: "2.0"
    description: "Pesquisa, analisa contexto, extrai informações"
    
    capabilities:
      - "source.read"
      - "wiki.read"
      - "task.read"
      - "decision.read"
    
    tools:
      - "read_yaml"
      - "full_text_search"
      - "graph_query"
      - "claude_api"
    
    model_policy: "reasoning"  # Precisa de modelo com boa reasoning
    risk_policy: "read-only"
    approval_policy: "none"
    
    input_schema:
      type: "object"
      properties:
        query: { type: "string" }
        scope: { type: "string", enum: ["project", "global"] }
        project_id: { type: "string" }
    
    output_schema:
      type: "object"
      properties:
        findings: { type: "string" }
        sources: { type: "array", items: { type: "string" } }
        confidence: { type: "number", minimum: 0, maximum: 1 }

  - id: "agent.decision-analyst"
    name: "Decision Analyst"
    version: "2.0"
    description: "Analisa alternativas, estrutura decisões, recomenda opções"
    
    capabilities:
      - "decision.read"
      - "decision.write"
      - "risk.read"
      - "alternative.analyze"
    
    tools:
      - "read_yaml"
      - "write_yaml"
      - "claude_api"
      - "git_commit"
    
    model_policy: "reasoning"
    risk_policy: "medium-barrier"
    approval_policy: "medium-barrier"  # HITL para decisões críticas
    
    input_schema:
      type: "object"
      properties:
        decision_type: { type: "string" }
        context: { type: "string" }
        alternatives: { type: "array", items: { type: "string" } }
    
    output_schema:
      type: "object"
      properties:
        analysis: { type: "string" }
        recommendation: { type: "string" }
        reasoning: { type: "string" }
        confidence: { type: "number" }
```

### 5.2 Workflow Registry

```yaml
# agent-system/workflows/workflows.yaml
version: "2.0"
workflows:
  - id: "wf.task-execution"
    name: "Task Execution Workflow"
    version: "2.0"
    description: "Executa tarefa desde classificação até conclusão"
    
    trigger: "task.created"  # Ou manual
    
    steps:
      - step_id: "classify-risk"
        agent: "agent.risk-classifier"
        action: "classify_by_policy"
        input:
          task_id: "{{ task.id }}"
        on_success: "next"
        on_failure: "notify_admin"
      
      - step_id: "check-approval"
        type: "conditional"
        condition: "risk_level >= medium"
        true_path: "request-approval"
        false_path: "select-model"
      
      - step_id: "request-approval"
        type: "approval"
        description: "Solicitar aprovação de tarefa"
        assignee: "project_owner"
        timeout_seconds: 3600
        on_approved: "select-model"
        on_rejected: "archive-task"
        on_timeout: "escalate"
      
      - step_id: "select-model"
        agent: "agent.model-router"
        action: "route_by_policy"
        input:
          task_id: "{{ task.id }}"
          risk_level: "{{ classify_risk.result.risk }}"
        on_success: "execute-task"
        on_failure: "fallback-model"
      
      - step_id: "execute-task"
        agent: "{{ select_model.result.chosen_agent }}"
        action: "execute"
        input:
          task_id: "{{ task.id }}"
          context: "{{ task.full_context }}"
        on_success: "validate-result"
        on_failure: "retry-or-escalate"
        retry:
          max_attempts: 3
          backoff_seconds: 10
      
      - step_id: "validate-result"
        type: "validation"
        schema: "task-result.schema.json"
        on_valid: "commit-result"
        on_invalid: "notify-and-retry"
      
      - step_id: "commit-result"
        agent: "agent.git-committer"
        action: "commit"
        input:
          files:
            - "chaos/projects/{{ task.project }}/results/{{ task.id }}.yaml"
          message: "Task {{ task.id }} completed"
        on_success: "update-indexes"
        on_failure: "manual-resolution"
      
      - step_id: "update-indexes"
        type: "system"
        action: "trigger_github_action"
        workflow: "rebuild-indexes"
        on_success: "notify-completion"
    
    notifications:
      - event: "on_success"
        channels: ["slack", "email"]
        template: "task-complete"
      - event: "on_failure"
        channels: ["slack", "email"]
        template: "task-failed"
      - event: "on_approval-requested"
        channels: ["slack", "in-app"]
        template: "approval-pending"

  - id: "wf.decision-making"
    name: "Decision Making Workflow"
    version: "2.0"
    description: "Estrutura e aprova decisões formais"
    
    trigger: "decision.initiated"
    
    steps:
      - step_id: "research-context"
        agent: "agent.researcher"
        action: "analyze_context"
        input:
          decision_id: "{{ decision.id }}"
      
      - step_id: "structure-alternatives"
        agent: "agent.decision-analyst"
        action: "structure"
        input:
          context: "{{ research_context.result }}"
          decision_type: "{{ decision.type }}"
      
      - step_id: "score-alternatives"
        agent: "agent.decision-analyst"
        action: "score_alternatives"
        input:
          alternatives: "{{ structure_alternatives.result }}"
          criteria: "{{ decision.criteria }}"
      
      - step_id: "recommend"
        agent: "agent.decision-analyst"
        action: "recommend"
        input:
          scores: "{{ score_alternatives.result }}"
          context: "{{ research_context.result }}"
        on_success: "request-decision-approval"
      
      - step_id: "request-decision-approval"
        type: "approval"
        description: "Aprovação de decisão formal"
        assignee: "{{ decision.stakeholders }}"
        timeout_seconds: 86400  # 24h
        on_approved: "formalize"
        on_rejected: "iterate"
        on_timeout: "escalate"
      
      - step_id: "formalize"
        agent: "agent.decision-analyst"
        action: "formalize"
        input:
          decision_id: "{{ decision.id }}"
          chosen_option: "{{ request_decision_approval.approved_option }}"
        on_success: "commit-decision"
      
      - step_id: "commit-decision"
        agent: "agent.git-committer"
        action: "commit"
        input:
          files:
            - "chaos/decisions/{{ decision.id }}.yaml"
          message: "Decision {{ decision.id }} formalized"
        on_success: "create-related-tasks"
      
      - step_id: "create-related-tasks"
        agent: "agent.project-manager"
        action: "create_tasks_for_decision"
        input:
          decision_id: "{{ decision.id }}"
          chosen_option: "{{ formalize.result.chosen }}"
        on_success: "notify-completion"
    
    notifications:
      - event: "on_approval-requested"
        channels: ["slack", "email"]
        template: "decision-approval"
      - event: "on_success"
        channels: ["slack"]
        template: "decision-approved"
```

### 5.3 Policies

```yaml
# agent-system/policies/model-policy.yaml
version: "2.0"
policies:
  default:
    description: "Policy padrão para tarefas comuns"
    task_types:
      - "documentation"
      - "analysis"
      - "planning"
    minimum_model_capabilities:
      reasoning: "medium"
      coding: "low"
    privacy_preference: "local_preferred"
    budget_per_task_usd: 0.50
  
  reasoning:
    description: "Para tarefas complexas que requerem reasoning"
    task_types:
      - "decision-making"
      - "strategy"
      - "research"
      - "architecture"
    minimum_model_capabilities:
      reasoning: "high"
      coding: "medium"
    privacy_preference: "local_only"  # Mais sensível
    budget_per_task_usd: 2.00
  
  coding:
    description: "Para tarefas de desenvolvimento"
    task_types:
      - "implementation"
      - "debugging"
      - "refactoring"
    minimum_model_capabilities:
      reasoning: "medium"
      coding: "high"
    privacy_preference: "cloud_allowed"
    budget_per_task_usd: 1.50
  
  vision:
    description: "Para tarefas com análise de imagens"
    task_types:
      - "diagram-analysis"
      - "chart-interpretation"
      - "visual-inspection"
    minimum_model_capabilities:
      vision: "high"
    privacy_preference: "cloud_allowed"
    budget_per_task_usd: 1.00

# agent-system/policies/risk-policy.yaml
version: "2.0"
risk_classifications:
  read:
    description: "Leitura de CHAOS"
    examples:
      - "Pesquisar documento"
      - "Analisar decision"
      - "Revisar project state"
    approval_required: false
    reversible: true
  
  reversible-low:
    description: "Modificações reversíveis, impacto baixo"
    examples:
      - "Atualizar status de task"
      - "Adicionar comentário"
      - "Criar documento wiki"
    approval_required: false
    reversible: true
  
  reversible-medium:
    description: "Modificações reversíveis, impacto médio"
    examples:
      - "Criar nova task"
      - "Formular decision"
      - "Atualizar risk mitigation"
    approval_required: "if_senior_decision"
    reversible: true
  
  external-impact:
    description: "Ações que afetam sistemas externos"
    examples:
      - "Deploy para produção"
      - "Configurar webhook"
      - "Integração com API externa"
    approval_required: true
    reversible: false
  
  irreversible:
    description: "Ações que não podem ser desfeitas"
    examples:
      - "Deletar projeto"
      - "Arquivar decisão crítica"
      - "Remover usuário"
    approval_required: true
    reversible: false
    escalation_required: true
  
  critical:
    description: "Ações críticas para o negócio"
    examples:
      - "Alteração de política de segurança"
      - "Mudança de arquitetura core"
      - "Decisão que afeta roadmap"
    approval_required: true
    reversible: false
    escalation_required: true
    audit_required: true

# agent-system/policies/approval-policy.yaml
version: "2.0"
approval_gates:
  low-barrier:
    risk_levels: ["read", "reversible-low"]
    auto_approve: true
    notification: "post-action"
  
  medium-barrier:
    risk_levels: ["reversible-medium"]
    requires_approval: "if_cost_or_schedule_impact"
    approvers: "project_owner"
    timeout_hours: 24
    notification: "pre-action"
  
  high-barrier:
    risk_levels: ["external-impact", "irreversible"]
    requires_approval: "always"
    approvers:
      - "project_owner"
      - "tech_lead"
    min_approvals: 1
    timeout_hours: 1
    escalation_on_timeout: true
    notification: "pre-action + escalation"
  
  critical-barrier:
    risk_levels: ["critical"]
    requires_approval: "always"
    approvers:
      - "cto"
      - "security_lead"
      - "project_owner"
    min_approvals: 2  # Quorum
    timeout_hours: 24
    escalation_on_timeout: true
    audit_required: true
    notification: "pre-action + all-stakeholders"

# agent-system/policies/permission-policy.yaml
version: "2.0"
default_permissions:
  agent:
    - "project.read"
    - "task.read"
    - "decision.read"
    - "wiki.read"
  
  human-project-owner:
    - "project.read"
    - "project.write"
    - "task.read"
    - "task.write"
    - "task.delete"  # Com restrições (approve gate)
    - "decision.read"
    - "decision.approve"
  
  human-tech-lead:
    - "project.read"
    - "project.write"
    - "task.read"
    - "task.write"
    - "task.delete"
    - "decision.read"
    - "decision.write"
    - "decision.approve"
    - "risk.read"
    - "risk.write"
  
  human-admin:
    - "all"

role_based_access:
  agent.project-manager:
    base_role: "agent"
    additions:
      - "task.write"
      - "task.create"
      - "milestone.write"
      - "dependency.write"
  
  agent.researcher:
    base_role: "agent"
    additions:
      - "source.read"
      - "wiki.write"
  
  agent.decision-analyst:
    base_role: "agent"
    additions:
      - "decision.write"
      - "decision.propose"
```

### 5.4 Executor (Python Script)

```python
# agent-system/scripts/executor.py
#!/usr/bin/env python3
"""
ORDER Executor — Orquestra agentes, workflows e execução de tarefas
Lê CHAOS, aplica policies, seleciona modelos, executa com Claude, escreve resultados.
"""

import os
import yaml
import json
import argparse
import subprocess
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import anthropic
import sys

# Configuração
CHAOS_DIR = "chaos"
AGENT_SYSTEM_DIR = "agent-system"
RESULTS_DIR = os.path.join(CHAOS_DIR, "projects")

@dataclass
class ExecutionContext:
    """Contexto de execução de uma tarefa"""
    task_id: str
    project_id: str
    agent_id: str
    workflow_id: Optional[str]
    risk_level: str
    requires_approval: bool
    approval_id: Optional[str]
    model_policy: str
    model_selected: Optional[str]
    execution_started_at: datetime
    execution_completed_at: Optional[datetime]
    status: str  # pending, running, completed, failed, blocked
    result: Optional[Dict[str, Any]]
    artifacts: List[str]
    error: Optional[str]

class RiskClassifier:
    """Classifica risco de uma tarefa conforme risk-policy.yaml"""
    
    def __init__(self, policy_path: str):
        with open(policy_path, 'r') as f:
            self.policy = yaml.safe_load(f)
    
    def classify(self, task_data: Dict[str, Any]) -> tuple[str, bool]:
        """
        Retorna (risk_level, requires_approval)
        """
        # Determina risk_level a partir de policy
        risk_level = task_data.get('risk_level', 'reversible-medium')
        
        classification = self.policy['risk_classifications'].get(risk_level, {})
        requires_approval = classification.get('approval_required', False)
        
        return risk_level, requires_approval

class ModelRouter:
    """Seleciona modelo conforme model-policy.yaml e capacidades disponíveis"""
    
    def __init__(self, policy_path: str, models_registry_path: str):
        with open(policy_path, 'r') as f:
            self.policy = yaml.safe_load(f)
        with open(models_registry_path, 'r') as f:
            self.models = yaml.safe_load(f)
    
    def select_model(self, 
                     model_policy_name: str,
                     risk_level: str) -> str:
        """
        Seleciona melhor modelo conforme policy.
        Por enquanto retorna "claude-opus-4.1" como default robusto.
        """
        # TODO: implementar seleção dinâmica baseada em capabilities
        # Por enquanto, usar modelo padrão
        return os.getenv("CLAUDE_MODEL", "claude-opus-4.1")

class ApprovalHandler:
    """Gerencia requisições de aprovação e HITL"""
    
    def __init__(self, approval_policy_path: str):
        with open(approval_policy_path, 'r') as f:
            self.policy = yaml.safe_load(f)
    
    def create_approval_request(self, 
                                context: ExecutionContext,
                                task_data: Dict[str, Any]) -> str:
        """Cria arquivo de approval request e retorna ID"""
        approval_id = f"APV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        approval_request = {
            'id': approval_id,
            'type': 'approval',
            'schema_version': '2.0',
            'created_at': datetime.now().isoformat() + 'Z',
            'task_id': context.task_id,
            'action': f"Execute task {context.task_id}",
            'risk_level': context.risk_level,
            'description': task_data.get('description', ''),
            'impact': task_data.get('impact', 'unknown'),
            'evidence': [
                {'type': 'task', 'ref': f"chaos/tasks/{context.task_id}.yaml"},
                {'type': 'project', 'ref': f"chaos/projects/{context.project_id}.yaml"},
            ],
            'status': 'pending',
            'requested_at': datetime.now().isoformat() + 'Z',
        }
        
        # Salva request em chaos/
        approval_path = os.path.join(CHAOS_DIR, 'approvals', f'{approval_id}.yaml')
        os.makedirs(os.path.dirname(approval_path), exist_ok=True)
        
        with open(approval_path, 'w') as f:
            yaml.dump(approval_request, f, default_flow_style=False)
        
        print(f"[APPROVAL] Created {approval_id}")
        print(f"[APPROVAL] Please review: {approval_path}")
        
        return approval_id
    
    def wait_for_approval(self, approval_id: str, timeout_seconds: int = 3600) -> bool:
        """Aguarda aprovação (blocking)"""
        approval_path = os.path.join(CHAOS_DIR, 'approvals', f'{approval_id}.yaml')
        
        start = datetime.now()
        while (datetime.now() - start).total_seconds() < timeout_seconds:
            if not os.path.exists(approval_path):
                return False
            
            with open(approval_path, 'r') as f:
                approval = yaml.safe_load(f)
            
            if approval.get('status') == 'approved':
                return True
            elif approval.get('status') == 'rejected':
                return False
            
            # Aguarda 5s antes de verificar novamente
            subprocess.run(['sleep', '5'])
        
        # Timeout
        return False

class TaskExecutor:
    """Executa tarefa com Claude"""
    
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    def execute(self, 
                context: ExecutionContext,
                task_data: Dict[str, Any],
                full_context: str) -> tuple[Dict[str, Any], bool]:
        """
        Executa tarefa com Claude e retorna (resultado, sucesso)
        """
        print(f"\n[EXECUTOR] Iniciando execução de {context.task_id}")
        print(f"[EXECUTOR] Modelo: {context.model_selected}")
        print(f"[EXECUTOR] Nível de risco: {context.risk_level}")
        
        # Prepara prompt
        system_prompt = f"""
Você é um agente de execução de tarefas especializado.

Tarefa ID: {context.task_id}
Projeto: {context.project_id}
Título: {task_data.get('title', 'Sem título')}

Contexto completo:
{full_context}

Instruções:
1. Analise a tarefa completamente
2. Identifique dependências (via chaos/dependencies/)
3. Verifique se há conflitos em chaos/risks/
4. Execute a capacidade requerida
5. Registre resultado de forma estruturada
6. Preservar Source of Truth (não inventar evidência)

Retorne resultado em YAML estruturado.
"""
        
        user_prompt = f"""
Execute a seguinte tarefa:

{yaml.dump(task_data, default_flow_style=False)}

Contexto completo (para referência):
{full_context}

Responda apenas em YAML válido estruturado como:

result:
  status: completed|failed|blocked
  summary: "Resumo do que foi feito"
  details: "Detalhes mais completos"
  artifacts: []  # Referências a arquivos criados
  next_steps: []  # Próximas ações sugeridas
  evidence:  # Documentação de decisões
    - "Descrição"
  issues: []  # Problemas encontrados
"""
        
        try:
            response = self.client.messages.create(
                model=context.model_selected or "claude-opus-4.1",
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            
            response_text = response.content[0].text
            print(f"[EXECUTOR] Resposta recebida: {len(response_text)} chars")
            
            # Parse YAML do resultado
            try:
                result = yaml.safe_load(response_text)
                if isinstance(result, dict) and 'result' in result:
                    return result['result'], True
                else:
                    return {'status': 'failed', 'error': 'Invalid response format'}, False
            except yaml.YAMLError as e:
                print(f"[EXECUTOR] Erro ao fazer parse YAML: {e}")
                return {'status': 'failed', 'error': f'YAML parse error: {str(e)}'}, False
        
        except anthropic.APIError as e:
            print(f"[EXECUTOR] Erro de API: {e}")
            return {'status': 'failed', 'error': f'API error: {str(e)}'}, False

class ResultWriter:
    """Escreve resultado em CHAOS e comita em Git"""
    
    def write_result(self, 
                     context: ExecutionContext,
                     result: Dict[str, Any]) -> str:
        """Escreve resultado em chaos/projects/.../results/ e retorna caminho"""
        
        results_path = os.path.join(
            RESULTS_DIR, 
            context.project_id, 
            "results",
            f"{context.task_id}-result.yaml"
        )
        
        os.makedirs(os.path.dirname(results_path), exist_ok=True)
        
        # Estrutura resultado conforme PMMS
        full_result = {
            'id': f"{context.task_id}-result",
            'type': 'result',
            'schema_version': '2.0',
            'created_at': context.execution_started_at.isoformat() + 'Z',
            'completed_at': datetime.now().isoformat() + 'Z',
            'task_id': context.task_id,
            'project_id': context.project_id,
            'agent_id': context.agent_id,
            'status': result.get('status', 'unknown'),
            'summary': result.get('summary', ''),
            'details': result.get('details', ''),
            'artifacts': result.get('artifacts', []),
            'evidence': result.get('evidence', []),
            'issues': result.get('issues', []),
            'next_steps': result.get('next_steps', []),
        }
        
        with open(results_path, 'w') as f:
            yaml.dump(full_result, f, default_flow_style=False, sort_keys=False)
        
        print(f"[WRITER] Resultado escrito em: {results_path}")
        return results_path
    
    def commit_result(self, filepath: str, task_id: str) -> bool:
        """Comita resultado em Git"""
        try:
            subprocess.run(['git', 'add', filepath], check=True)
            subprocess.run([
                'git', 'commit', '-m', 
                f"Task {task_id} executed by executor"
            ], check=True)
            print(f"[WRITER] Commit realizado com sucesso")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[WRITER] Erro ao fazer commit: {e}")
            return False

def load_task(task_id: str) -> Dict[str, Any]:
    """Carrega definição de tarefa de CHAOS"""
    task_path = os.path.join(CHAOS_DIR, 'tasks', f'{task_id}.yaml')
    
    if not os.path.exists(task_path):
        raise FileNotFoundError(f"Task not found: {task_path}")
    
    with open(task_path, 'r') as f:
        return yaml.safe_load(f)

def build_full_context(project_id: str) -> str:
    """Reconstrói contexto completo de um projeto"""
    # Para prototipação, retornar contexto básico
    # TODO: implementar lógica completa de Context Builder
    project_path = os.path.join(CHAOS_DIR, 'projects', f'{project_id}.yaml')
    
    if os.path.exists(project_path):
        with open(project_path, 'r') as f:
            project = yaml.safe_load(f)
        return yaml.dump(project, default_flow_style=False)
    
    return "No project context available"

def main():
    parser = argparse.ArgumentParser(description="ORDER Executor")
    parser.add_argument('--task', required=True, help='Task ID (e.g., TSK-001)')
    parser.add_argument('--project', help='Project ID (optional, inferred from task)')
    parser.add_argument('--agent', help='Agent ID (optional, default: auto-select)')
    parser.add_argument('--skip-approval', action='store_true', help='Skip approval for testing')
    
    args = parser.parse_args()
    
    try:
        # Carrega definição de tarefa
        task_data = load_task(args.task)
        project_id = args.project or task_data.get('project', 'UNKNOWN')
        
        print(f"\n[INIT] Task loaded: {args.task} ({task_data.get('title', 'No title')})")
        print(f"[INIT] Project: {project_id}")
        
        # Cria contexto de execução
        context = ExecutionContext(
            task_id=args.task,
            project_id=project_id,
            agent_id=args.agent or "agent.project-manager",
            workflow_id=None,
            risk_level='reversible-medium',  # Será atualizado
            requires_approval=False,
            approval_id=None,
            model_policy='default',
            model_selected=None,
            execution_started_at=datetime.now(),
            execution_completed_at=None,
            status='pending',
            result=None,
            artifacts=[],
            error=None,
        )
        
        # Classificação de risco
        risk_classifier = RiskClassifier(
            os.path.join(AGENT_SYSTEM_DIR, 'policies', 'risk-policy.yaml')
        )
        risk_level, requires_approval = risk_classifier.classify(task_data)
        context.risk_level = risk_level
        context.requires_approval = requires_approval
        
        print(f"[RISK] Classified as: {risk_level} (approval required: {requires_approval})")
        
        # Verificar aprovação
        if context.requires_approval and not args.skip_approval:
            approval_handler = ApprovalHandler(
                os.path.join(AGENT_SYSTEM_DIR, 'policies', 'approval-policy.yaml')
            )
            context.approval_id = approval_handler.create_approval_request(context, task_data)
            
            print(f"[APPROVAL] Waiting for approval...")
            if not approval_handler.wait_for_approval(context.approval_id):
                context.status = 'blocked'
                print(f"[BLOCKED] Task approval denied or timed out")
                return
        
        # Seleciona modelo
        router = ModelRouter(
            os.path.join(AGENT_SYSTEM_DIR, 'policies', 'model-policy.yaml'),
            os.path.join(AGENT_SYSTEM_DIR, 'tools', 'models.yaml')  # TODO: criar este arquivo
        )
        context.model_selected = router.select_model(context.model_policy, context.risk_level)
        
        # Reconstrói contexto completo
        full_context = build_full_context(project_id)
        
        # Executa com Claude
        executor = TaskExecutor()
        result, success = executor.execute(context, task_data, full_context)
        
        if not success:
            context.status = 'failed'
            context.error = result.get('error', 'Unknown error')
            print(f"[FAILED] {context.error}")
            return
        
        context.status = result.get('status', 'unknown')
        context.result = result
        context.execution_completed_at = datetime.now()
        
        print(f"[SUCCESS] Task {context.task_id} status: {context.status}")
        
        # Escreve resultado em CHAOS
        writer = ResultWriter()
        result_path = writer.write_result(context, result)
        
        # Comita em Git
        if writer.commit_result(result_path, args.task):
            print(f"[COMPLETE] Task execution pipeline finished")
        else:
            print(f"[WARNING] Commit failed, result written but not versioned")
    
    except Exception as e:
        print(f"[ERROR] {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
```

---

## 6. GitHub Actions — Automação CI/CD

### 6.1 Workflow: validate-chaos.yaml

```yaml
# .github/workflows/validate-chaos.yaml
name: Validate CHAOS

on:
  push:
    paths:
      - 'chaos/**/*.yaml'
      - 'chaos/metadata/schemas/**'
  pull_request:
    paths:
      - 'chaos/**/*.yaml'
  schedule:
    # Valida a cada 30 minutos
    - cron: '*/30 * * * *'

jobs:
  validate-schemas:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install pyyaml jsonschema
      
      - name: Validate CHAOS schemas
        run: |
          python agent-system/scripts/validator.py --chaos-dir chaos --schemas-dir chaos/metadata/schemas
      
      - name: Check for ID collisions
        run: |
          python -c "
          import os
          import yaml
          
          ids = {}
          chaos_dir = 'chaos'
          
          for root, dirs, files in os.walk(chaos_dir):
              for file in files:
                  if file.endswith('.yaml'):
                      path = os.path.join(root, file)
                      with open(path, 'r') as f:
                          try:
                              data = yaml.safe_load(f)
                              if isinstance(data, dict) and 'id' in data:
                                  id_val = data['id']
                                  if id_val in ids:
                                      print(f'ERROR: Duplicate ID {id_val} in {path} and {ids[id_val]}')
                                      exit(1)
                                  ids[id_val] = path
                          except yaml.YAMLError:
                              print(f'ERROR: Invalid YAML in {path}')
                              exit(1)
          print(f'OK: {len(ids)} unique IDs found')
          "
      
      - name: Validate dependency integrity
        run: |
          python agent-system/scripts/validator.py --check-dependencies --chaos-dir chaos
      
      - name: Report validation
        if: always()
        run: |
          echo "Validation completed at $(date -u +'%Y-%m-%dT%H:%M:%SZ')" >> chaos/audit/validations.log
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add chaos/audit/validations.log
          git commit -m "Validation report $(date -u +'%Y-%m-%d %H:%M:%S')" --allow-empty || true
          git push
```

### 6.2 Workflow: rebuild-indexes.yaml

```yaml
# .github/workflows/rebuild-indexes.yaml
name: Rebuild Indexes

on:
  workflow_run:
    workflows: ["Validate CHAOS"]
    types: [completed]
  workflow_dispatch:

jobs:
  rebuild:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install pyyaml networkx graphml
      
      - name: Rebuild indexes
        run: |
          python agent-system/scripts/indexer.py \
            --chaos-dir chaos \
            --output-dir chaos/indexes
      
      - name: Generate graph
        run: |
          python agent-system/scripts/indexer.py \
            --chaos-dir chaos \
            --output-graph chaos/graph/graph.json
      
      - name: Commit indexes
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add chaos/indexes/* chaos/graph/*
          git commit -m "Rebuild indexes and graphs [skip ci]" --allow-empty || true
          git push
```

### 6.3 Git Hooks

```bash
#!/bin/bash
# agent-system/hooks/post-merge
# Executado após merge/pull

set -e

echo "[POST-MERGE] Rebuilding indexes..."
python agent-system/scripts/indexer.py \
  --chaos-dir chaos \
  --output-dir chaos/indexes

echo "[POST-MERGE] Validating schemas..."
python agent-system/scripts/validator.py \
  --chaos-dir chaos \
  --schemas-dir chaos/metadata/schemas

echo "[POST-MERGE] Done"
```

```bash
#!/bin/bash
# agent-system/hooks/pre-commit
# Executado antes de commit

set -e

echo "[PRE-COMMIT] Linting YAML..."
for file in $(git diff --cached --name-only --diff-filter=ACM | grep '\.yaml$'); do
    if [ -f "$file" ]; then
        python -m yamllint "$file" || exit 1
    fi
done

echo "[PRE-COMMIT] Validating schemas..."
python agent-system/scripts/validator.py \
  --chaos-dir chaos \
  --schemas-dir chaos/metadata/schemas \
  --files $(git diff --cached --name-only --diff-filter=ACM | grep 'chaos/' | tr '\n' ' ')

echo "[PRE-COMMIT] Passed"
```

---

## 7. Sincronização Multi-Dispositivo

### 7.1 Fluxo de Sincronização Celular

**Cenário:** Usuário em Claude Mobile propõe criar tarefa, Desktop executa, Celular vê resultado.

```
T+0s:  [CELULAR] Claude Mobile
       Usuário digita: "Cria tarefa: Configurar OAuth2"
       Claude gera proposta YAML para TSK-042

T+5s:  [CELULAR] GitHub Mobile App
       Link para criar arquivo: 
       https://github.com/seu-usuario/workspace/new/main/chaos/tasks/TSK-042.yaml
       Usuário clica, GitHub Mobile abre editor
       Copia YAML gerado, cola no editor
       Clica "Create File" e comita

T+10s: [GITHUB] Webhook
       POST https://seu-executor-webhook/events
       {
         "event": "push",
         "ref": "refs/heads/main",
         "commits": [
           {
             "modified": ["chaos/tasks/TSK-042.yaml"]
           }
         ]
       }

T+15s: [GITHUB ACTIONS] validate-chaos
       Valida schema de TSK-042.yaml
       ✓ PASS → continua
       ✗ FAIL → rejeita commit + notifica

T+20s: [GITHUB ACTIONS] rebuild-indexes
       Reconstrói indexes (by-status.md, etc.)
       Comita automaticamente

T+25s: [EXECUTOR] Webhook Handler
       Inicia job: python executor.py --task=TSK-042

T+45s: [EXECUTOR] Claude API
       Envia contexto para Claude
       Claude analisa, retorna resultado

T+50s: [EXECUTOR] Git Commit
       Escreve resultado em chaos/projects/PRJ-001/results/TSK-042-result.yaml
       Comita em Git

T+55s: [DESKTOP] File Watcher
       VSCode detecta novo arquivo
       Recarrega indexes
       Usuário vê resultado

T+60s: [CELULAR] GitHub Mobile
       Usuário faz refresh ou abre GitHub Mobile
       Vê novo arquivo de resultado
       Lê resultado em Claude Mobile
```

### 7.2 Mecanismo de Sincronização

```yaml
# agent-system/sync-config.yaml
sync:
  git:
    remote: "origin"
    branch: "main"
    auto_pull_interval: 300  # A cada 5 minutos
    auto_pull_on_webhook: true
    
  webhook:
    url: "${WEBHOOK_URL}"  # Env var, e.g., https://executor.example.com/webhook
    secret: "${WEBHOOK_SECRET}"
    events:
      - "push:chaos/tasks"
      - "push:chaos/decisions"
      - "push:chaos/projects"
    timeout_seconds: 30
  
  notification:
    channels:
      - type: "slack"
        webhook_url: "${SLACK_WEBHOOK}"
        events:
          - "task.created"
          - "task.completed"
          - "decision.approved"
      
      - type: "email"
        to: "${OWNER_EMAIL}"
        events:
          - "approval.required"
          - "execution.failed"
      
      - type: "github-discussion"
        repo: "seu-usuario/workspace"
        events:
          - "risk.detected"
          - "conflict.found"
```

---

## 8. Fases de Implementação

### Fase 0 — Setup (30 min)

**Objetivo:** Criar repositório, estrutura básica, configuração Git.

1. Criar repositório privado no GitHub: `workspace`
2. Clone localmente e crie estrutura:
   ```bash
   git clone git@github.com:seu-usuario/workspace.git
   cd workspace
   
   # Criar estrutura CHAOS
   mkdir -p chaos/{inbox,wiki,areas,resources,projects,tasks,milestones,risks,dependencies,deliverables,meetings,decisions,sources,metadata/{schemas,registries,policies},indexes,graph,audit,archive}
   
   # Criar estrutura ORDER
   mkdir -p agent-system/{agents,workflows,policies,scripts,tools,.github/workflows,hooks,tests}
   
   # Criar README roots
   echo "# Workspace" > README.md
   echo "# CHAOS" > chaos/README.md
   echo "# ORDER" > agent-system/README.md
   ```

3. Criar schemas básicos:
   ```bash
   # chaos/metadata/schemas/task.schema.json
   # chaos/metadata/schemas/decision.schema.json
   # agent-system/tools/agents.schema.json
   # etc.
   ```

4. Commit inicial:
   ```bash
   git add .
   git commit -m "Initial workspace structure"
   git push -u origin main
   ```

5. Configure GitHub repository settings:
   - Marque como "Private"
   - Ative "Require pull request reviews" (opcional)
   - Proteja branch `main`
   - Configure webhooks (se usando executor externo)

6. Instale Git hooks:
   ```bash
   cp agent-system/hooks/post-merge .git/hooks/
   cp agent-system/hooks/pre-commit .git/hooks/
   chmod +x .git/hooks/*
   ```

**Checklist Fase 0:**
- [ ] Repositório criado
- [ ] Estrutura de diretórios criada
- [ ] README.md nos roots
- [ ] Primeiro commit e push realizado
- [ ] Git hooks instalados
- [ ] GitHub Actions habilitado

### Fase 1 — Protótipo Desktop (2h)

**Objetivo:** Criar primeira tarefa manualmente e validar pipeline.

1. Criar projeto de teste:
   ```yaml
   # chaos/projects/PRJ-TEST.yaml
   id: "PRJ-TEST"
   type: "project"
   name: "Test Project"
   status: "active"
   created_at: "2026-09-13T00:00:00Z"
   ```

2. Criar tarefa de teste:
   ```yaml
   # chaos/tasks/TSK-TEST-001.yaml
   id: "TSK-TEST-001"
   type: "task"
   title: "Test task - hello world"
   project: "PRJ-TEST"
   status: "todo"
   risk_level: "read"
   ```

3. Commit:
   ```bash
   git add chaos/projects/PRJ-TEST.yaml chaos/tasks/TSK-TEST-001.yaml
   git commit -m "Add test project and task"
   git push
   ```

4. Verificar se GitHub Actions rodou:
   - Vá para repo → Actions
   - Procure por workflow "Validate CHAOS"
   - Verifique se passou

5. Manualmente (ainda sem automação):
   ```bash
   python agent-system/scripts/validator.py --chaos-dir chaos
   python agent-system/scripts/indexer.py --chaos-dir chaos --output-dir chaos/indexes
   git add chaos/indexes/*
   git commit -m "Rebuild indexes (manual)"
   git push
   ```

6. Abra em VSCode:
   ```bash
   code .
   ```
   Verifique se indexes foram criados corretamente.

**Checklist Fase 1:**
- [ ] Projeto de teste criado
- [ ] Tarefa de teste criada
- [ ] GitHub Actions passou na validação
- [ ] Indexes reconstruídos manualmente
- [ ] Estrutura visível em VSCode

### Fase 2 — Celular + Sincronização (1h)

**Objetivo:** Testar proposta de tarefa via Claude Mobile e sincronização.

1. Instale GitHub Mobile (se não tiver):
   - iOS: App Store
   - Android: Google Play

2. Em Claude Mobile:
   ```
   "Propõe uma tarefa para o projeto PRJ-TEST. 
    Crie estrutura YAML válida conforme chaos/tasks/ 
    com ID TSK-TEST-002."
   ```

3. Claude Mobile retorna proposta YAML.

4. Copie a proposta e abra GitHub Mobile:
   - Abra repositório `workspace`
   - Selecione branch `main`
   - Navegue até `chaos/tasks/`
   - Clique "Create File"
   - Nomeie: `TSK-TEST-002.yaml`
   - Cole conteúdo YAML
   - Commit com mensagem: "Task created from mobile"

5. Verifique em Desktop (VSCode):
   ```bash
   git pull
   ```
   Novo arquivo deve aparecer.

6. Verifique novamente em Claude Mobile:
   - Abra GitHub Mobile
   - Refresque repositório
   - Navegue até `chaos/tasks/TSK-TEST-002.yaml`
   - Veja conteúdo

**Checklist Fase 2:**
- [ ] GitHub Mobile instalado
- [ ] Tarefa criada via Claude Mobile e GitHub Mobile
- [ ] Sincronização funcionando (Desktop recebe mudança)
- [ ] Resultado visível em ambos dispositivos

### Fase 3 — Automação CI/CD (1.5h)

**Objetivo:** Configurar GitHub Actions para validação e indexação automáticas.

1. Verifique se `.github/workflows/` já existe com YAML:
   - `validate-chaos.yaml`
   - `rebuild-indexes.yaml`

2. Faça um push para ativar workflows:
   ```bash
   git add .github/workflows/*
   git commit -m "Add GitHub Actions workflows"
   git push
   ```

3. Verifique execução:
   - GitHub → Actions
   - Procure pelos workflows
   - Verifique logs

4. Teste criando uma tarefa com erro intencional:
   ```yaml
   # chaos/tasks/TSK-BAD.yaml
   id: "TSK-BAD"
   # Faltando "type" propositalmente
   ```

5. Commit:
   ```bash
   git add chaos/tasks/TSK-BAD.yaml
   git commit -m "Test invalid task"
   git push
   ```

6. Verifique se validação rejeitou ou alertou.

7. Corrija e recomita.

8. Teste automação de indexes:
   - Crie nova tarefa válida
   - Push
   - Verifique se `chaos/indexes/by-status.md` foi reconstruído automaticamente
   - GitHub Actions deve ter criado auto-commit

**Checklist Fase 3:**
- [ ] GitHub Actions workflows ativados
- [ ] Validação automática funcionando
- [ ] Rejeição de schema inválido testada
- [ ] Rebuilding de indexes automatizado
- [ ] Auto-commit de indexes funcionando

### Fase 4 — Executor e Workflows (Opcional, 2-3h)

**Objetivo:** Configurar Python executor, webhooks e execução de tarefas com Claude.

1. Setup Executor:
   ```bash
   pip install -r agent-system/requirements.txt
   
   export ANTHROPIC_API_KEY="sk-..."
   export CLAUDE_MODEL="claude-opus-4.1"
   ```

2. Teste executor manualmente:
   ```bash
   python agent-system/scripts/executor.py --task=TSK-TEST-001 --skip-approval
   ```

3. Verifique se resultado foi escrito em:
   ```
   chaos/projects/PRJ-TEST/results/TSK-TEST-001-result.yaml
   ```

4. (Opcional) Configure webhook para automatizar:
   - Deploy executor em servidor (e.g., AWS Lambda, DigitalOcean)
   - Configure GitHub webhook em Settings → Webhooks
   - Teste: crie tarefa nova, deve disparar execução automaticamente

5. Teste aprovação (HITL):
   - Crie tarefa com `risk_level: reversible-medium`
   - Deve parar antes de executar
   - Crie arquivo de aprovação manualmente
   - Executor deve detectar e continuar

**Checklist Fase 4:**
- [ ] Executor Python funciona localmente
- [ ] Resultado escrito em CHAOS
- [ ] Modelo Claude selecionado corretamente
- [ ] (Opcional) Webhook configurado
- [ ] (Opcional) HITL testada

---

## 9. Integração com Claude Desktop e VSCode

### 9.1 Claude Desktop

Claude Desktop pode acessar repositório de forma nativa:

```
File → Open Workspace
→ Selecione pasta /workspace
→ Claude Desktop indexa chaos/ e agent-system/
→ Use `@project` ou `@file` para referenciar
```

**Exemplo prompt em Claude Desktop:**
```
"@workspace Analise os riscos em RSK-042 e crie plano de mitigação"
```

Claude Desktop lerá `chaos/risks/RSK-042.yaml` e criará mitigação.

### 9.2 Claude Code (VSCode Extension)

Claude Code em VSCode pode operar sobre o workspace:

```python
# Claude Code artifact em VSCode

import yaml
import os

# Lê todos os tasks pendentes
tasks_dir = "chaos/tasks"
pending_tasks = []

for file in os.listdir(tasks_dir):
    if file.endswith('.yaml'):
        with open(os.path.join(tasks_dir, file), 'r') as f:
            task = yaml.safe_load(f)
            if task.get('status') == 'todo':
                pending_tasks.append(task)

# Imprime resumo
print(f"Found {len(pending_tasks)} pending tasks:")
for task in pending_tasks:
    print(f"- {task['id']}: {task['title']}")
```

Claude Code pode criar scripts, validadores, indexadores tudo integrado ao workspace Git.

---

## 10. Observabilidade e Auditoria

### 10.1 Audit Log

```text
# chaos/audit/changes.log
# Formato: TIMESTAMP | TYPE | ACTOR | ACTION | STATUS

2026-09-13T10:45:00Z | COMMIT  | alice@workspace   | TSK-001 created              | ✓
2026-09-13T10:45:10Z | VALIDATE| github-actions    | validate-chaos passed       | ✓
2026-09-13T10:45:15Z | REINDEX | github-actions    | indexes rebuilt             | ✓
2026-09-13T10:46:00Z | COMMIT  | bob@workspace     | DEC-042 approved            | ✓
2026-09-13T10:50:30Z | JOB     | executor          | TSK-001 execution started   | ▶
2026-09-13T10:51:15Z | JOB     | executor          | TSK-001 execution completed | ✓
2026-09-13T10:51:20Z | COMMIT  | executor          | TSK-001 result committed    | ✓
2026-09-13T10:52:00Z | HITL    | carlos@workspace  | Approval requested for DEC-043 | ⏳
2026-09-13T11:00:00Z | HITL    | carlos@workspace  | DEC-043 approved            | ✓
```

### 10.2 Metrics

Capture métricas via GitHub Actions:

```python
# agent-system/scripts/metrics.py
"""
Coleta métricas de execução para observabilidade
"""

import os
import yaml
from datetime import datetime

def count_entities():
    """Conta todas as entidades em CHAOS"""
    counts = {
        'projects': 0,
        'tasks': 0,
        'decisions': 0,
        'risks': 0,
        'completed_tasks': 0,
        'blocked_tasks': 0,
    }
    
    # Conta projects
    for f in os.listdir('chaos/projects'):
        if f.endswith('.yaml'):
            counts['projects'] += 1
    
    # Conta tasks
    for f in os.listdir('chaos/tasks'):
        if f.endswith('.yaml'):
            with open(f'chaos/tasks/{f}', 'r') as fp:
                task = yaml.safe_load(fp)
                counts['tasks'] += 1
                if task.get('status') == 'completed':
                    counts['completed_tasks'] += 1
                elif task.get('status') == 'blocked':
                    counts['blocked_tasks'] += 1
    
    # ... etc
    
    return counts

def print_metrics():
    counts = count_entities()
    print(f"[METRICS] {datetime.now().isoformat()}")
    for key, value in counts.items():
        print(f"  {key}: {value}")

if __name__ == '__main__':
    print_metrics()
```

---

## 11. Tratamento de Conflitos

Se dois dispositivos fizerem push simultâneamente:

```bash
# Desktop fez push de TSK-001.yaml
# Celular também fez push de TSK-001.yaml

# Git detecta conflict:
# CONFLICT (add/add): Merge conflict in chaos/tasks/TSK-001.yaml

# Resolver:
# 1. VSCode mostra conflict markers
# 2. Developer escolhe qual versão manter
# 3. Git merge --continue
# 4. Push resolvido

# MELHOR: Usar diferentes IDs para diferentes dispositivos
# Desktop cria TSK-D-001
# Celular cria TSK-M-001
# Nenhum conflito
```

---

## 12. Segurança e Permissões

### 12.1 GitHub Access

- Repositório **PRIVATE**
- SSH keys configuradas para cada dispositivo
- Branch `main` protegido (opcional)

### 12.2 API Keys

```bash
# Arquivo: .env.local (NÃO commitar)
ANTHROPIC_API_KEY="sk-..."
WEBHOOK_SECRET="signing-secret"
SLACK_WEBHOOK="https://hooks.slack.com/..."

# .gitignore
.env.local
*.secrets.yaml
```

### 12.3 Role-Based Access (futuro)

```yaml
# agent-system/policies/permission-policy.yaml
# (Já definido em Seção 5.3)

roles:
  admin:
    can_delete_project: true
    can_execute_critical_decision: true
  
  developer:
    can_create_task: true
    can_update_task: true
    can_execute_low_risk_task: true
  
  readonly:
    can_read_anything: true
```

---

## 13. Rollback e Recuperação

### 13.1 Rollback de Tarefa

```bash
# Se tarefa TSK-001 teve resultado ruim:
cd workspace
git log --oneline chaos/tasks/TSK-001.yaml
# Retorna: abc1234 Task TSK-001 updated

git checkout abc1234~1 -- chaos/tasks/TSK-001.yaml
git add chaos/tasks/TSK-001.yaml
git commit -m "Rollback TSK-001 to previous state"
git push
```

### 13.2 Recover Full Workspace

```bash
# Se acidentalmente deletou tudo:
git reflog
# Mostra todos os commits (mesmo deletados)

git checkout abc1234
# Volta para ponto anterior

git merge --no-ff main
# Reintegra com branch principal
```

---

## 14. Extensões Futuras

- **GraphQL API:** Expor CHAOS como GraphQL para queries complexas
- **Obsidian Plugin:** Sincronize CHAOS com Obsidian
- **Slack Bot:** Crie tarefas/decisões via Slack
- **Webhooks de Custom Integrations:** Conecte sistemas externos
- **Análise de Gráfo:** Detecte ciclos e dependências circulares
- **Machine Learning:** Recomende agentes/modelos baseado em histórico

---

## 15. Checklist Implementação Completa

- [ ] **Fase 0 — Setup:** Repo criado, estrutura pronta
- [ ] **Fase 1 — Protótipo:** Tarefa criada e validada
- [ ] **Fase 2 — Celular:** Sincronização mobile testada
- [ ] **Fase 3 — CI/CD:** GitHub Actions automático
- [ ] **Fase 4 — Executor:** Tarefas executadas com Claude

---

## Referências

- **CHAOS Spec v2.1:** `/mnt/user-data/uploads/CHAOS_Especificacao_Completa_v2_1.md`
- **ORDER Spec v2.1:** `/mnt/user-data/uploads/Agent_System_Especificacao_Completa_v2_1.md`
- **GitHub Docs:** https://docs.github.com/
- **Git Documentation:** https://git-scm.com/docs
- **Claude API:** https://docs.anthropic.com/

---

**Especificação Completa — Cenário E**  
Versão 1.0 | 2026-09-13 | Pronta para Implementação
