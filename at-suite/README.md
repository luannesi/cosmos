# Suíte de conformidade CHAOS v2.5 / ORDER v2.5

**AT** = *Acceptance Test* (teste de aceitação). **CLI** = *Command Line Interface*.
**DoD** = *Definition of Done* — o portão de conformidade de cada especificação.

Os AT de CHAOS §30 e ORDER §44 escritos como código executável. As DoD de ambas as
specs exigem que a suíte inteira passe, então isto **é** o portão: enquanto um teste
falha, a fase correspondente não está entregue.

## Estado

| | |
|---|---|
| CHAOS §30 | 35 AT, todos escritos |
| ORDER §44 | 29 AT, todos escritos |
| Total | 124 casos executáveis (contando parametrizações), 0 inviáveis |
| Consistência | 10 testes sobre as specs, que **rodam sem implementação** |
| Achados | 6 em `FINDINGS.md` (CHAOS), 7 + 5 em `FINDINGS-ORDER.md` |

## Uso

```bash
pip install pytest pyyaml jsonschema
pytest --chaos-bin=/caminho/para/chaos --order-bin=/caminho/para/order \
       --episodic-bin=/caminho/para/ai-memory      # opcional (CHAOS §4.2)
```

Sem `--episodic-bin`, os AT da camada episódica são pulados — a camada é opcional,
e o AT-34 verifica justamente que o sistema inteiro passa sem ela.

Sem `--chaos-bin` a suíte **pula** com motivo explícito, nunca passa em verde: uma
suíte de conformidade que fica verde sem implementação é pior que nenhuma, porque
transmite garantia falsa.

Seleção por marcador:

```bash
pytest tests/test_contract_consistency.py   # só as specs — não precisa de implementação
pytest -m chaos                    # só CHAOS §30
pytest -k at21                     # um AT específico
pytest -m "not needs_two_executors"  # pula o que exige dois clones
```

## Como a suíte enxerga o sistema

A superfície de contrato é a **CLI**, não o código: CHAOS §21, ORDER §38 e
Implementação §11 declaram que toda escrita de entidade passa por ela. Os testes
invocam `chaos` e `order` como subprocessos e depois inspecionam o **repositório**,
que é o artefato canônico (CHAOS §3.1). Nenhum teste importa módulo da
implementação nem lê estado interno — trocar a linguagem ou a arquitetura interna
não deve quebrar um único AT. Se quebrar, ou o teste está olhando para o lugar
errado, ou a mudança violou um contrato.

**Identidades.** `harness.py` define `HUMAN`, `WORKER`, `CLOUD` e `AGENT` como
identidades Git distintas, porque CHAOS §17.1 exige credenciais separadas por
executor e o validador cruza identidade × trailer. Vários AT (19, 17, 15) só têm
sentido com essa separação.

**Dois executores.** A fila do ORDER (§11) e a política de merge do CHAOS (§17.3)
só são observáveis com dois clones sobre o mesmo remoto. A fixture `clone` fornece
o segundo; `repo_pair` fornece dois repositórios de classes de privacidade
distintas, necessários para §28.2.

## Arquivos

```
harness.py     invocador de CLI, identidades, leitura de repositório
conftest.py    fixtures: repo, clone, repo_pair, chaos, order
pytest.ini     marcadores e defaults
tests/         os AT + test_contract_consistency.py (verifica as specs)
FINDINGS.md       os AT do CHAOS que não eram escrevíveis, e por quê
FINDINGS-ORDER.md os achados do ORDER — o maior deles é a CLI, não os AT
```

## O que esta suíte não cobre

Comportamento de modelo. Resistir a instrução embutida, escolher bem a quem
delegar, não inventar evidência — nada disso é AT, e a separação está em CHAOS
§30.1. Esses comportamentos são medidos por eval, em taxa, fora da DoD. Todo
controle de que a segurança depende existe em código — `guard`, validador,
CODEOWNERS, classes de risco — justamente para que a conformidade não dependa de
o modelo colaborar.
