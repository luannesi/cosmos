<#
    bootstrap.ps1 — pacote portátil do CHAOS/ORDER (Implementação §18)

    Monta PATH e variáveis de ambiente PARA ESTA SESSÃO e verifica a integridade
    do pacote. Não instala nada fora da própria pasta, não escreve no registro,
    não exige administrador e não altera variáveis de usuário — se você fechar o
    terminal, nada fica para trás.

    Uso:
        .\bootstrap.ps1                 # prepara a sessão
        .\bootstrap.ps1 -Verify         # só verifica e sai
        .\bootstrap.ps1 -Repo D:\chaos-personal   # já entra no repositório

    O que ele deliberadamente NÃO faz: atualizar o pacote, baixar ferramenta que
    falte, ou "consertar" divergência de versão. Alinhar toolchain é
    `chaos tooling update <tag>`, que escreve em protected path e é humano.
#>
[CmdletBinding()]
param(
    [string] $Repo,
    [switch] $Verify,
    [switch] $SkipHashes
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot

function Say  ($m) { Write-Host "  $m" }
function Ok   ($m) { Write-Host "  [ok]   $m"   -ForegroundColor Green }
function Warn ($m) { Write-Host "  [aviso] $m"  -ForegroundColor Yellow }
function Die  ($m) { Write-Host "  [erro] $m"   -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "CHAOS/ORDER — pacote portátil" -ForegroundColor Cyan
Write-Host "raiz: $Root"
Write-Host ""

# ---------------------------------------------------------------- manifesto
$manifestPath = Join-Path $Root 'TOOLKIT.yaml'
if (-not (Test-Path $manifestPath)) {
    Die "TOOLKIT.yaml não encontrado. Este diretório não é um pacote válido."
}

# Leitura mínima de YAML plano — o pacote não pode depender de módulo externo
# justamente porque ele é quem prepara o ambiente que teria esse módulo.
$manifest = @{}
foreach ($line in Get-Content $manifestPath -Encoding UTF8) {
    if ($line -match '^\s*#' -or $line -notmatch ':') { continue }
    $k, $v = $line -split ':', 2
    $manifest[$k.Trim()] = $v.Trim().Trim('"')
}
$tag = $manifest['tag']
if (-not $tag) { Die "TOOLKIT.yaml não declara `tag`." }
Ok "pacote tag $tag"

# ------------------------------------------------- marca de origem (Windows)
# Um zip baixado carrega a Mark of the Web; binários extraídos dele falham de
# formas confusas (às vezes silenciosamente). Desbloquear é barato; descobrir
# depois, não.
$blocked = Get-ChildItem -Path $Root -Recurse -File -ErrorAction SilentlyContinue |
           Where-Object { Get-Item $_.FullName -Stream Zone.Identifier -ErrorAction SilentlyContinue }
if ($blocked) {
    Warn "$($blocked.Count) arquivo(s) ainda marcados como baixados da internet — desbloqueando"
    $blocked | Unblock-File
    Ok "desbloqueados"
}

# ---------------------------------------------------------------- variáveis
# Tudo para dentro do pacote: nada escrito em %USERPROFILE% nem em C:.
$env:UV_INSTALL_DIR        = Join-Path $Root 'uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Root 'python'
$env:UV_CACHE_DIR          = Join-Path $Root 'cache\uv'
$env:UV_TOOL_DIR           = Join-Path $Root 'tools\uv'
$env:UV_TOOL_BIN_DIR       = Join-Path $Root 'tools\bin'
$env:UV_NO_MODIFY_PATH     = '1'
$env:OLLAMA_MODELS         = Join-Path $Root 'models'
$env:GIT_CONFIG_NOSYSTEM   = '1'          # ignora config de máquina: o pacote é autocontido

$paths = @(
    (Join-Path $Root 'git\cmd'),
    (Join-Path $Root 'git\usr\bin'),
    (Join-Path $Root 'uv'),
    (Join-Path $Root 'venv\Scripts'),
    (Join-Path $Root 'episodic'),
    (Join-Path $Root 'ollama'),
    (Join-Path $Root 'tools\bin')
) | Where-Object { Test-Path $_ }

$env:PATH = ($paths -join ';') + ';' + $env:PATH
Ok "PATH e variáveis montados para esta sessão"

# ---------------------------------------------------------------- presença
$obrigatorios = @{
    'git'    = 'git\cmd\git.exe'
    'uv'     = 'uv\uv.exe'
    'python' = 'venv\Scripts\python.exe'
}
$opcionais = @{
    'camada episódica' = 'episodic\ai-memory.exe'
    'ollama'           = 'ollama\ollama.exe'
}

foreach ($nome in $obrigatorios.Keys) {
    $p = Join-Path $Root $obrigatorios[$nome]
    if (Test-Path $p) { Ok "$nome presente" } else { Die "$nome ausente em $p — pacote incompleto" }
}
foreach ($nome in $opcionais.Keys) {
    $p = Join-Path $Root $opcionais[$nome]
    if (Test-Path $p) { Ok "$nome presente" }
    else { Say "[--]   $nome ausente (opcional — o sistema funciona sem)" }
}

# ---------------------------------------------------------------- integridade
if (-not $SkipHashes) {
    $divergentes = @()
    foreach ($k in $manifest.Keys) {
        if ($k -notlike 'sha256_*') { continue }
        $rel = $k.Substring(7).Replace('__', '\')
        $alvo = Join-Path $Root $rel
        if (-not (Test-Path $alvo)) { continue }
        $h = (Get-FileHash $alvo -Algorithm SHA256).Hash.ToLower()
        if ($h -ne $manifest[$k].ToLower()) { $divergentes += $rel }
    }
    if ($divergentes) {
        Warn "hash divergente em: $($divergentes -join ', ')"
        Warn "o download pode estar corrompido — baixe o pacote de novo antes de usar"
    } else {
        Ok "hashes conferem"
    }
}

# ---------------------------------------------------------------- versões
Write-Host ""
Say "git      $((& git --version) 2>&1)"
Say "uv       $((& uv --version) 2>&1)"
Say "python   $((& python --version) 2>&1)"
Write-Host ""

if ($Verify) { Ok "verificação concluída"; exit 0 }

# ---------------------------------------------------------------- repositório
if ($Repo) {
    if (-not (Test-Path $Repo)) { Die "repositório não encontrado em $Repo" }
    Set-Location $Repo
    Ok "repositório: $Repo"

    $chaos = Join-Path $Repo 'bin\chaos'
    if (Test-Path $chaos) {
        Write-Host ""
        Say "chaos health:"
        & python $chaos health
        if ($LASTEXITCODE -ne 0) {
            Warn "toolchain divergente do vendorizado (CHAOS §21.1)."
            Warn "Alinhe com: chaos tooling update <tag>   — é escrita em protected path, logo humana."
        }
    } else {
        Say "o repositório ainda não tem tools/chaos — rode 'chaos onboarding run' depois da Fase 0"
    }
} else {
    Write-Host "Próximo passo:" -ForegroundColor Cyan
    Write-Host "  git clone <url-do-seu-repo> D:\chaos-<classe>"
    Write-Host "  .\bootstrap.ps1 -Repo D:\chaos-<classe>"
}

Write-Host ""
Ok "sessão pronta. Nada foi instalado fora desta pasta."
Write-Host ""
