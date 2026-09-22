# Achados da tradução dos AT para código — CHAOS §30

**AT** = *Acceptance Test* (teste de aceitação). **CLI** = *Command Line Interface*.

Escrever os 26 AT do CHAOS como asserções executáveis expôs sete que não se deixam
traduzir. Seis são defeito de especificação; um é lacuna da própria suíte. Nenhum
tinha aparecido em oito rodadas de revisão por leitura, porque todos **parecem**
corretos em prosa — só falham quando alguém pergunta "qual é o arranjo, qual é a
asserção".

Rodar `pytest -rx` na suíte lista os sete como `XFAIL` com o motivo.

---

## #1 — AT-01 não tem sujeito observável

**Como está:** "remover Obsidian não impede leitura/escrita."

**Problema:** Obsidian nunca está instalado no sistema sob teste. É uma interface
externa que abre a mesma pasta; não faz parte do repositório, do CLI nem do
runtime. Não há o que remover, logo não há transição de estado para observar.

**Invariante real** (CHAOS §3.3): nenhuma entidade exige ferramenta além do CLI e
um editor de texto.

**Reescrita proposta:** toda entidade é UTF-8 com frontmatter YAML legível e
editável por editor de texto comum; uma cópia do repositório sem nenhum binário do
projeto continua legível; uma entidade editada à mão por humano é aceita pelo
validador, que reconcilia (§21).

---

## #2 — AT-02 é ambíguo quanto ao campo `narrative`

**Como está:** "estado de um PRJ é reconstruído em ambiente limpo."

**Problema:** §9.1 declara `state.md` como `derived` **com edição humana permitida
no campo `narrative`**. Se alguém editou `narrative`, o state regenerado não pode
ser idêntico ao original — e a spec não diz se a reconstrução preserva ou descarta
esse campo. As duas leituras levam a implementações incompatíveis, e a segunda
apaga texto humano sem aviso.

**Decisão proposta:** a reconstrução regenera todos os campos derivados e
**preserva `narrative` quando o arquivo existe**; reconstruído do zero (clone
limpo), `narrative` nasce vazio e sua ausência nunca é divergência para o
validador. Isto torna o AT verificável em ambos os arranjos.

---

## #3 — AT-05 não tem operação nem critério

**Como está:** "fontes conflitantes continuam identificáveis."

**Problema:** nenhum comando do §21 produz duas fontes em conflito, e §14 não
define o que torna duas fontes conflitantes — contradição factual? mesma asserção
com `confidence` diferente? A suíte não consegue nem montar o arranjo.

**Reescrita proposta:** duas SRC citadas como evidência de asserções incompatíveis
sobre o mesmo campo da mesma entidade permanecem **ambas** recuperáveis; o campo
`conflicts` da entidade referencia as duas; nenhuma é apagada, sobrescrita ou
rebaixada automaticamente. O critério deixa de ser semântico (o que é "conflito")
e passa a ser estrutural (duas evidências, uma entidade, um campo).

---

## #4 — AT-09 tem duas leituras incompatíveis

**Como está:** "CHAOS funciona sem ORDER."

**Problema:** a spec afirma as duas coisas em lugares diferentes. §1 diz que o
estado operacional do ORDER é persistido **dentro** do CHAOS, em `order/`; §4.1
inclui `order/` no layout do repositório. Então "sem ORDER" pode ser (a) sem o
*runtime*, com a pasta intacta, ou (b) sem a pasta — que viola §4.1.

**Decisão proposta:** "sem ORDER" significa **sem o runtime**. A pasta `order/`
permanece e suas entidades (RUN, APV, HND, SES) são tratadas pelo validador como
entidades comuns. O AT passa a ser: com nenhum binário `order` disponível,
`chaos validate`, `search`, `context`, `<tipo> create|update` e `index rebuild`
funcionam integralmente.

---

## #5 — AT-10 testa um procedimento manual

**Como está:** "legado migrável sem perda silenciosa."

**Problema:** §28.1 é um roteiro de doze passos executado por uma pessoa, sem
comando correspondente no §21, e "perda silenciosa" não está definida. Não há
entrada nem saída observáveis.

**Proposta em duas partes:**
1. **Acrescentar ao §21** o comando `chaos vault import <dir> [--dry-run]`, que
   inventaria, classifica e relata — sem apagar nada.
2. **Reescrever o AT** como: importar uma pasta legada contendo arquivos que não
   se encaixam em nenhum schema produz um relatório que lista **todos** os
   arquivos de entrada; os não mapeáveis vão para `inbox/` com
   `provenance.origin: external_source`; nenhum arquivo de origem é apagado ou
   alterado. "Sem perda silenciosa" vira: entrada e relatório têm a mesma
   contagem.

---

## #6 — AT-13 mistura conformidade com avaliação de comportamento

**Como está:** "instrução embutida em item do inbox não altera comportamento do
agente e é registrada como warning."

**Problema:** a segunda metade é determinística e testável. A primeira exige
observar um modelo de linguagem **decidir** — resultado probabilístico, que varia
com o modelo, a temperatura e o prompt. Um portão de conformidade (Definition of
Done) que depende disso ou fica instável, ou é satisfeito com um caso fácil e não
prova nada.

**Divisão proposta:**
- **AT-13 (conformidade, fica na DoD):** item entrando pelo inbox recebe
  `provenance.origin: external_source`; o Context Builder o marca `untrusted`; o
  `guard` **nega** ação A2+ de um RUN cuja única justificativa seja fonte
  `untrusted`; a tentativa gera EVT com warning. Tudo isto é código, não modelo.
- **Eval de resistência a injeção (fora da DoD):** suíte separada, com casos
  adversariais, medida por taxa e acompanhada ao longo do tempo — não é portão
  binário de release.

Esta é a única defesa que não depende do modelo se comportar bem, e é justamente
a que estava embutida num teste que dependia disso.

---

## #7 — AT-26 exige fixture que a suíte não tem (lacuna da suíte, não da spec)

**Como está:** a metade "entidade com `migrated_to` é read-only" é testável com um
repositório só. A outra metade — mesmo ID no destino, `migrated_from` apontando de
volta, nenhum EVT atravessando a fronteira (§17.5) — exige **dois repositórios de
classes de privacidade diferentes**, e `chaos init` cria uma classe por vez.

**Ação:** construir a fixture `repo_pair` na suíte. Não é defeito do CHAOS; é
trabalho pendente aqui, registrado para não se perder.

---

## O que isto sugere sobre o método

Os seis defeitos de spec têm a mesma forma: **o AT descreve uma propriedade
desejável em vez de um experimento**. Prosa aceita "funciona sem X" e "sem perda
silenciosa"; um teste exige dizer o que se monta, o que se executa e o que se
observa. Oito rodadas de leitura adversarial não pegaram nenhum deles.

Sugestão para as próximas especificações: escrever cada AT já no formato
**arranjo → ação → asserção**. Um AT que não couber nesse formato é uma intenção,
não um critério de aceitação — e não deveria travar uma Definition of Done.
