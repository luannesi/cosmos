# Runbook — primeira execução do COSMOS numa máquina

Passo a passo para sair de **nada** e chegar a um repositório de conhecimento
governado, funcionando, na sua máquina.

Escrito para **Windows**, que é a plataforma-alvo; onde Linux e macOS diferem,
está indicado. Tempo realista: **duas a três horas**, quase todo ele nas 28
perguntas do Onboarding, que são as que definem o seu sistema.

> **Leia isto antes de começar.** Esta é a primeira execução real do sistema.
> As especificações estão fechadas e a implementação passa 134 testes de
> aceitação, mas ninguém percorreu este caminho numa máquina de verdade ainda.
> Você vai encontrar coisas. Quando encontrar, anote — o `order-tooling/ACHADOS.md`
> é onde esse tipo de descoberta vive, e é o documento que mais ensina sobre o
> projeto. Um tutorial que promete tranquilidade que não tem é pior que um que
> avisa.

**Ao final você terá:** um repositório Git privado com o layout CHAOS, as
políticas do ORDER, a sua equipe de agentes declarada, chaves de assinatura
estabelecendo quem é humano, e os comandos `chaos` e `order` operando contra
tudo isso.

**Você ainda não terá:** chamadas reais a modelos (falta credencial de
provedor), camada episódica (componente opcional de terceiro), e o worker
registrado no logon. Nada disso impede o uso.

---

## Parte 0 — Decisões que você toma antes de digitar

Três, e vale pensá-las agora para não parar no meio.

**A classe de privacidade do primeiro repositório.** O isolamento por classe é
a única fronteira de confidencialidade do sistema — conteúdo de uma classe
nunca entra em contexto de outra, porque são repositórios distintos. Comece com
uma só; `pessoal` é a escolha usual. Outras classes vêm na Fase 5.

**O seu identificador.** Algo como `human:luan`. Aparece em todo commit e em
todo evento de auditoria. Não precisa ser bonito, precisa ser estável.

**Onde o repositório vai morar.** Um caminho curto, fora de pasta sincronizada.
`D:\chaos-pessoal` serve. **Não use OneDrive, Google Drive ou Dropbox**: dois
escritores sobre `.git/` sem merge semântico corrompem o repositório, e o
sintoma aparece dias depois, como histórico impossível.

---

## Parte 1 — Base

### 1.1 Python

```powershell
py --version
```

Precisa responder **3.10 ou mais novo**. Se não responder nada, instale de
python.org marcando "Add python.exe to PATH".

### 1.2 Git

```powershell
git --version
```

**2.34 ou mais novo** — é a partir dessa versão que o Git assina com chave SSH,
e a assinatura é a raiz de confiança de todo o resto. No Windows, instale o Git
for Windows e escolha **"Checkout as-is, commit as-is"** na tela de finais de
linha (é a opção do meio, não a padrão): a normalização quem faz é o
`.gitattributes` do repositório, e deixar o Git converter por conta quebraria
três garantias em silêncio.

### 1.3 Identidade Git

```powershell
git config --global user.name
git config --global user.email
```

As duas têm que responder. Se vierem vazias, preencha — senão o `chaos init`
falha no commit com uma mensagem que não parece ter relação com identidade.

### 1.4 Autenticação Git — o passo que parece burocrático e não é

Numa instalação limpa do Git for Windows, **não há gerenciador de credenciais
configurado**, e o GitHub removeu autenticação por senha. O primeiro `push`
falha com `Invalid username or token`, que não sugere a causa.

```powershell
git config --global credential.helper
```

Vazio? Ative o que já veio junto com o Git:

```powershell
git config --global credential.helper manager
```

O comando de escrita não responde nada — silêncio ali é sucesso. Confirme
rodando o de leitura de novo: deve dizer `manager`.

**Verifique de verdade**, não confie na configuração:

```powershell
git clone https://github.com/luannesi/cosmos.git D:\cosmos
```

Se abrir uma janela de login do GitHub, é o gerenciador funcionando. Se
concluir sem pedir nada, melhor ainda — você já estava autenticado.

> No Linux e no macOS: configure um helper (`gh auth login` + `gh auth setup-git`
> é o mais simples) ou use SSH. O teste é o mesmo: um clone que conclui.

### 1.5 Dependências Python

```powershell
py -m pip install pyyaml jsonschema pytest
```

### 1.6 Claude Code (opcional agora, necessário para os agentes)

Exige plano Pro, Max, Team ou Enterprise. Pode ficar para depois da Parte 4 —
nada até lá depende dele.

---

## Parte 2 — Chaves de assinatura

É aqui que se estabelece quem conta como humano no seu sistema. Leia as duas
linhas de justificativa: elas explicam por que a fricção existe.

### 2.1 A chave humana

```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\chaos-humano" -C "seu-email@exemplo.com"
```

Ele pede uma frase-secreta duas vezes. **Digite uma de verdade e guarde-a.**

Sem frase-secreta, qualquer processo rodando na sua máquina assina como você —
inclusive um agente. A aprovação de ações irreversíveis (classe A4) existe para
exigir que uma pessoa autorize conscientemente, e é o ato de digitar a frase
que constitui essa autorização. A fricção **é** o controle.

### 2.2 A chave do worker

```powershell
ssh-keygen -t ed25519 -N '""' -f "$env:USERPROFILE\.ssh\chaos-worker" -C "worker@chaos.local"
```

Esta sem frase, porque o worker roda sem você por perto. Ela prova
**procedência** — que a ação veio desta máquina e não da nuvem — e nunca
**consentimento**. São principais distintos de propósito: um worker que
assinasse em seu nome seria um oráculo de assinatura, e qualquer coisa capaz de
enfileirar trabalho para ele obteria a marca.

### 2.3 A segunda chave humana

Gere **outra** chave humana, em outra máquina ou num pendrive guardado, e não
perca o arquivo `.pub`.

Se a máquina morrer com a sua única chave humana, nada do conteúdo se perde —
são arquivos Markdown no Git. Mas **nenhuma aprovação A4 volta a ser possível**,
porque registrar uma chave nova exige assinatura da chave que se perdeu. É a
diferença entre reconfigurar e reconstruir do zero.

### 2.4 Ativar a assinatura

```powershell
git config --global gpg.format ssh
git config --global user.signingkey "$env:USERPROFILE\.ssh\chaos-humano.pub"
git config --global commit.gpgsign true
```

---

## Parte 3 — O toolchain

Se você ainda não clonou no passo 1.4:

```powershell
git clone https://github.com/luannesi/cosmos.git D:\cosmos
```

### 3.1 Portão: a suíte tem que passar

```powershell
cd D:\cosmos
py -m pytest at-suite -q --chaos-bin=order-tooling\bin\chaos --order-bin=order-tooling\bin\order
```

**Esperado:** 134 testes, com 4 pulados por falta do componente episódico
opcional.

**Se falhar, pare aqui.** Uma falha neste ponto é da implementação na sua
plataforma, não da sua instalação — e seguir adiante construiria o seu
repositório sobre código que não faz o que promete. Anote a saída e investigue
antes de continuar; é exatamente para isso que a suíte existe.

Esta é também a primeira execução do sistema em Windows nativo. Se aparecer
algo relacionado a caminho, finais de linha ou `ssh-keygen`, é achado novo.

---

## Parte 4 — O seu repositório de conhecimento

### 4.1 Crie o repositório remoto

No GitHub: **privado**, **vazio** — sem README, sem `.gitignore`, sem licença.
Qualquer arquivo inicial cria um commit que não é seu e atrapalha o passo 4.4.

Com o GitHub CLI: `gh repo create chaos-pessoal --private`

### 4.2 Inicialize

```powershell
mkdir D:\chaos-pessoal
cd D:\chaos-pessoal
git init -b main
py D:\cosmos\order-tooling\bin\chaos init --privacy-class pessoal --owner human:luan
```

Isso cria o layout inteiro, **vendoriza as ferramentas dentro do repositório**,
escreve o `AGENTS.md`, os schemas, as políticas, o `.gitattributes`, o
`allowed_signers` vazio com o formato documentado, e configura o Git local para
verificar assinatura.

A partir daqui as ferramentas moram no seu repositório: use `.\bin\chaos.cmd` e
`.\bin\order.cmd` de dentro dele. **O clone do `cosmos` deixa de ser
necessário** — ele volta a importar só quando você for atualizar as ferramentas.

Confira:

```powershell
.\bin\chaos.cmd validate
.\bin\chaos.cmd health
```

`validate` limpo e `health` respondendo `ok`.

### 4.3 Onboarding

```powershell
.\bin\chaos.cmd onboarding run
```

28 perguntas, **nenhuma com resposta padrão silenciosa**. No fim, um relatório
para você confirmar.

Três avisos sobre esta parte:

Várias respostas viram arquivo de política, e política é caminho protegido.
Corrigir depois é uma aprovação A4, não uma edição. **Se não souber uma
resposta, pare e descubra** em vez de chutar.

Quando perguntar os *principais* de assinatura, use o e-mail que você pôs no
`-C` de cada chave na Parte 2. Eles precisam bater, porque é esse mapeamento
que diz a qual papel — humano ou worker — cada chave pertence.

Este passo tem de vir **antes** de registrar as chaves. O `init` preenche os
e-mails com valores de exemplo; o Onboarding é quem escreve os seus reais. Se
você registrar antes, o principal não resolve para o seu identificador humano e
a assinatura não conta como humana — e isso só apareceria na primeira aprovação
A4 negada sem motivo aparente.

### 4.4 Registrar as chaves e fazer o commit que funda a confiança

```powershell
$h = .\bin\chaos.cmd key register human:luan "$env:USERPROFILE\.ssh\chaos-humano.pub" --principal seu-email@exemplo.com | ConvertFrom-Json
Add-Content -Path metadata\registries\allowed_signers -Value $h.linha -Encoding utf8

$w = .\bin\chaos.cmd key register executor:local_worker "$env:USERPROFILE\.ssh\chaos-worker.pub" --principal worker@chaos.local | ConvertFrom-Json
Add-Content -Path metadata\registries\allowed_signers -Value $w.linha -Encoding utf8
```

Acrescente também a linha da **segunda chave humana** (item 2.3), com o mesmo
comando apontando para o outro `.pub`.

```powershell
git add metadata\registries\allowed_signers
git commit -m "registra as chaves de assinatura"
```

Vai pedir a sua frase-secreta. **É o commit mais importante do repositório:**
define quem conta como humano, e é o único em toda a vida dele que não precisa
de assinatura prévia — porque antes dele não havia chave. Daí em diante a regra
passa a valer sobre o próprio arquivo.

O `key register` monta a linha e para aí, de propósito. Registrar chave é
conceder autoridade; um comando que fizesse isso como efeito colateral seria a
porta exata que o desenho existe para trancar.

```powershell
.\bin\chaos.cmd key verify
```

Tem que responder `"humano": true`.

### 4.5 Conecte e empurre

```powershell
git remote add origin https://github.com/SEU-USUARIO/chaos-pessoal.git
git push -u origin main
```

---

## Parte 5 — Verificação

```powershell
.\bin\chaos.cmd validate          # sem erros
.\bin\chaos.cmd health            # ok
.\bin\chaos.cmd key verify        # humano: true
.\bin\order.cmd status            # runs, leases, aprovações pendentes
.\bin\order.cmd agent list        # a equipe que o Onboarding declarou
```

Um teste de ponta a ponta, que exercita entidade, ledger e commit governado:

```powershell
.\bin\chaos.cmd task create --title "Primeira tarefa do COSMOS"
.\bin\chaos.cmd status
.\bin\chaos.cmd search "primeira"
```

A tarefa aparece no `status`, a busca a encontra, e existe um evento
correspondente no `audit/events.jsonl`. Se as três coisas valem, o sistema está
de pé.

### O que a suíte prova e o que ela não prova

A suíte da Parte 3 prova que **a implementação** faz o que as especificações
exigem — ela trabalha em repositórios temporários que cria e descarta. Os
comandos desta parte provam que **o seu repositório** está íntegro. São
verificações diferentes e as duas importam: a primeira valida o código, a
segunda valida a sua instalação.

---

## Parte 6 — Daqui em diante

**Segunda máquina:** não repita nada disto à mão. `toolkit\montar-pacote.ps1`
monta um pacote portátil com ferramentas, Python e ambiente virtual; a outra
máquina descompacta e conecta ao Git. O estado viaja pelo Git, as ferramentas
pelo pacote. Cada máquina tem identidade de executor e chave de worker próprias.

**Modelos locais e chamadas reais:** Fase 6 do binding. Precisa de credencial de
provedor, que o Onboarding coleta, e de hardware compatível.

**Camada episódica:** opcional e dispensável por construção — há um critério de
aceitação (CHAOS AT-34) que prova que, sem ela, nenhum outro resultado muda.
O spike que decide se vale adotá-la está na Parte 3.5 do tutorial longo.

**Worker no logon:** Agendador de Tarefas no Windows, `systemd --user` no Linux,
`LaunchAgent` no macOS. Instruções na Parte 6 do
`TUTORIAL_Instalacao_e_Configuracao.md`.

---

## Problemas comuns

**`Invalid username or token` no clone ou push.** Falta o `credential.helper`
(item 1.4). É o tropeço mais provável numa máquina nova.

**O commit assinado não é reconhecido como humano.** Quase sempre o principal
no `allowed_signers` não bate com o `signing_principal` do
`metadata/registries/executors.yaml`. Confira com `.\bin\chaos.cmd key list`.

**`git log --show-signature` diz que não há assinatura num commit assinado.**
Falta o `gpg.ssh.allowedSignersFile` na configuração local. O `chaos init` o
define; se você clonou o repositório noutra máquina, rode
`.\bin\chaos.cmd bootstrap sync`.

**`%G?` devolve `U` em vez de `G`.** As opções no `allowed_signers` foram
separadas por espaço. O OpenSSH exige **vírgula** num campo único; com espaço
ele rejeita a linha inteira e a assinatura legítima deixa de verificar, sem
mensagem que aponte a causa. O `key register` monta a linha certa.

**`bin\chaos` não executa.** Use `.\bin\chaos.cmd` no Windows. O arquivo sem
extensão é um script Python com shebang, e o Windows não honra shebang.

**O validador reclama de `CRLF`.** Alguma ferramenta converteu finais de linha.
O `.gitattributes` do repositório cuida disso; se persistir, confirme a opção
"Checkout as-is, commit as-is" na instalação do Git (item 1.2).
