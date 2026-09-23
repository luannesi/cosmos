# Achados da implementação — o que só apareceu ao escrever o código

Cada item abaixo é uma contradição ou lacuna que doze rodadas de leitura
adversarial não pegaram. Mesma lição de sempre: contato com a realidade acha o
que releitura não acha.

---

## 1. AT-01 e AT-07 se contradizem (suíte)

**O defeito.** Os dois fazem *exatamente* a mesma coisa — humano acrescenta uma
linha ao corpo de uma entidade e comita direto — e esperam resultados opostos:
AT-01 exige que `chaos validate` **aceite** ("o validador reconcilia"), AT-07
exige que **recuse** com violação `integrity` ("commit sem EVT é detectado").

**Resolução, com base em texto normativo.** Implementação §11 é explícita:
*"Edição manual no Obsidian é aceita para humanos; o validador reconcilia.
Toda escrita de entidade por agente passa pelo CLI."* A exigência de EVT é sobre
**executores**, não sobre o humano — exigi-la do humano tornaria o repositório
ineditável à mão, que é justamente a promessa do AT-01.

**O que muda:** o validador só exige EVT para commits de credencial de executor.
O arranjo do AT-07 passa a comitar com identidade de executor. Uma linha de teste.

---

## 2. `hardware-profile.yaml` → dois nomes de schema (CHAOS §20 × Implementação §4.5)

CHAOS §20 diz que `<dir>/<nome>.yaml` valida contra
`metadata/schemas/<nome>.schema.json` — resolução por radical do nome. A tabela
da Implementação §4.5 mapeia `hardware-profile.yaml` para `hardware.schema.json`.
Os dois não podem estar certos.

**Resolução:** vale §20, que é o contrato; a tabela do binding é que está errada.
Schema renomeado para `hardware-profile.schema.json`.

---

## 3. `run` e `inbox` são tipo de entidade E comando (CHAOS §21)

§21 declara `chaos <tipo> create|update|show|list` para todo tipo de §7.3 — o que
inclui `run` e `inbox` — e também `chaos run merge|reset|repair` e
`chaos inbox add`. Em argparse isso é colisão direta de subcomando.

Não é defeito do contrato, é uma consequência dele que a spec não menciona: o
mesmo parser serve aos dois usos. Registrado para que a próxima implementação não
trope na mesma pedra.

---

## 4. `merge=union` não pode manter ordem física (CHAOS §17.1 × AT-16)

**O defeito.** §17.1 manda `merge=union` no ledger; a AT-16 exigia que, depois do
merge, os `ts` estivessem em ordem crescente. O driver de união **concatena** os
dois lados sem conhecer a semântica das linhas — não ordena, e não tem como.
Numa corrida real ele produz `ours` antes de `theirs`, e o lado local costuma ser
o mais recente. A asserção era impossível de satisfazer.

**Resolução.** A ordem do ledger é da **leitura**, não do disco. O que o formato
garante é ausência de perda e `ts` como chave de ordenação total; quem precisa de
cronologia ordena ao ler. §17.1 e a AT-16 foram corrigidas; `chaos audit verify`
passou a conferir integridade (sem `event_id` duplicado) em vez de ordem física.

**Alternativa descartada:** driver de merge próprio que ordena. Exigiria
`git config merge.<driver>.driver` em cada clone — e um clone fresco sem essa
config cai no driver padrão **em silêncio**, que é pior que o problema.

---

## 5. `minimum_tier` não dizia em que direção (ORDER §21.3)

A regra mandava "aplicar `tier_preference`" sem declarar se a preferência é pelo
maior ou pelo menor tier aceitável. Implementado como **menor tier que satisfaz o
piso**: preferir o maior gastaria capacidade cara em trabalho barato, e uma
policy `classify` com piso `low` servida por `mid` é desperdício silencioso —
invisível até a fatura. §21.3 atualizada.

---

## 6. O HND apontava para a subtarefa, não para a tarefa de origem (ORDER §10.1)

Ao implementar a delegação ficou claro que "o receptor reconstrói o contexto só
com HND + CHAOS" exige que o handoff ancore na tarefa **que motivou** a
delegação; a subtarefa criada é consequência, e vai em `context_refs`. §10.1
atualizada.

---

## 7. `audit/events.jsonl` protegido bloqueava o próprio adapter

§4.1 lista `audit/**` como protected path e §17.1 diz que "o ledger só cresce
pelo adapter, que qualquer executor invoca". Na prática as duas regras se
chocavam: o commit de qualquer executor toca `events.jsonl` e era recusado.

**Resolução — a regra verificável não é *quem*, é *como*:** `chaos commit` aceita
`audit/events.jsonl` quando a mudança é **append puro** (o arquivo em disco começa
com a versão comitada) e recusa qualquer reescrita. Isso é mais forte que a lista
de permissões original, porque passa a barrar também um humano que reescreva o
log — e append-only existe justamente para isso.

---

## 8. O que ficou deliberadamente isolado

A derivação de ator a partir da credencial (§17.1) vive em `tools/chaos/repo.py`
(classe `Identidade`) e a checagem cruzada no validador em
`validador._identidade()`. **É a única parte cuja forma depende do spike de
identidade.** Se a sessão na nuvem puder escolher a própria identidade, muda esse
par de lugares — não o resto.

---

## 9. Três motores sem comando na CLI (ORDER §3 × §38)

§3 declara que o ORDER **contém** Workflow Engine, Notification Adapter e Model
Gateway. §38, que é "o contrato completo" da CLI, não dava comando a nenhum dos
três. Um motor sem superfície é um motor que ninguém invoca, inspeciona nem
testa — e os três estavam nessa situação.

É o defeito das oito operações fantasma da 9ª rodada **pelo avesso**: lá, os AT
usavam comandos que a CLI não declarava; aqui, a spec declara motores que a CLI
não alcança. O teste `test_nenhum_comando_fantasma` pega o primeiro caso e é
cego para o segundo.

**Resolução:** `order workflow list|show|run`, `order notify` e `order model call`
acrescentados a §38.

---

## 10. `chaos area` e as consultas de grafo não existiam

CHAOS §9 exige Área State e ORDER §23 manda injetá-lo no início de todo contexto
de agente; não havia comando que o criasse ou mantivesse. §15 nomeia três
consultas de grafo — vizinhos, caminho, subárvore — e o grafo era **gravado e
nunca lido**. Índice que ninguém consulta é peso morto que ainda por cima
precisa ser mantido em dia.

**Resolução:** `chaos area create|sync|show|list` e
`chaos graph neighbors|path|subtree` em §21.

---

## 11. `any(glob(...))` é sempre verdadeiro

No fechamento de sessão, a condição "houve RUN ou HND?" estava escrita como
`any(diretorio.glob(padrao) for ...)`. Um gerador é sempre *truthy*, mesmo
vazio — então toda sessão criava SES, que é precisamente o que CHAOS §7.4 evita
("SES só vira arquivo se houve RUN ou HND; caso contrário, apenas EVT").

Bug clássico de Python, invisível em revisão, achado ao rodar. Vale registrar
porque a classe é recorrente e o sintoma é silencioso: nada falha, só aparecem
arquivos a mais para sempre.

---

## 12. Um guard que trata sessão de modelo como escrita humana não protege nada

A primeira versão do hook `PreToolUse` derivava o ator da credencial Git da
máquina. Numa máquina cujo dono é o proprietário, isso resolvia para
`human:owner` — e o guard liberava protected path, porque humano pode escrever.

**Mas numa sessão do Claude Code quem escreve é o modelo, não a pessoa.** O hook
passou a declarar o ator explicitamente (`cloud:claude-code` ou o agente ativo),
e o `order guard` passou a negar protected path para **qualquer ator que não
comece com `human:`** — em vez de só para `agent:*`.

É a confusão exata que a derivação de ator (§17.1) existe para evitar, e ela
reapareceu na camada de cima.

---

# Rodada v2.6 — implementação da âncora de assinatura (21/09/2026)

Achados de **implementar** o resultado do spike, não de planejá-lo. Os quatro
primeiros só apareceram porque o código rodou.

---

## 13. O exemplo de `allowed_signers` da especificação não funcionava

§17.6 foi escrita com as opções separadas por **espaço**:

```
luan@exemplo.com namespaces="git" valid-after="20260921" ssh-ed25519 AAAA...
```

O OpenSSH exige **vírgula**, num único campo. Com espaço, ele lê o segundo campo
como início da chave e rejeita a linha inteira com `invalid key`.

O efeito é pior que um erro de sintaxe, e é por isso que vale um achado: o
`git log --format=%G?` devolve **`U`** em vez de `G` — "assinatura boa, validade
desconhecida". Uma assinatura legítima que não verifica, uma aprovação legítima
negada, e nenhuma mensagem que aponte para a vírgula. A especificação foi
corrigida com o motivo escrito ao lado, porque a forma errada é a que qualquer
um escreve por analogia com outros formatos de configuração.

Descoberto em dez minutos ao rodar o primeiro `verificar_commit` contra um
repositório real. Nenhuma releitura teria encontrado.

---

## 14. Exigir assinatura de todo commit impede o repositório de existir

A primeira versão de `_assinatura()` verificava todos os commits que tocam
protected path. O `chaos init` toca 80 deles — ele **cria** o layout inteiro,
incluindo o próprio `allowed_signers` — e não pode ser assinado, porque no
momento em que roda não existe chave nenhuma.

Resultado: nenhum repositório recém-criado passava no validador. O sistema
exigia que a raiz de confiança existisse antes de ser criada.

A correção é uma janela de vigência: a regra vale a partir do commit que
registrou a **primeira chave humana**. Esse commit é o único isento, e a
isenção é consciente — quem escreve a primeira linha define quem é humano.
§17.6 a fecha do lado certo: acontece no Onboarding, antes de existir agente.

Um detalhe do critério que só ficou claro ao escrever o AT-36: a condição de
isenção é "**nunca existiu** chave humana", não "não há chave vigente hoje".
Se fosse a segunda, expirar a última chave devolveria o repositório ao estado
inicial — isto é, **relaxaria** o controle exatamente quando ele acabou de ser
revogado. Com a primeira, expirar a última chave deixa o sistema sem caminho de
aprovação, que é falhar fechando.

---

## 15. Vigência tem de ser avaliada na data do commit, não em hoje

Corolário do anterior, e o mais sutil dos quatro. Verificar `valid-before`
contra a data de hoje faz com que expirar uma chave torne inválidos,
retroativamente, todos os commits que ela assinou — inclusive o próprio commit
que registrou a expiração.

Isto apaga a diferença entre **revogar** e **adulterar**, que é justamente o que
§17.6 existe para preservar. A verificação passou a ler `%ad` do commit e
avaliar a vigência naquela data. AT-38 trava as duas metades: expirar mantém o
passado verificando; apagar a linha é violação.

---

## 16. AT-07 passava pela regra errada

Ao rebaixar "identidade de executor sem trailer" de `integrity` para aviso,
AT-07 ("commit sem EVT é detectado") começou a falhar — e a investigação
mostrou que ele **nunca** havia testado o que dizia testar. A regra de EVT em
`_auditoria` só olhava entidades com **zero** eventos no ledger; uma entidade
que já tinha histórico podia ser editada à mão por um executor sem que nada
acusasse. O teste passava porque a *outra* regra, a de trailer, pegava o commit
por outro motivo.

Duas correções: "evento correspondente" passou a ser por **escrita**, não por
entidade (contagem de commits de executor versus contagem de EVTs de executor);
e só EVT de executor cobre commit de executor — um evento gravado pelo humano
ao criar a entidade não justifica uma escrita crua que um executor fez depois.

O padrão vale mais que o caso: **um teste verde não prova que a regra que ele
nomeia existe** — prova que alguma regra reprovou aquele arranjo. Remover uma
regra é a única forma barata de descobrir quais testes dependiam dela.

---

## 17. Sem chave registrada, metade da suíte do ORDER parava

Ao fazer `_abrir_aprovacao` recusar quando não há chave humana (AT-31), todo AT
que passa por A3+ quebrou, a começar por AT-05. Não é defeito: é o contrato
novo. Um repositório sem raiz de confiança não aprova com menos rigor — não
aprova. A fixture `chaves` entrou nos AT que precisam de aprovação, e a
distinção ficou explícita no docstring de cada um.

Vale registrar porque a tentação, no momento, é óbvia e errada: fazer a ausência
de chave cair num modo permissivo "só para os testes passarem". Seria reabrir o
buraco da v2.5 com um nome simpático.

---

## 18. Saída de ferramenta externa no stdout de um comando que devolve JSON

`chaos key new` chamava `ssh-keygen` deixando-o herdar o stdout. O randomart e o
"Your identification has been saved" caíam no meio do JSON do comando, e
qualquer consumidor quebrava na primeira linha.

A correção óbvia — `capture_output=True` — estaria errada: a chave humana pede
**frase-secreta de forma interativa**, e capturar a saída mataria o prompt, que
é justamente o controle que §17.6 exige. A saída do `ssh-keygen` passou a ir
para stderr; o prompt continua funcionando e o stdout continua sendo JSON.

Pequeno, mas registra uma classe: **todo comando que devolve dado estruturado e
invoca ferramenta externa precisa decidir para onde vai a saída da ferramenta**,
e a decisão não é sempre "capturar".

---

## 19. A janela da primeira chave, fechada do lado possível

O achado #14 deixou uma concessão explícita: o commit que registra a primeira
chave humana é isento de assinatura, porque não há chave quando ele roda. Quem
executa `chaos init` define quem é humano.

`chaos init` passou a recusar rodar sob ator declarado que não comece com
`human:`. Não é defesa forte e não finge ser — quem controla a variável de
ambiente controla a declaração. É defesa contra o caso realista: uma sessão de
agente que, por instrução embutida ou por engano, rode `chaos init` num
diretório e se registre como a primeira chave humana. Contra adversário com
shell na máquina, a barreira é a frase-secreta.

Vale escrever a diferença em vez de deixá-la implícita: uma barreira honesta
sobre o que não cobre é utilizável; uma que se apresenta como completa convida
a parar de procurar a próxima.

---

## 20. A quarta camada de enforcement faltava no CI

O CI rodava `chaos validate`, que já inclui a checagem de assinatura — mas só
no ramo principal e sobre o repositório inteiro. Faltava a verificação por
commit no Pull Request, que é onde a escrita em protected path chega vinda de
fora. `validate.yml` ganhou um job que percorre `base..head` e exige `%G? = G`
em todo commit que toque protected path, com a mensagem nomeando o erro que o
spike produziu: autor e committer humanos não bastam.

---

## 21. A regra de assinatura tornaria o ledger inescrevível

Ao fazer o worker assinar por padrão, `chaos validate` passou a reprovar os
próprios commits dele: `audit/events.jsonl` está em protected paths, e a nova
regra exigia assinatura **humana** em todo commit que tocasse um.

A exceção já existia no caminho de escrita desde a primeira leva (achado #3):
o que se proíbe em `audit/**` é **reescrita**, não crescimento, e
`_recusar_protegidos` verifica isso comparando a versão em disco com a
comitada. A regra nova não conhecia a exceção e, por pouco, não passou sem
ela — exigir assinatura humana por linha de auditoria tornaria o ledger
inescrevível por quem o alimenta, que é o oposto do que §17.1 quer.

A classe vale registro: **uma regra nova sobre um conjunto de caminhos herda as
exceções que aquele conjunto já tinha, e nada obriga o autor a lembrar-se
delas.** A exceção estava a trinta linhas de distância, em outra função, e o
sintoma só apareceu porque um teste exercitou o worker assinando — nenhum
teste anterior o fazia.

---

## 22. Um commit assinado que o usuário lê como não assinado

`git log --format=%G?` devolve `N` — "sem assinatura" — quando o repositório
não tem `gpg.ssh.allowedSignersFile` configurado, mesmo num commit que **está**
assinado. Descoberto ao escrever o teste de procedência: o commit tinha o bloco
`gpgsig` no objeto e o Git relatava ausência.

Para as ferramentas isso nunca foi problema — elas passam `-c` em toda
verificação, de propósito, para não depender de configuração local. Para o
humano é péssimo: ele olha o histórico na própria máquina e vê o oposto da
verdade.

`chaos init` e `chaos bootstrap sync` passaram a configurar o Git local do
repositório. Não é segurança e está escrito como não sendo; é legibilidade —
e a diferença entre "não verificável" e "não assinado" é exatamente a que o
sistema inteiro existe para preservar.

---

# Rodada v2.6b — montagem do pacote portátil

## 23. `uv pip download` não existe

A Implementação §18.2 e o Apêndice A do tutorial mandavam baixar as rodas com
`uv pip download`. O `uv pip` tem `compile`, `sync`, `install`, `uninstall`,
`freeze`, `list`, `show`, `tree` e `check` — e nenhum `download`.

A spec descrevia uma operação inexistente com a segurança de quem a tinha
usado. Passou por duas rodadas de revisão porque **é plausível**: o `uv pip` é
deliberadamente pip-compatível, e o pip tem `download`.

Correção: o venv passa a ser criado com `--seed`, que traz o pip, e quem baixa
as rodas é o pip de dentro do próprio venv. As rodas viraram conveniência
explícita — o venv já viaja com as dependências instaladas —, então falhar o
download avisa em vez de abortar.

---

## 24. O pacote sairia com um Python que não existe no destino

O mais grave dos três, e invisível sem rodar: `uv venv --python 3.13` numa
máquina de montagem que **já tenha** Python 3.13 usa o do sistema. A pasta
`python/` do pacote fica vazia, o `pyvenv.cfg` do venv aponta para
`/usr/bin/...` ou `C:\Python313\...`, e o ZIP sai com tamanho plausível, sem
erro nenhum. Quebra na primeira máquina de destino, com uma mensagem sobre
interpretador ausente que não sugere a causa.

Duas defesas, porque uma só não basta: `--managed-python` força o Python do
pacote, e o script **confere depois** que `python/` não ficou vazia e que o
`home` do `pyvenv.cfg` aponta para dentro do pacote. A segunda é o que importa:
a primeira depende de uma flag que alguém pode remover ao editar o script.

Vale o registro do padrão: **um pacote portátil falha silenciosamente na
máquina errada.** Toda verificação que só roda na máquina de montagem verifica
o caso fácil. As asserções que valem são as que descrevem o que o destino vai
encontrar.

---

## 25. A verificação de segredos precisava ser executável, não normativa

§18.3 dizia "nenhuma credencial, nenhuma exceção" desde a v1.3, e era prosa. A
montagem passou a varrer o pacote antes de compactar: cabeçalho de chave
privada em qualquer arquivo de texto, `*.pem`, `*.key`, `.env*`, e
`allowed_signers` com qualquer linha não comentada. É a única etapa que aborta
em vez de avisar.

A regra ficou mais grave com a v2.6 e por isso mereceu código: quando a
garantia dependia de identidade Git, uma chave vazada no pacote era um problema
sério; agora que depende de assinatura por chave que existe numa máquina só,
uma chave no pacote estaria em toda máquina que o baixou — e a marca deixaria
de significar "esta pessoa, nesta máquina" para significar "quem quer que tenha
descompactado". Pior do que não ter assinatura, porque teria a aparência de
garantia.

---

## 26. As CLIs não executavam na plataforma-alvo

`bin/chaos` e `bin/order` são scripts Python com shebang. O POSIX honra
shebang; **o Windows não**. Apontar a suíte para o arquivo sem extensão
funciona no Linux e falha no Windows com um erro de formato que não sugere a
causa — e o Windows é a plataforma para a qual este sistema foi desenhado
desde a décima segunda rodada, quando descobrimos que a tabela de negação do
guard era inteiramente POSIX.

O defeito sobreviveu a três levas de implementação e a 134 testes de aceitação
porque **todos rodaram em Linux**. Nenhum teste podia encontrá-lo: eles
exercitam o contrato, e o contrato estava certo — o que estava errado era
poder invocá-lo.

Duas correções, porque servem a usuários diferentes: invólucros `.cmd` ao lado
de cada script, para o uso interativo e para o `tools-seed` do pacote portátil;
e `_invocacao()` no harness da suíte, que no Windows prefere o `.cmd` e, na
falta dele, chama o interpretador explicitamente — assim a suíte não depende de
o usuário ter apontado o caminho certo.

Achado ao **escrever o runbook de instalação**, não ao rodar nada. Redigir o
comando que outra pessoa vai digitar obriga a imaginar a máquina dela, e foi
isso que expôs a diferença. Vale como método: escrever a instrução é uma forma
barata de testar a hipótese de que o sistema é utilizável.

---

## 27. O Onboarding exigia um humano que só o Onboarding podia criar

`chaos onboarding run` recusava rodar em qualquer repositório recém-criado,
sempre, para qualquer pessoa: `"[policy] o Onboarding é do proprietário: ele
define classes de privacidade, identidades e cotas (§3)"`.

A causa era circular. `chaos init` grava `executors.yaml` com placeholders
(`owner@example.invalid` etc. — RFC 2606, de propósito: §3 diz que é o
Onboarding quem substitui pelos e-mails reais, pergunta `human_email`).
`Identidade.eh_humano` deriva o ator cruzando `git config user.email` contra
esse mesmo arquivo; com só placeholder lá, nenhuma credencial bate, e
`eh_humano` é `False` — sempre, pra qualquer humano real, porque o arquivo que
provaria a humanidade dele é o arquivo que o comando bloqueado existe pra
escrever.

`assinatura.commit_da_primeira_chave_humana` já documentava essa janela — "ela
acontece no Onboarding, antes de existir agente" — e `chaos init` já tinha a
defesa certa pro mesmo problema (§17.6: olhar o que o ambiente *declarou*
via `CHAOS_ACTOR`, não o registry, porque o registry ainda não existe). O
Onboarding não herdou essa defesa; ganhou uma checagem forte (`eh_humano`,
via registry) que só faz sentido depois que o próprio Onboarding já rodou.

Não apareceu em nenhuma das 134 rodadas de teste de aceitação pelo mesmo
motivo do achado 26: harness de teste não passa por `chaos init` seguido de
`chaos onboarding run` numa credencial Git nova de verdade — ou já parte de
um `executors.yaml` populado, ou roda sob uma identidade que o teste registra
por fora. Só apareceu na primeira instalação real, ponta a ponta, numa
credencial que nunca tinha existido em nenhum registry (Parte 4 do
`EXECUTAR_COSMOS.md`).

Correção em `cmd_onboarding`: quando `ident.entrada()` é `None` (bootstrap),
cai pra a mesma defesa fraca-mas-deliberada do `init` — bloqueia só se
`CHAOS_ACTOR` foi declarado como não-humano, ou se uma chave humana **já**
foi registrada (janela fechada, via `commit_da_primeira_chave_humana`) — e
usa o único executor `kind: human` do registry como ator efetivo pra
`materializar`/`ledger`, já que `ident.ator` também levantaria sem
credencial batendo. Fora da janela de bootstrap, a checagem forte
(`eh_humano`) continua valendo exatamente como antes.

---

## 28. O default de uma pergunta de lista virava string quando aceito digitando Enter

`chaos onboarding run` grava respostas erradas sem avisar sempre que a
pergunta é de lista (`lista=True`) **e** a pessoa aceita o default apertando
Enter em vez de digitar algo. Ex.: `allowed_channels` (default `"self"`)
vira o texto solto `self` em `metadata/repo.yaml`, não a lista `["self"]`;
pior, `automations` (default `"briefing-diario"`) some por trás de
`list("briefing-diario")` em `materializar` — que itera **caractere por
caractere** da string, e teria criado uma automação por letra
(`b`, `r`, `i`, ...) se o Onboarding tivesse chegado até lá nessa rodada.

Achado ao rodar o Onboarding de verdade pela primeira vez (Parte 4.3),
gravando `D:\personal-assistant`: o `git status` mostrou `allowed_channels:
self` como string solta em vez de lista, o que só é visível olhando o
arquivo gravado — o comando não erra, não avisa, só grava o tipo errado.

Causa: das três rotas que `coletar()`/`_normalizar()` usam pra resolver o
valor de uma pergunta (arquivo de respostas, digitado, default sem
interação), duas já convertiam string-com-vírgula em lista quando
`p.lista`; só a rota "default aceito com Enter em modo interativo", dentro
de `_normalizar()`, retornava `p.default` cru. Não é uma pergunta rara —
é toda pergunta de lista com default não vazio (`surfaces`, `allowed_channels`,
`capture_ignore`, `functionals`, `automations`), sempre que a resposta for
"aceito o que já está mostrado".

Correção: `_normalizar()` agora faz a mesma conversão nessa rota também —
lista com vírgula vira lista de verdade antes de voltar, igual às outras
duas rotas. Sem isso, qualquer Onboarding real ia embutir esse defeito
silenciosamente cedo ou tarde — é o caminho que a maioria escolhe (aceitar
o default é o comum; digitar de novo o que já está na tela, não).
