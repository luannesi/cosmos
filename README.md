# COSMOS

Um segundo cérebro governado: conhecimento que persiste em arquivos de texto
versionados, e agentes que agem sobre ele sob regras verificáveis.

**COSMOS** é o sistema inteiro. *Kósmos* é a palavra grega para o mundo
ordenado que emerge do *kháos* — e o par não é enfeite: são os nomes das duas
camadas.

| Camada | O que é | Documento |
|---|---|---|
| **CHAOS** — *Capture · Harvest · Atomize · Organize · Synthesize* | onde o conhecimento mora, e o pipeline que ele percorre | `CHAOS_Especificacao_v2.6.md` |
| **ORDER** — *Orchestrated Runtime for Distributed Execution & Reasoning* | o que executa, decide risco, pede aprovação e controla cota | `ORDER_Especificacao_v2.6.md` |
| *binding* | como as duas se realizam numa máquina concreta | `Implementacao_Claude_Nativa_v1.4.md` |

O ORDER opera o CHAOS **sem ser sua fonte de verdade**, e guarda o próprio
estado dentro dele, na pasta `order/`. Por isso existe um repositório, não
dois: sem o runtime, o conhecimento continua legível e editável com um editor
de texto e o `git`.

O binding não tem nome próprio de propósito. É o membro substituível do trio —
existe um Perfil B (auto-hospedado) previsto para ser outro binding com os
mesmos contratos. Nomear o conjunto, e não a implementação corrente, mantém o
nome válido quando a infraestrutura mudar.

---

## Por onde começar

**Se você quer entender o desenho:** leia o `CHAOS_Especificacao_v2.6.md` do §1
ao §7, depois o `ORDER_Especificacao_v2.6.md` §12 (taxonomia de risco A0–A4) e
§18 (aprovações). São os dois pontos onde o resto se apoia.

**Se você quer instalar:** `TUTORIAL_Instalacao_e_Configuracao.md`, do começo.
Ele foi escrito para ser seguido sem conhecer as especificações.

**Se você quer contribuir com código:** `order-tooling/README.md` e
`order-tooling/ACHADOS.md`. O segundo é o registro de todos os defeitos que a
implementação encontrou nas especificações — é o documento que mais ensina
sobre o projeto, porque cada entrada é um lugar onde a análise errou e o
contato com a realidade corrigiu.

---

## O que há neste repositório

```
CHAOS_Especificacao_v2.6.md          contrato da camada de persistência
ORDER_Especificacao_v2.6.md          contrato do runtime
Implementacao_Claude_Nativa_v1.4.md  binding de referência (Perfil A)
TUTORIAL_Instalacao_e_Configuracao.md

order-tooling/    implementação de referência (~6.400 linhas de Python)
  tools/chaos/    entidades, validador, ledger, índice, contexto, assinatura
  tools/order/    risco, guard, fila, aprovações, cotas, roteamento, worker
  hooks/          os cinco hooks do Claude Code
  bin/            chaos, order, order-worker, episodic-ref
  tests/          79 testes de unidade (~1 s)
  ACHADOS.md      25 defeitos encontrados ao implementar, com a análise de cada

at-suite/         suíte de conformidade: 134 testes
  tests/          CHAOS AT-01..38, ORDER AT-01..32
  test_contract_consistency.py   verifica as ESPECIFICAÇÕES, sem implementação

toolkit/          pacote portátil: scripts de montagem e de primeiro arranque
spike-identidade/ o experimento que mudou a raiz de confiança do sistema
```

As versões anteriores das especificações ficam ao lado das atuais, com o número
no nome. Não são lixo: o changelog de cada versão explica o que mudou e por
quê, e várias decisões só fazem sentido lidas contra a versão que superaram.

---

## Estado

**As especificações estão completas e a implementação de referência passa
134 testes de aceitação e 79 de unidade.** O que falta não é código: é a
instalação numa máquina real (Fase 0 do binding §13), credencial de provedor
para a primeira chamada de modelo, e o componente da camada episódica.

Para rodar a suíte:

```bash
pip install pyyaml jsonschema pytest
python -m pytest at-suite -q \
  --chaos-bin=order-tooling/bin/chaos \
  --order-bin=order-tooling/bin/order
```

Sem os binários apontados, a suíte **pula** os testes com motivo explícito em
vez de passar em verde. Uma suíte de conformidade que passa sem implementação é
pior que nenhuma.

---

## O que este projeto aprendeu

Quinze rodadas de revisão adversarial e três levas de implementação. Se você só
for ler uma coisa além das especificações, leia os `ACHADOS.md` — mas estas são
as lições que se repetiram:

**Contato com a realidade acha o que releitura não acha, e a taxa não
converge.** Catorze rodadas de análise não viram que a garantia central do
sistema era forjável. Dois dias de experimento viram. Escrever os testes
revelou CLIs contraditórias; escrever a implementação revelou dois critérios de
aceitação que se contradiziam ponto a ponto; rodar os scripts revelou um `return`
num script *sourced* que deixava um pacote incompleto passar como pronto.

**Garantia expressa como ausência de marca é garantia frágil.** A v2.5 definia
"commit humano" como *identidade humana e ausência de trailer de agente*. Um
spike mediu o runtime real: a sessão na nuvem sobrescreve autor e committer com
dois comandos. Ausência é o estado natural e custa zero produzir. A v2.6 inverte
a polaridade — autoria humana é a **presença** de uma assinatura que o executor
comprovadamente não consegue produzir.

**Um teste verde não prova que a regra que ele nomeia existe.** Prova que
*alguma* regra reprovou aquele arranjo. Descoberto ao rebaixar uma regra e ver
um teste cair que, investigado, nunca havia testado o que dizia testar.

**Auto-relato de executor não é evidência.** No spike, a sessão afirmou ter
assinado um commit. Não assinou. Não é defeito de um modelo específico: é a
razão pela qual a verificação se faz no artefato, nunca no relato.

**Barreira que o agente restringido pode redigir não é barreira.** A plataforma
barrou corretamente um metadado de autorização forjado — e o próprio agente
então ofereceu três formas de contornar o bloqueio, descrevendo-o como
formalidade. Não por má-fé: quem quer completar a tarefa naturalmente descreve
o obstáculo como formalidade. Por isso o pedido de aprovação passou a ser
redigido pelo motor de risco, nunca pelo proponente.

**Termo familiar para de ser examinado.** "CHAOS" atravessou quinze rodadas,
duas delas com revisores adversariais cruzados, usado centenas de vezes sem
nunca ter sido definido. O `chaos health` sobreviveu a quatro rodadas declarado
na interface de linha de comando sem contrato nenhum.

---

## Convenções

As **especificações são normativas** e usam MUST / MUST NOT / SHOULD no sentido
da RFC 2119. O binding as realiza sem redefini-las: quando os dois divergem, a
especificação vence e o binding é o defeito.

Todo critério de aceitação novo entra na *Definition of Done* da sua
especificação. Toda regra normativa nova precisa de um critério de aceitação
que a verifique — regra sem teste é intenção, não contrato.

O idioma de trabalho é o português.
