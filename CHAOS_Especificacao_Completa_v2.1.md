# CHAOS — Especificação Completa v2.1

**Status:** Especificação de referência para implementação
**Versão:** 2.1
**Idioma normativo:** PT-BR

> Esta especificação define contratos, modelos, protocolos, invariantes e critérios de aceitação. A implementação concreta pode usar qualquer linguagem, banco, editor, runtime ou infraestrutura que preserve esses contratos.

## 1. Propósito

CHAOS é a camada persistente de conhecimento, memória canônica, gestão de projetos, decisões, documentos, proveniência e integridade do ecossistema de agentes.

CHAOS deve permanecer útil sem o ORDER. O ORDER opera CHAOS, mas não é sua fonte de verdade.

### 1.1 Objetivos

- armazenar conhecimento legível por humanos e máquinas;
- manter projetos e seu estado reconstruível;
- representar tarefas, milestones, dependências, riscos e entregáveis;
- registrar decisões, alternativas, critérios e resultados;
- preservar fontes, evidências, confiança e conflitos;
- fornecer recuperação lexical e estrutural sem exigir banco vetorial;
- permitir auditoria, integridade e proveniência;
- funcionar com Git e formatos abertos;
- permitir migração entre ferramentas sem perda semântica.

### 1.2 Não objetivos

CHAOS não é:

- runtime de agentes;
- gateway de LLM;
- banco vetorial obrigatório;
- SaaS de project management;
- repositório obrigatório de código-fonte;
- canal de notificação;
- blockchain.

## 2. Linguagem normativa

- **MUST:** requisito obrigatório.
- **MUST NOT:** proibição.
- **SHOULD:** recomendação forte, podendo haver justificativa documentada.
- **SHOULD NOT:** recomendação de evitar.
- **MAY:** opcional.

## 3. Princípios arquiteturais

1. **Source of Truth:** conteúdo canônico deve existir em arquivos versionáveis e/ou armazenamento equivalente, com semântica exportável.
2. **LLM não é autoridade:** modelos geram interpretação/candidatos; fatos e estado canônico precisam de registro e validação.
3. **Obsidian é interface:** pode ser a principal UI, mas não pode ser dependência estrutural.
4. **Projeto não é código:** CHAOS guarda gestão/documentação; código permanece em repositórios próprios.
5. **Entidades atômicas:** tarefas, decisões, riscos etc. possuem IDs estáveis.
6. **Views são derivadas:** Gantt, Kanban, índices e agregações podem ser reconstruídos.
7. **Proveniência é primeira classe:** informação crítica deve apontar para sua origem.
8. **Integridade não é verdade:** hash/signatura demonstram integridade/autenticidade, não veracidade factual.
9. **Autonomia é governada por risco:** irreversibilidade e consequência determinam rigor.
10. **Substituibilidade:** componentes tecnológicos devem poder ser trocados.
11. **Degradação graciosa:** recursos opcionais não podem destruir o núcleo.
12. **Simplicidade:** complexidade adicional exige benefício mensurável.

## 4. Topologia de repositórios

```text
workspace/
├── chaos/                 # conhecimento, estado, PM, decisões, auditoria
├── agent-system/          # execução e orquestração
├── project-code-a/        # código independente
├── project-code-b/
└── ...
```

### 4.1 Estrutura recomendada

```text
chaos/
├── README.md
├── inbox/
├── wiki/
├── areas/
├── resources/
├── sources/
├── projects/
├── tasks/
├── milestones/
├── risks/
├── dependencies/
├── deliverables/
├── meetings/
├── decisions/
├── contracts/
├── deadlines/
├── reports/
├── archive/
├── metadata/
│   ├── schemas/
│   ├── registries/
│   └── policies/
├── indexes/
├── graph/
└── audit/
```

A estrutura física pode variar se os contratos lógicos forem preservados.

## 5. PARA e camadas epistemológicas

CHAOS suporta PARA:

```text
Projects → Areas → Resources → Archive
```

e separa o ciclo epistemológico:

```text
RAW/INBOX → SOURCES → KNOWLEDGE/WIKI → PROJECTS/AREAS → DECISIONS → ARCHIVE
```

### 5.1 Inbox

Conteúdo recém-capturado, ainda não classificado ou validado.

### 5.2 Sources

Fontes primárias ou externas que sustentam afirmações.

### 5.3 Wiki

Conhecimento consolidado e reutilizável.

### 5.4 Projects

Trabalho temporário orientado a resultado.

### 5.5 Decisions

Registro explícito de decisões e racional.

### 5.6 Archive

Conteúdo inativo, preservado para histórico.

## 6. Source of Truth

Ordem padrão de autoridade:

1. registro primário verificável;
2. documento oficial;
3. fonte diretamente citada;
4. decisão formal registrada;
5. Project State;
6. conhecimento consolidado;
7. interpretação derivada;
8. hipótese;
9. inferência de agente;
10. geração não verificada.

Conflitos não podem ser silenciosamente descartados.

## 7. Identidade e schemas

Toda entidade canônica deve ter pelo menos:

```yaml
id: TSK-001
type: task
schema_version: "2.0"
title: "Nome"
status: todo
created_at: "2026-09-12T00:00:00Z"
updated_at: "2026-09-12T00:00:00Z"
```

IDs são imutáveis e nunca reutilizados.

### 7.1 Tipos mínimos

`PRJ`, `TSK`, `MS`, `RSK`, `DEP`, `DLV`, `MTG`, `DEC`, `SRC`, `DOC`, `DL`, `EVT`.

### 7.2 Compatibilidade de schema

- leitores devem preservar campos desconhecidos quando possível;
- breaking changes exigem nova versão;
- migrações devem ser explícitas;
- antes/depois devem ser validados;
- deve existir changelog;
- rollback deve ser possível quando tecnicamente viável.

# 8. PMMS — Project Management Markdown Schema

PMMS é o contrato canônico para gerenciamento de projetos.

## 8.1 Project

```yaml
id: PRJ-001
type: project
schema_version: "2.0"
name: "Projeto"
status: active
objective: "Resultado esperado"
owner: ""
start_date: "2026-01-01"
target_date: "2026-12-31"
repository: ""
health: green
scope:
  included: []
  excluded: []
constraints: []
assumptions: []
```

Estados: `idea`, `planned`, `active`, `blocked`, `paused`, `completed`, `cancelled`, `archived`.

## 8.2 Milestone

```yaml
id: MS-001
type: milestone
project_id: PRJ-001
title: "Marco"
status: planned
target_date: "2026-06-30"
criteria_of_done: []
dependencies: []
deliverables: []
```

## 8.3 Task

```yaml
id: TSK-001
type: task
project_id: PRJ-001
title: "Tarefa"
status: todo
priority: medium
owner: ""
estimate: ""
start_date: ""
due_date: ""
depends_on: []
blocks: []
milestone_id: ""
acceptance_criteria: []
definition_of_ready: []
definition_of_done: []
risk_ids: []
```

Estados: `backlog`, `todo`, `ready`, `in_progress`, `blocked`, `review`, `done`, `cancelled`.

## 8.4 Dependency

```yaml
id: DEP-001
type: dependency
from: TSK-002
relation: blocks
to: TSK-003
status: active
reason: ""
```

Relações: `blocks`, `blocked_by`, `depends_on`, `precedes`, `follows`, `related_to`.

## 8.5 Risk

```yaml
id: RSK-001
type: risk
project_id: PRJ-001
title: "Risco"
status: open
probability: medium
impact: high
score: 0
owner: ""
mitigation: []
contingency: []
triggers: []
```

A fórmula do score deve ser definida pela política adotada.

## 8.6 Deliverable

```yaml
id: DLV-001
type: deliverable
project_id: PRJ-001
title: "Entregável"
status: planned
owner: ""
due_date: ""
acceptance_criteria: []
artifact_refs: []
```

## 8.7 Meeting

```yaml
id: MTG-001
type: meeting
schema_version: "2.0"
date: "2026-01-01"
participants: []
project_id: PRJ-001
agenda: []
notes: ""
decisions: []
actions: []
source_refs: []
```

Ata deve distinguir fatos, decisões, ações, responsáveis, prazos e pendências.

## 8.8 Document / Contract / Deadline

Devem manter ID, status, origem, validade, datas críticas, responsáveis e referências relacionadas.

# 9. Project State Protocol

Project State é a representação canônica do estado atual de um projeto.

Deve responder:

1. objetivo;
2. estado atual;
3. concluído;
4. em andamento;
5. bloqueios;
6. próximo passo;
7. riscos;
8. decisões vigentes;
9. dependências;
10. evidências.

O estado pode ser materializado em `projects/PRJ-xxx/state.md`, mas os fatos precisam ser rastreáveis às entidades canônicas.

# 10. Planejamento

Hierarquia recomendada:

```text
Épico → Feature → Milestone → Task → Subtask
```

PMMS deve suportar DoR, DoA, DoD, dependências, estimativas, caminho crítico, milestones, riscos, Gantt e Kanban.

Gantt/Kanban e agregações são views derivadas, salvo declaração explícita em contrário.

# 11. Decision Protocol

Fluxo normativo:

```text
Problem → Frame → Explore → Generate → Classify →
Select Mode → Evaluate → Decide → Execute/Experiment → Verify → Learn
```

## 11.1 Schema

```yaml
id: DEC-001
type: decision
schema_version: "2.0"
title: "Decisão"
status: proposed
problem: ""
context: ""
objective: ""
constraints: []
alternatives: []
criteria: []
decision_mode: ""
selected_option: ""
rationale: ""
expected_outcomes: []
risks: []
reversible: true
consequence: low
approval:
  required: false
  approved_by: ""
  approved_at: ""
evidence: []
supersedes: []
review_date: ""
result: ""
lessons: []
```

## 11.2 Frameworks suportados

- Logic Tree;
- Decision Matrix;
- Weighted Scoring;
- Cost-Benefit;
- Expected Value;
- Cynefin;
- Reversibility × Consequence;
- premortem;
- experimento controlado;
- política explícita;
- decisão humana.

## 11.3 Revisão e supersessão

Decisões podem ser superseded, mas não devem ser apagadas do histórico. Uma decisão posterior deve referenciar a anterior.

# 12. Autonomia e risco

A autonomia é função de:

```text
ação + risco + reversibilidade + consequência + permissão + política
```

| Classe | Exemplo | Aprovação |
|---|---|---|
| A0 | leitura | não |
| A1 | escrita local reversível | política |
| A2 | ação externa limitada | política/condição |
| A3 | impacto relevante | humana |
| A4 | irreversível/crítica | humana explícita |

# 13. Knowledge Lifecycle

```text
Capture → Classify → Validate → Link → Promote → Maintain → Archive
```

Estados possíveis: `raw`, `candidate`, `verified`, `consolidated`, `canonical`, `archived`.

Promoção deve preservar fontes e histórico.

## 13.1 Memory decay

Memórias derivadas devem poder carregar:

- criação;
- última confirmação;
- validade;
- confiança;
- fonte;
- status.

Memórias antigas podem ser rebaixadas sem destruição automática.

# 14. Proveniência e epistemologia

Informação relevante deve declarar:

```yaml
provenance:
  origin: human|agent|external_source|derived
  source_refs: []
  confidence: high|medium|low|unknown
  epistemic_status: fact|verified|inference|hypothesis|decision|unknown
  verified_at: ""
  verified_by: ""
```

# 15. Retrieval

Arquitetura baseline:

```text
Query
 ↓
BM25 + Graphify + Wiki + Project State + Decisions
 ↓
Context Builder
 ↓
Agent/LLM
```

## 15.1 BM25

Busca lexical recomendada como baseline por simplicidade, velocidade e independência.

## 15.2 Graphify

Grafo derivado de IDs e referências. Exemplo:

```text
PRJ-001
├── MS-001
│   ├── TSK-001
│   └── TSK-002
├── RSK-001
└── DEC-001
```

## 15.3 Vector DB

É opcional. Qdrant ou equivalente só deve ser introduzido quando o ganho de recuperação justificar complexidade, custo, manutenção e risco de privacidade.

# 16. Context Builder

Entrada:

```yaml
query: ""
agent: ""
project_id: ""
task_id: ""
token_budget: 0
retrieval_policy: ""
```

Saída:

```yaml
context:
  sources: []
  entities: []
  decisions: []
  project_state: []
  constraints: []
  conflicts: []
  warnings: []
provenance: []
```

Regras: priorizar autoridade, preservar conflitos, respeitar orçamento, evitar duplicação, registrar fontes e nunca fabricar evidência.

# 17. Integrity & Provenance Layer

A camada de integridade é independente do Git.

## 17.1 Audit Ledger

```yaml
event_id: EVT-000001
timestamp: "2026-01-01T10:00:00Z"
actor: agent:planner
action: update
entity_id: TSK-001
before_hash: ""
after_hash: ""
payload_hash: ""
previous_event_hash: ""
signature: ""
```

O ledger deve ser append-only na semântica lógica.

## 17.2 Hash chain

```text
EVT-001 → EVT-002 → EVT-003 → EVT-004
```

Alterações retroativas devem ser detectáveis.

## 17.3 Assinaturas

Eventos críticos podem usar Ed25519 ou mecanismo equivalente.

## 17.4 Merkle

Eventos podem ser agregados periodicamente em Merkle Tree e seu root armazenado externamente.

## 17.5 Blockchain

Blockchain é somente uma âncora externa opcional para integridade/timestamp. Não é banco primário, memória, source of truth ou requisito.

# 18. Git, commits e mudança de schema

Git é o mecanismo recomendado de versionamento.

Commits devem preferir Conventional Commits:

```text
feat(project): add milestone
fix(task): correct dependency
docs(decision): record decision
test(schema): add validation
```

Mudança incompatível de schema requer migração, changelog, validação e estratégia de rollback.

# 19. Views e índices

Views possíveis:

- tasks.md;
- dependencies.csv;
- Gantt;
- Kanban;
- dashboards;
- risk matrix;
- decision index;
- knowledge index;
- graph;
- reports.

Cada artefato deve declarar `canonical`, `derived`, `cache` ou `temporary`.

Agentes não devem editar uma view derivada como fonte canônica.

# 20. Validação

O validador deve detectar:

- IDs duplicados;
- referências inexistentes;
- ciclos proibidos;
- schema inválido;
- status inválido;
- datas inconsistentes;
- dependências inválidas;
- entidades órfãs;
- links quebrados;
- versões incompatíveis;
- hash inválido;
- assinatura inválida;
- índice inconsistente.

Categorias: `syntax`, `schema`, `reference`, `semantic`, `integrity`, `policy`.

# 21. CLI

Uma CLI deve oferecer semânticas equivalentes a:

```text
chaos init
chaos validate
chaos status
chaos project list
chaos project show PRJ-001
chaos task list
chaos task create
chaos task update
chaos decision create
chaos decision show DEC-001
chaos search "query"
chaos graph build
chaos index rebuild
chaos audit verify
chaos integrity verify
chaos migrate
chaos backup
chaos restore
```

A sintaxe concreta é livre.

# 22. API

Se houver API, deve haver recursos equivalentes a:

```text
GET/POST/PATCH /projects
GET/POST/PATCH /tasks
GET/POST /decisions
GET /search
GET /context
GET /audit
POST /validate
POST /rebuild
```

REST, gRPC, GraphQL ou outro protocolo são aceitáveis.

# 23. Segurança

Deve haver:

- least privilege;
- separação de segredos;
- arquivos sensíveis fora do Git;
- permissões por operação;
- logs sem segredos;
- criptografia conforme risco;
- backups protegidos;
- validação de entradas;
- controle de execução.

Segredos nunca devem estar no Markdown canônico.

# 24. Backup e recuperação

Backup deve contemplar no mínimo:

1. conteúdo CHAOS;
2. audit ledger;
3. schemas/policies;
4. configurações não secretas necessárias à reconstrução.

Índices derivados podem ser regenerados.

Restore deve ser testado periodicamente.

# 25. Integração com ORDER

ORDER pode:

- ler CHAOS;
- consultar contexto;
- criar/atualizar entidades;
- registrar decisões;
- atualizar estado;
- registrar auditoria.

CHAOS não conhece a implementação interna dos agentes.

# 26. Interoperabilidade

Outra ferramenta deve conseguir:

1. ler os formatos canônicos;
2. identificar entidades;
3. preservar IDs;
4. resolver referências;
5. validar schemas;
6. reconstruir views;
7. preservar provenance;
8. operar sem Obsidian;
9. operar sem banco vetorial;
10. preservar histórico.

# 26. Política de implementação e seleção de tecnologias

Esta seção é **normativa** e complementa a matriz tecnológica. O objetivo é permitir que uma LLM implemente o CHAOS sem transformar uma ferramenta concreta em dependência arquitetural.

## 26.1 Classificação das tecnologias

Toda tecnologia concreta deve possuir exatamente uma classificação no contexto de uma implementação:

- **RECOMMENDED** — ferramenta padrão para a capacidade. A implementação deve utilizá-la por padrão.
- **ALTERNATIVE** — ferramenta compatível que pode substituir a recomendada preservando os contratos.
- **EXPERIMENTAL** — opção ainda não estabelecida como caminho de produção.
- **NOT REQUIRED** — não necessária para a arquitetura/base.

A classificação é uma decisão de implementação. Não altera os contratos canônicos do CHAOS.

## 26.2 Regra para LLM implementadora

Quando uma LLM receber esta especificação para implementação, deve seguir esta ordem:

1. identificar a capacidade necessária;
2. localizar a ferramenta **RECOMMENDED** para essa capacidade;
3. verificar compatibilidade com o ambiente, requisitos de segurança e restrições explicitamente fornecidas pelo usuário;
4. utilizar a ferramenta recomendada quando ela estiver disponível e for compatível;
5. se a ferramenta recomendada não estiver disponível, estiver incompatível ou exigir uma decisão relevante de arquitetura, **não substituir silenciosamente**;
6. apresentar as alternativas válidas e perguntar ao usuário qual deseja utilizar;
7. se existir uma política previamente autorizada de fallback para aquela capacidade, aplicar somente essa política e registrar a substituição;
8. registrar a decisão tecnológica, a justificativa e a alternativa escolhida;
9. implementar por meio do contrato/adaptador da capacidade, nunca acoplando o restante do CHAOS à ferramenta concreta.

A LLM pode sugerir uma alternativa, mas não deve convertê-la em escolha implícita quando a substituição alterar custo, segurança, operação, manutenção, portabilidade ou comportamento observável.

## 26.3 Preferência explícita do usuário

Se o usuário escolher uma ferramenta ALTERNATIVE e ela satisfizer o contrato da capacidade, essa escolha deve prevalecer sobre a ferramenta RECOMMENDED.

A implementação deve:

- registrar a ferramenta selecionada;
- preservar o contrato canônico;
- encapsular diferenças no adapter;
- indicar incompatibilidades reais antes de implementar;
- não modificar o modelo conceitual apenas para acomodar a ferramenta.

## 26.4 Regra de substituibilidade

```text
                 CANONICAL CONTRACT
                         |
          +--------------+--------------+
          |              |              |
     Recommended     Alternative     Alternative
       Tool A           Tool B          Tool C
          |              |              |
          +--------------+--------------+
                         |
                    Adapter Layer
                         |
                  CHAOS capability
```

A substituição deve ocorrer abaixo do contrato. Um componente pode ser trocado sem exigir alteração dos schemas, IDs, protocolos, Project State, Decision Protocol ou formato canônico de conhecimento, salvo quando houver uma decisão explícita de evolução do próprio contrato.

## 26.5 Registro de decisão tecnológica

Toda escolha concreta relevante deve ser registrável como `technology_decision`:

```yaml
---
type: technology_decision
schema_version: 1.0
id: TEC-EXAMPLE-001
capability: retrieval
recommended: bm25
selected: bm25
classification: recommended
alternatives:
  - graphify
  - vector_database
reason: "Baseline lexical retrieval with low operational complexity"
user_selected: false
compatibility_verified: true
created:
updated:
---
```

Para substituições, `selected` deve registrar a tecnologia efetivamente utilizada e `reason` deve explicar por que a recomendada não foi utilizada.

## 26.6 Ferramentas não são contratos

Os contratos canônicos do CHAOS são, entre outros:

- Markdown/YAML/CSV;
- IDs e schemas;
- Project State;
- PMMS;
- Decision Protocol;
- provenance;
- audit/integrity semantics;
- retrieval interface;
- Context Builder interface;
- Git/versioning semantics;
- APIs/CLI semânticas definidas pela especificação.

Ferramentas como Obsidian, BM25 implementations, Graphify, PostgreSQL, Qdrant, Git hosting ou qualquer editor são implementações ou interfaces desses contratos.

## 26.7 Modelos de IA permanecem totalmente agnósticos

Nenhum LLM/provider/model específico é classificado como RECOMMENDED ou ALTERNATIVE nesta especificação.

O sistema deve selecionar **capacidades**, não marcas. A cadeia permanece:

```text
Task
  ↓
Model Policy
  ↓
Model Router
  ↓
Model Gateway
  ↓
Provider / Runtime / Model
```

A implementação não deve assumir um fornecedor de LLM como padrão estrutural.

# 27. Matriz tecnológica

A matriz define a referência de implementação, não dependências arquiteturais.

| Capacidade | RECOMMENDED | ALTERNATIVES | EXPERIMENTAL / NOT REQUIRED |
|---|---|---|---|
| Persistência de conhecimento | Markdown + YAML/CSV | formatos abertos equivalentes | — |
| Versionamento | Git | outro VCS que preserve histórico/branching | — |
| Busca lexical | BM25 | outra implementação BM25/FTS equivalente | — |
| Grafo derivado | Graphify | Neo4j, FalkorDB ou implementação equivalente | outros graph engines |
| Estado operacional | PostgreSQL | SQLite ou outro banco relacional compatível | — |
| Interface de conhecimento | Obsidian | VSCode, editor Markdown, UI própria | — |
| Memória operacional | ai-memory via adapter | implementação própria compatível | soluções futuras |
| Interoperabilidade de ferramentas | MCP quando aplicável | adapters diretos, APIs, CLI | protocolos futuros |
| Vetor | **não obrigatório** | Qdrant ou outro vector DB compatível | — |
| Auditoria/integridade | Git + Audit Ledger/Hash Chain | mecanismos equivalentes | ancoragem blockchain/Merkle externa |
| Automação/execução | scripts/CLI do próprio sistema | ferramentas equivalentes | — |

### 27.1 Regra importante sobre Qdrant/vector DB

Vector DB não é requisito do CHAOS. A implementação deve começar com recuperação lexical/estrutural e somente adicionar vetor quando houver benefício mensurável que justifique complexidade, custo, manutenção ou risco de privacidade.

### 27.2 Regra importante sobre Obsidian

Obsidian é a interface recomendada para navegação e edição humana, mas o CHAOS deve continuar funcional sem ele.

### 27.3 Regra importante sobre Git

Git é a ferramenta recomendada para versionamento do CHAOS. GitHub, GitLab ou outro hosting são opções de infraestrutura e não fazem parte da fonte de verdade semântica.

# 28. Migração do segundo cérebro

A migração deve ser incremental:

1. backup;
2. inventário;
3. classificação;
4. identificação de entidades;
5. atribuição de IDs;
6. frontmatter;
7. resolução de links;
8. Project State;
9. índices;
10. validação;
11. Git baseline;
12. ativação gradual dos agentes.

Não apagar conteúdo legado apenas para adequação ao schema.

# 29. Roadmap

### Fase 1 — Foundation
Schemas, estrutura, IDs, Git, validator e Project State.

### Fase 2 — Knowledge
Inbox, sources, wiki, provenance e promotion.

### Fase 3 — Project Management
PMMS, tasks, milestones, dependencies, risks e views.

### Fase 4 — Decisions
Decision Protocol, scoring, revisão e experimentos.

### Fase 5 — Retrieval
BM25, Graphify e Context Builder.

### Fase 6 — Integrity
Audit ledger, hash chain, assinaturas e Merkle.

### Fase 7 — Advanced
Vector DB e ancoragem externa apenas se justificadas.

# 30. Acceptance Tests

**AT-01 — Tool independence:** remover Obsidian não impede leitura/escrita.

**AT-02 — Project reconstruction:** estado de PRJ-001 pode ser reconstruído em ambiente limpo.

**AT-03 — Stable IDs:** alterar título não altera ID.

**AT-04 — Derived views:** apagar uma view e reconstruí-la sem perda.

**AT-05 — Conflict preservation:** fontes conflitantes continuam identificáveis.

**AT-06 — Decision traceability:** decisão referencia contexto, alternativas e resultado.

**AT-07 — Audit integrity:** alteração retroativa é detectável.

**AT-08 — Vector independence:** remover vector DB não quebra busca lexical/estrutural.

**AT-09 — Agent independence:** CHAOS funciona sem ORDER.

**AT-10 — Migration:** conteúdo legado é migrável sem perda silenciosa.

# 31. Anti-padrões

Não implementar:

- LLM como banco de dados;
- vector DB como única memória;
- Obsidian como dependência;
- blockchain como banco;
- PM SaaS como autoridade;
- arquivos monolíticos como única representação;
- agentes editando views derivadas;
- decisão crítica sem protocolo;
- ação irreversível sem aprovação;
- acoplamento a fornecedor;
- complexidade distribuída sem necessidade.

# 32. Critério para adoção/removal de componentes

Uma tecnologia deve demonstrar ganho mensurável em qualidade, desempenho, segurança, interoperabilidade ou esforço.

Deve ser removida quando duplicar funcionalidade ou aumentar complexidade sem retorno.

# 33. Golden Architecture

```text
                 USER / AGENTS
                      |
                      v
              +---------------+
              | Context       |
              | Builder       |
              +-------+-------+
                      |
          +-----------+-----------+
          |           |           |
         BM25      Graphify   Project State
          |           |           |
          +-----------+-----------+
                      |
                      v
              +---------------+
              |     CHAOS      |
              | MD/YAML/CSV/Git|
              +-------+-------+
                      |
                      v
              +---------------+
              | Audit/Integrity|
              +---------------+
```

# 34. Definition of Done

CHAOS v2.1 é compatível quando:

- schemas são formalizados;
- entidades possuem IDs estáveis;
- Project State é reconstruível;
- PMMS é validável;
- decisões são rastreáveis;
- provenance é preservada;
- views são regeneráveis;
- busca funciona sem vetor;
- integridade pode ser verificada;
- backup/restore funciona;
- Obsidian é opcional;
- ORDER é externo/substituível;
- não existe dependência estrutural de fornecedor.
