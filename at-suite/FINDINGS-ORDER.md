# Achados da tradução dos AT do ORDER para código — ORDER §44

**AT** = *Acceptance Test* (teste de aceitação). **CLI** = *Command Line Interface*.
**DoD** = *Definition of Done*.

Dos 25 AT do ORDER, dois não são escrevíveis. Mas o achado principal desta metade
não está nos AT: está na **CLI**, que é a superfície de contrato que eles exigem.

---

## #1 — As duas CLIs do `order` divergem (o achado mais sério)

ORDER §38 e Implementação §11 declaram, cada uma, 22 comandos `order`. **Apenas 10
são comuns.**

| Só em ORDER §38 | Só em Implementação §11 |
|---|---|
| `task submit\|claim\|release\|resume` | `trigger fire\|scan` |
| `agent list\|run` | `risk eval` |
| `model list\|route` | `guard` |
| `audit inspect` | `delegate` |
| `health` | `session open\|close` |
| `pause\|resume` | `agents sync` |
| | `quota status`, `report`, `run merge\|resume` |

Três conflitos diretos, não apenas omissões:

- **Kill-switch com dois donos:** `order pause|resume` (§38) e `chaos pause|resume`
  (CHAOS §21) fazem a mesma coisa. Qual delas o AT-09 exercita? Qual o hook chama?
- **`task resume` × `run resume`:** §38 retoma tarefa, Implementação retoma RUN.
  São objetos diferentes com ciclos de vida diferentes.
- **`agents sync` × `agent list|run`:** namespaces distintos (`agents` e `agent`)
  para o mesmo domínio.

Isto passou despercebido em nove rodadas porque nenhuma leu as duas listas lado a
lado. A suíte leu, porque precisava escolher qual invocar.

**Correção aplicada:** ORDER §38 passa a ser a CLI completa — é a spec, e o binding
não pode declarar operações que o contrato desconhece. Implementação §11 passa a
referenciá-la em vez de manter lista paralela, acrescentando só o que é específico
do Perfil A. Kill-switch fica no `chaos` (é estado no repositório, não do runtime),
e `order pause|resume` some.

---

## #2 — Oito operações que os AT exigem não existem em nenhuma CLI

Traduzir os AT obriga a enumerar o que o sistema precisa **saber fazer**. Oito
operações necessárias não estão declaradas em lugar nenhum:

| Operação | Exigida por | Gravidade |
|---|---|---|
| `run checkpoint` | AT-08, AT-11, AT-21 do CHAOS | **crítica** — todo o contrato de retomada (§7.4) depende dela |
| `run claim` | AT-07, AT-18 | alta — é o passo 1 do Task Queue Protocol (§11) |
| `run act` | AT-05, AT-13 | alta — é onde risco e permissão são aplicados |
| `approval create` | AT-05, AT-19 | alta — APV nasce de alguma coisa |
| `approval expire` | AT-05 | média — §18 exige expiração |
| `automation create` | AT-11 | média — a escada de maturidade começa em algum lugar |
| `quota consume` | AT-10 | baixa — pode ser efeito colateral, mas o teste precisa forçar |
| `hardware set` | AT-24 | baixa — pode ser edição de policy |

`run checkpoint` é o caso que vale reter: as rodadas 4 a 8 gastaram muito esforço
no **contrato** de checkpoint — campos obrigatórios, `version_hash`, precedência de
merge, o que acontece quando está incompleto — sem que nenhuma delas notasse que
**não há comando declarado que grave um checkpoint**. O contrato de um dado que
nenhuma operação produz.

---

## #3 — Três AT do ORDER duplicam AT do CHAOS, e já divergiram

| ORDER | CHAOS | Situação |
|---|---|---|
| AT-12 Protected paths | AT-15 Protected paths | mesma regra, dois testes |
| AT-13 Untrusted | AT-13 Untrusted | **já divergiram**: o do CHAOS foi dividido na 9ª rodada, o do ORDER não |
| AT-14 Privacy | AT-14 Privacy | sobrepostos |

A DoD de cada spec exige a sua suíte, então a mesma regra é travada duas vezes — e
quando uma é reescrita, como aconteceu agora, as duas passam a exigir coisas
diferentes do mesmo mecanismo.

**Correção aplicada:** os pares sobreviventes ganham escopo explícito e
complementar. O CHAOS testa as **camadas** (hook nega, validador rejeita,
CODEOWNERS bloqueia); o ORDER testa o **motor** (Permission Engine decide e
registra a tentativa). AT-13 do ORDER recebe a mesma divisão já aplicada ao CHAOS.

---

## #4 — AT-07 e AT-18 são o mesmo teste

AT-07: "dois executores tentando o mesmo claim → exatamente um vence."
AT-18: "claims simultâneos por dois executores terminam com exatamente um RUN
`claimed` e nenhum conflito de merge pendente."

AT-18 é AT-07 mais uma condição. Um arranjo, duas entradas na contagem da DoD.

**Correção aplicada:** AT-07 cobre o resultado da corrida; AT-18 passa a cobrir
especificamente o que acontece com o **perdedor** — descarte do claim sem rebase,
sem marcador de conflito, sem RUN órfão —, que é a parte que a Implementação §8.1
detalha e ninguém testava.

---

## #5 — AT-22 exige "a mesma suíte de casos" que a spec não enumera

AT-22: "o worker local nega em processo as mesmas ações que o hook nega na nuvem
(mesma suíte de casos)."

A asserção de igualdade é boa e o teste correto é justamente paramétrico. Mas
"mesma suíte" não existe na spec: nada diz quais são os casos, então duas
implementações podem satisfazer o AT com conjuntos diferentes e ambas alegar
conformidade.

**Correção aplicada:** os casos passam a ser enumerados em ORDER §16 (a lista
mínima: interpretadores, redirecionamento, `git` de escrita, protected paths,
`audit/` direto). A suíte os consome de uma tabela única, `GUARD_CASES` em
`harness.py`, partilhada entre os testes de AT-20 e AT-22 — é o partilhamento que
dá sentido a "mesma".

---

## #6 — AT-16 é uma afirmação arquitetural, não um experimento

AT-16: "troca de provedor ou de perfil preserva agentes e contratos."

Trocar de **perfil** é substituir o runtime inteiro (Perfil A → Perfil B). Só é
observável tendo duas implementações completas — o que nenhuma suíte de
conformidade de uma implementação pode montar. Como portão de DoD, é
insatisfazível até a segunda existir, o que na prática significa que ninguém o
executa e ele passa por omissão.

**Correção aplicada:** vira teste de **ausência de acoplamento**, que é o
invariante verificável por trás e é checável hoje: nenhum identificador de
provedor, modelo, runtime ou perfil aparece no registry de agentes ou no
frontmatter de qualquer entidade; trocar `model-registry.yaml` inteiro não exige
editar nenhum agente nem nenhuma entidade; nenhuma entidade referencia `litellm`,
`ollama`, `claude`, `openai` ou nome de produto.

---

## #7 — AT-13 do ORDER continua comportamental

Mesmo defeito que o AT-13 do CHAOS tinha antes da 9ª rodada: exige observar um
modelo **decidir** não obedecer a uma instrução embutida. Portão binário de DoD
sobre resultado probabilístico.

**Correção aplicada:** mesma divisão — parte determinística (Permission Engine
nega A2+ justificada só por fonte `untrusted`, e registra) fica no AT; resistência
do modelo vai para eval, sob CHAOS §30.1, fora da DoD.

---

## O que os dois conjuntos de achados têm em comum

Na metade CHAOS, seis AT descreviam **propriedade em vez de experimento**. Nesta
metade, os AT estavam em melhor forma — mas exigiam uma superfície de contrato que
as specs declaram de dois jeitos incompatíveis e que, em oito operações, não
declaram de jeito nenhum.

A leitura adversarial verifica se o texto é coerente consigo mesmo. Escrever o
teste verifica se existe **alguma coisa para executar**. São perguntas diferentes,
e a segunda só aparece quando alguém tenta rodar.

---

# Rodada 10 — a outra metade do achado #1

O achado #1 acima dizia que as duas listas do `order` divergiam. A correção
reconciliou o `order` e **não conferiu o `chaos`** — que tinha exatamente o mesmo
defeito, encontrado na rodada seguinte.

**CHAOS §21 × Implementação §11:** 25 e 21 comandos declarados, 12 em comum. E o
pior caso possível: **§21 não declarava `chaos commit` nem `chaos sync`**. Desde a
3ª rodada esses dois são o único caminho de commit e sincronização para agentes —
injetam os trailers antes do commit, recusam protected paths, implementam a
política de merge. O controle mais citado das três specs não existia na CLI que o
CHAOS declara.

Três consequências da reconciliação da 9ª rodada que ficaram para trás:

- **Seis referências órfãs a `order agents sync`** (plural), depois de §38 passar a
  declarar `agent sync` (singular), em Implementação §3.3, §5.3, §13 (duas fases) e
  ORDER §8.4 e §21.2.
- **`order automation sync`** usado no corpo da Implementação §5.2 e ausente de §38.
- **Dois testes invocando a CLI errada:** `chaos guard` (guard é do `order`) e
  `chaos policy set` — comando que não existe e **não deve existir**: policies são
  protected paths editados por humano fora do caminho do modelo; um comando que as
  escrevesse seria o alvo óbvio de qualquer escalação. Está agora dito em §21.
- **`GUARD_CASES` cobria 5 das 6 classes** que ORDER §16 declara mínimas — faltava
  `editor` (`sed -i`, `tee`). A suíte não verificava o mínimo da própria spec.

## O que mudou no método

Estes cinco defeitos são todos *consequência* de uma correção anterior, não do
material original. Corrigir uma spec grande produz destroços, e nove rodadas de
leitura não os pegaram.

A resposta foi `tests/test_contract_consistency.py`: oito testes sobre as
**especificações**, que rodam sem implementação nenhuma. Verificam que nenhum
comando usado pelos AT falta na CLI declarada; que a Implementação referencia as
CLIs em vez de duplicá-las; que `GUARD_CASES` cobre o mínimo de §16; que as DoD não
fixam faixa numérica de AT; e que os AT estão numerados sem lacuna e todos têm
teste.

Cada um deles nasceu de um defeito real das rodadas 7 a 10. É a diferença entre
corrigir a instância e fechar a classe.
