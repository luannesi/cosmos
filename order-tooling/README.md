# order-tooling — implementação de referência do CHAOS v2.5 / ORDER v2.5

Vendorizado em cada `chaos-<classe>` como `tools/` (Implementação §4.3).
A tag corresponde a `metadata/tooling.yaml.vendored_tag`; `chaos health` compara.

```
bin/chaos          CLI de CHAOS §21
bin/order          CLI de ORDER §38
bin/order-worker   worker local como processo (Impl. §8.1)
bin/episodic-ref   adaptador episódico de REFERÊNCIA (não é o ai-memory)
hooks/             os cinco hooks do Claude Code, vendorizados no repo por init
tools/chaos/       entidades, áreas, validador, ledger, índice, grafo, contexto,
                   onboarding, saúde
tools/order/       risco, guard, fila, aprovações, agentes, cotas, gatilhos,
                   workflows, gateway de modelos, notificações, worker
tests/             73 testes de unidade dos motores (rodam em 1 segundo)
```

## Estado

**124 de 124 testes de aceitação** e **73 de unidade** passam — CHAOS §30 (35 AT),
ORDER §44 (29 AT), 10 de consistência das specs, todas as parametrizações.

```bash
python -m pytest tests/ -q          # unidade, ~1s
```

```bash
cd at-suite
pytest --chaos-bin=../order-tooling/bin/chaos \
       --order-bin=../order-tooling/bin/order \
       --episodic-bin=../order-tooling/bin/episodic-ref
```

## O que NÃO está aqui

- **Chamada real de modelo.** O gateway está pronto e roteia; o que falta é o
  registry ter um provedor com `endpoint` e `api_key_env`, ou um runner local
  instalado. Isso vem do Onboarding (§3.4) — inventar a configuração do usuário
  seria pior que não chamar.
- **Integração real com o `ai-memory`.** Há o adaptador de referência, e o
  contrato que ele implementa é o que o componente real precisa satisfazer.
- **O registro do worker no logon** — Agendador de Tarefas, systemd ou LaunchAgent.
  É configuração de máquina, não arquivo; o procedimento está no tutorial.
- **Execução em Windows nativo.** Tudo rodou em Linux; a tabela de plataformas
  de Impl. §4.6 continua verificada por leitura, não por execução.
- O que depende do spike de identidade continua isolado; ver `ACHADOS.md` §8.

## Dependências

Python 3.10+ (verificado em 3.10; a suíte inteira passa), `PyYAML`, `jsonschema` (opcional: sem ele o validador cai num
verificador mínimo de tipos e obrigatórios, e diz que caiu).
