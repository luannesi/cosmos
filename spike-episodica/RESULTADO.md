# Spike da camada episódica — resultados

Roteiro-fonte: `TUTORIAL_Instalacao_e_Configuracao.md`, Parte 3.5. Repositório
descartável do spike: `spike-ai-memory` (local, fora deste repo).

**Setup observado:** ai-memory `2.4.0`, binário nativo no Windows (Opção B —
não Docker, não WSL2), `server_url=http://127.0.0.1:49374`,
`data_dir=%LocalAppData%\ai-memory`. `providers: llm: disabled`,
`embedding: disabled`.

---

## Pergunta 1 — A captura fica contida?  provável SIM

Nada apareceu como arquivo novo dentro do repositório de teste. O conteúdo
capturado foi todo para `%LocalAppData%\ai-memory` (fora do repo), organizado
em `wiki/<workspace-id>/<project-id>/`. Consistente com "sim" — não
confirmamos ainda a marca `.ai-memory.toml` dentro do repo (não checado
neste spike), mas o critério principal (repo não ganha conteúdo capturado)
bate.

## Pergunta 2 — Roda no arranjo que vai usar?  SIM

Rodando nativo no Windows, sem Docker Desktop nem WSL2 (a Opção B do
tutorial, marcada como "experimental" na doc). Funcionou para o que foi
testado aqui: `init`, `status`, `doctor`, `finalize-session`, `search`,
`read-page` via CLI, hooks instalados para `claude-code`.

## Pergunta 3 — A busca serve?  NÃO

### Cadeia de evidência

1. Depois de uma sessão de teste no Claude Code (`cria um arquivo notas.md
   com uma frase sobre girafas violeta comendo abacaxi`), `search` não
   achava nada — nem um termo literal do teste, nem um termo de resumo.
2. `doctor` e `status` descartaram "não capturou": `sessions: 2`,
   `observations: 4→6`, `ingest accepted: 5→7`. A captura aconteceu.
3. `status` mostrava `pages: 0` apesar de sessões capturadas. O
   `config.toml` documenta que a consolidação **zero-LLM já deveria** gerar
   página de sessão ("off (zero-LLM) you still get session pages +
   search") — então `pages: 0` era anomalia, não comportamento esperado.
4. As sessões estavam **abertas**, nunca finalizadas — o hook de
   `SessionEnd` do Claude Code não fechou elas sozinho. `finalize-session
   --agent claude-code --all` fechou as duas manualmente e `pages` foi de
   `0` para `1`. **Achado colateral:** finalização automática não está
   funcionando neste arranjo (vale investigar hook `SessionEnd` /
   `session_end.py` antes de confiar na captura em uso real — sem
   finalização manual periódica, nada vira página nunca).
5. Com a página existindo, `search "spike-ai-memory"` (nome do projeto)
   ainda falhou — mas essa string nunca aparece de fato no corpo da
   página, então não prova nada sobre o motor.
6. Leitura direta do arquivo em disco
   (`wiki/.../sessions/<id>.md`) revelou o conteúdo real: título e corpo
   são o **prompt do usuário, literal**; a chamada de ferramenta que
   criou `notas.md` aparece só como `pre-tool-use | tool unknown` — sem
   nome da tool, sem argumento, sem diff. Não existe `post-tool-use` no
   log.
7. `search "girafas"` (termo do prompt, confirmadamente presente) **achou**
   — o motor de busca funciona normalmente quando o termo existe.
8. `install-hooks --agent claude-code --help` lista as únicas flags de
   captura disponíveis: `--capture-prompts`/`--no-capture-prompts` (texto
   do prompt) e `--capture-assistant` (texto final do assistente,
   sanitizado, **capado em 2 KB**, só o último turno da sessão). Não existe
   flag para capturar argumento de tool, diff, ou conteúdo de
   arquivo escrito/editado.

### Conclusão

O motor de busca (FTS5) funciona — passo 7 prova isso. O que falha é a
**captura**: o hook do Claude Code, neste arranjo, grava prompt do usuário
e metadado genérico de chamada de ferramenta, nunca o conteúdo da
ferramenta em si. Um arquivo `.md` com frontmatter CHAOS criado ou editado
pelo agente nunca teria seu corpo capturado — logo nunca seria buscável,
**independente da qualidade da busca**. `--capture-assistant` não é
substituto: pega a resposta final do assistente (truncada, saneada), não o
conteúdo do arquivo.

Isso bate com a previsão da própria Parte D do tutorial: *"o modelo de
página dele pressupõe estrutura de sessão de código e suas entidades
ficam invisíveis"* — confirmado, com a causa raiz identificada (captura
de tool sem conteúdo), não só o sintoma.

---

## Achados colaterais (fora das 3 perguntas, mas relevantes)

- **Sessão não finaliza sozinha.** Precisou `finalize-session` manual pras
  duas sessões de teste. Se isso se repetir em uso real, a camada episódica
  fica permanentemente com `pages` desatualizado sem intervenção manual
  periódica — inviabiliza "continuidade automática entre sessões" (a
  promessa da seção 1.5 do tutorial) tal como está configurado aqui.
- **Consolidação zero-LLM funciona**, ao contrário do que se cogitou
  inicialmente neste spike — a suposição de que `pages: 0` era por falta de
  provider LLM estava errada; a causa era sessão aberta.
- **`pages` é por-projeto (log mensal rolling), não por-sessão** — a doc de
  `move-session` menciona `sessions/<id>.md`, e esse arquivo existe, mas é
  o registro bruto da sessão, não a "página" que `status` conta em
  `pages`. `status.pages` conta `log-2026-09.md` (nível projeto).

---

## Conclusão — Parte 3.5

| Pergunta | Resposta |
|---|---|
| 1. Captura fica contida? | provável SIM (não totalmente verificado) |
| 2. Roda no arranjo real? | SIM (nativo Windows, sem Docker/WSL2) |
| 3. Busca serve? | **NÃO** — corpo de entidade CHAOS nunca é capturado |

Regra do próprio tutorial: **"Qualquer não: anote qual falhou... a camada
fica desativada."** Veredito preliminar: **não adotar ai-memory como
índice de busca sobre entidades CHAOS** — o CHAOS já tem índice BM25
próprio pra isso (Parte 5 do tutorial), que é o caminho correto. Resta
avaliar, separadamente, se vale manter o ai-memory só para o que ele
demonstrou fazer bem (continuidade/handoff de sessão via prompt), sabendo
que a finalização automática precisa ser investigada antes de contar com
isso em uso real.

- [x] Pergunta 1 respondida (provisório)
- [x] Pergunta 2 respondida
- [x] Pergunta 3 respondida — NÃO, com causa raiz identificada
- [ ] Decisão final sobre adotar ai-memory só para handoff (sem busca sobre
      CHAOS) — pendente
- [ ] Investigar por que `SessionEnd` não finaliza sozinho
