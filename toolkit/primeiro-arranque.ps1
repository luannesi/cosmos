<#
    primeiro-arranque.ps1 — assistente do pacote portátil (Implementação §18.5)

    Chamado por INICIAR.cmd. Prepara o ambiente (bootstrap.ps1) e pergunta o que
    fazer: conectar a um repositório existente, criar um novo, ou parar por aqui.

    LIMITE DELIBERADO (opções 1, 2 e 4): por padrão este assistente não age fora
    da pasta do pacote e do repositório que você indicar. Não instala o Claude
    Code, não registra o worker no agendador e não escreve credencial nenhuma —
    imprime os comandos no fim para você executar. A promessa "nada foi
    instalado fora desta pasta" é verificável, e um assistente que a quebrasse
    por conveniência tornaria o pacote impossível de auditar.

    A opção 3 é a exceção, deliberada e explícita: quem escolhe "automatizar
    tudo" está pedindo pra sair desse limite — delega a bootstrap_cosmos.py
    (Partes 1 a 6), que roda o Onboarding, registra as chaves, empurra pro
    remoto e registra o worker. Continua nunca guardando frase-secreta nem
    credencial: essas continuam indo direto pro prompt do terminal.
#>
[CmdletBinding()]
param([switch] $NaoInterativo)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot

function Titulo ($m) { Write-Host ""; Write-Host $m -ForegroundColor Cyan }
function Say    ($m) { Write-Host "  $m" }
function Ok     ($m) { Write-Host "  [ok]   $m"    -ForegroundColor Green }
function Warn   ($m) { Write-Host "  [aviso] $m"   -ForegroundColor Yellow }
function Erro   ($m) { Write-Host "  [erro] $m"    -ForegroundColor Red }

function Perguntar ($texto, $padrao) {
    if ($padrao) { $r = Read-Host "  $texto [$padrao]" ; if (-not $r) { return $padrao } ; return $r }
    return (Read-Host "  $texto")
}

# ------------------------------------------------------------------ funções
function DestinoValido ($caminho) {
    if (Test-Path $caminho) {
        $itens = @(Get-ChildItem -Force $caminho -ErrorAction SilentlyContinue)
        if ($itens.Count -gt 0) {
            Erro "$caminho já existe e não está vazia."
            Erro "Escolha outro destino — este assistente nunca escreve por cima de pasta com conteúdo."
            return $false
        }
    }
    return $true
}

function Concluir ($repo, [switch] $Automatizado) {
    Set-Content -Path $estado -Value $repo -Encoding UTF8

    if (-not $Automatizado) {
        Titulo "Verificação"
        $chaos = Join-Path $repo 'bin\chaos'
        if (Test-Path $chaos) {
            Push-Location $repo
            & python $chaos health
            $rc = $LASTEXITCODE
            Pop-Location
            if ($rc -ne 0) {
                Warn "o toolchain do pacote e o vendorizado no repositório divergem (CHAOS §21.1)."
                Warn "Alinhe com:  chaos tooling update <tag>"
                Warn "É escrita em caminho protegido, logo é humana — de propósito."
            }
        } else {
            Say "o repositório ainda não tem tools/chaos (Fase 0 não construída)."
        }
    }

    if ($Automatizado) {
        Titulo "Falta um passo, e é seu"
        Write-Host ""
        Write-Host "  Claude Code — uma linha, sem administrador:" -ForegroundColor White
        Write-Host "     irm https://claude.ai/install.ps1 | iex"
        Write-Host ""
        Say "Onboarding, chaves, push e worker no logon já foram feitos por"
        Say "bootstrap_cosmos.py — reveja o que ele fez acima."
    } else {
        Titulo "Faltam dois passos, e os dois são seus"
        Write-Host ""
        Write-Host "  1) Claude Code — uma linha, sem administrador:" -ForegroundColor White
        Write-Host "     irm https://claude.ai/install.ps1 | iex"
        Write-Host ""
        Write-Host "  2) Worker no logon — Agendador de Tarefas:" -ForegroundColor White
        Write-Host "     veja a Parte 6 do tutorial (dois minutos, sem administrador)"
        Write-Host ""
        Say "Este assistente não executa nenhum dos dois de propósito: os dois mexem"
        Say "fora desta pasta, e o pacote promete não fazer isso."
    }
    Write-Host ""
    Ok "repositório pronto em $repo"
}

# ------------------------------------------------------------------ ambiente
Titulo "CHAOS/ORDER — primeiro arranque"
Say "pacote: $Root"

try {
    . (Join-Path $Root 'bootstrap.ps1')
} catch {
    Erro "o ambiente não pôde ser preparado: $($_.Exception.Message)"
    Erro "o pacote pode estar incompleto ou corrompido no download."
    exit 1
}

# ------------------------------------------------- estado: já há repositório?
$estado = Join-Path $Root 'ULTIMO-REPO.txt'
$repoAnterior = if (Test-Path $estado) { (Get-Content $estado -Raw).Trim() } else { $null }
if ($repoAnterior -and (Test-Path $repoAnterior)) {
    Titulo "Este pacote já foi usado"
    Say "repositório: $repoAnterior"
    $r = Perguntar "Usar esse mesmo repositório? (s/n)" "s"
    if ($r -match '^[sSyY]') { Concluir $repoAnterior; exit 0 }
}

# ------------------------------------------------------------------ o menu
Titulo "O que você quer fazer?"
Write-Host ""
Write-Host "  [1] Conectar a um repositório Git que já tem o meu conteúdo"
Write-Host "      (é o caso da segunda máquina em diante)"
Write-Host ""
Write-Host "  [2] Criar um repositório novo do zero"
Write-Host "      (abre o Onboarding pra você rodar; chaves e worker ficam por sua conta)"
Write-Host ""
Write-Host "  [3] Criar um repositório novo e automatizar tudo"
Write-Host "      (Onboarding, chaves, push e worker no logon — Partes 1 a 6; sai do"
Write-Host "       limite deliberado acima, de propósito, só quando você escolhe isto)"
Write-Host ""
Write-Host "  [4] Só preparar o ambiente, sem repositório"
Write-Host ""

$escolha = Perguntar "Opção (1/2/3/4)" "1"

# ------------------------------------------------------------------ opção 1
if ($escolha -eq '1') {
    Titulo "Conectar a um repositório existente"
    Say "A autenticação é a do seu Git (SSH ou gerenciador de credenciais)."
    Say "Este assistente não pede, não guarda e não grava token nenhum."
    Write-Host ""

    $url = Perguntar "URL do repositório (ex.: git@github.com:voce/chaos-personal.git)"
    if (-not $url) { Erro "sem URL não há o que clonar."; exit 1 }

    $nome = ($url -split '[/\\]')[-1] -replace '\.git$',''
    $destino = Perguntar "Onde clonar?" "D:\$nome"
    if (-not (DestinoValido $destino)) { exit 1 }

    Write-Host ""
    Say "clonando…"
    & git clone $url $destino
    if ($LASTEXITCODE -ne 0) {
        Erro "o clone falhou. Causas comuns: URL errada, sem acesso à rede,"
        Erro "ou a chave/credencial desta máquina ainda não tem permissão no repositório."
        exit 1
    }
    Ok "clonado"
    Concluir $destino
    exit 0
}

# ------------------------------------------------------------------ opção 2
if ($escolha -eq '2') {
    Titulo "Criar um repositório novo"

    $seed = Join-Path $Root 'tools-seed\bin\chaos'
    if (-not (Test-Path $seed)) {
        Erro "este pacote não traz tools-seed/ — não dá para semear um repositório novo."
        Erro "Use a opção 1 com um repositório existente, ou monte o pacote com a semente."
        exit 1
    }

    Say "O repositório não é inventado aqui. Este assistente cria a pasta, roda"
    Say "'chaos init' e entrega para o Onboarding (Implementação §3), que é quem"
    Say "faz as perguntas que importam: classes de privacidade, áreas, identidades,"
    Say "modelos e cotas. Nenhuma delas tem resposta silenciosa."
    Write-Host ""

    $destino = Perguntar "Onde criar?" "D:\chaos-personal"
    if (-not (DestinoValido $destino)) { exit 1 }

    New-Item -ItemType Directory -Force -Path $destino | Out-Null
    Push-Location $destino
    & git init -q -b main
    & python $seed init
    $rc = $LASTEXITCODE
    Pop-Location

    if ($rc -ne 0) { Erro "'chaos init' falhou — nada foi deixado pela metade em $destino"; exit 1 }
    Ok "repositório semeado em $destino"

    Write-Host ""
    Say "Agora rode o Onboarding, que é a etapa que define o seu sistema:"
    Write-Host "     cd $destino"
    Write-Host "     python bin\chaos onboarding run"
    Concluir $destino
    exit 0
}

# ------------------------------------------------------------------ opção 3
if ($escolha -eq '3') {
    Titulo "Criar um repositório novo com tudo automatizado"
    Say "Isso roda bootstrap_cosmos.py (Partes 1 a 6): o Onboarding é perguntado"
    Say "aqui mesmo — cada pergunta sem resposta anterior é feita a você, nada é"
    Say "assumido — as chaves são registradas, o repositório vai pro remoto e o"
    Say "worker é registrado no Agendador de Tarefas."
    Say "Frase-secreta de chave nunca passa por este script: vai direto pro prompt"
    Say "do ssh-keygen/git commit, no terminal."
    Write-Host ""

    $motor = Join-Path $Root 'bootstrap_cosmos.py'
    if (-not (Test-Path $motor)) {
        Erro "bootstrap_cosmos.py não encontrado em $Root — este pacote não tem o motor automatizado."
        exit 1
    }

    $destino = Perguntar "Onde criar?" "D:\chaos-personal"
    if (-not (DestinoValido $destino)) { exit 1 }

    & python $motor --repo-dir $destino --cosmos-dir $Root
    $rc = $LASTEXITCODE
    if ($rc -ne 0) {
        Erro "o instalador parou (código $rc) — rode este menu de novo e escolha [3]:"
        Erro "ele retoma exatamente de onde parou, não refaz o que já foi feito."
        exit $rc
    }
    Concluir $destino -Automatizado
    exit 0
}

# ------------------------------------------------------------------ opção 4
Titulo "Ambiente preparado"
Say "As ferramentas estão no PATH desta janela. Quando quiser um repositório:"
Write-Host ""
Write-Host "     .\INICIAR.cmd        (e escolha 1, 2 ou 3)"
Write-Host ""
Ok "nada foi instalado fora desta pasta."
