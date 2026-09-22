<#
    montar-pacote.ps1 — monta o pacote portátil (Implementação §18).

    Roda UMA vez, na máquina que já funciona, e produz o ZIP que as outras
    máquinas consomem. Não é o assistente de primeiro arranque
    (`primeiro-arranque.ps1`) — aquele roda no destino; este, na origem.

    O que ele NÃO faz, e é deliberado:
      - não baixa modelos do Ollama (gigabytes que o `pull` busca no destino);
      - não inclui credencial nem chave de assinatura — e verifica isso antes
        de compactar, recusando o pacote se encontrar qualquer uma (§18.3);
      - não instala nada fora da pasta do pacote.

    Uso:
        .\montar-pacote.ps1 -RepoOrigem D:\chaos-pessoal -Tag v0.1.0
#>
param(
    [Parameter(Mandatory = $true)][string]$RepoOrigem,
    [Parameter(Mandatory = $true)][string]$Tag,
    [string]$Destino = ".\pacote",
    [switch]$SemGit,
    [switch]$SemOllama
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path

function Passo($t) { Write-Host "`n== $t" -ForegroundColor Cyan }
function Aviso($t) { Write-Host "   ! $t" -ForegroundColor Yellow }
function Fatal($t) { Write-Host "`nABORTADO: $t" -ForegroundColor Red; exit 1 }

# --- 0. origem -------------------------------------------------------------
Passo "Conferindo o repositório de origem"
if (-not (Test-Path (Join-Path $RepoOrigem "tools\chaos\cli.py"))) {
    Fatal "`$RepoOrigem não parece um repositório CHAOS construído (falta tools\chaos\cli.py)."
}
$tagRepo = (Select-String -Path (Join-Path $RepoOrigem "metadata\tooling.yaml") `
            -Pattern 'vendored_tag:\s*"?([^"\s]+)"?').Matches.Groups[1].Value
if ($tagRepo -ne $Tag) {
    # Não é fatal, mas é exatamente o descasamento que `chaos health` vai
    # reportar como `drift` em toda máquina que receber este pacote.
    Aviso "tag pedida ($Tag) difere da vendorizada no repositório ($tagRepo)."
}

$pkg = Join-Path $raiz $Destino
if (Test-Path $pkg) { Fatal "`$Destino já existe: $pkg. Apague ou escolha outro." }
New-Item -ItemType Directory -Path $pkg | Out-Null

# --- 1. esqueleto e scripts ------------------------------------------------
Passo "Copiando scripts e esqueleto"
foreach ($f in @("INICIAR.cmd","iniciar.sh","LEIA-ME.txt","primeiro-arranque.ps1",
                 "bootstrap.ps1","bootstrap.sh","TOOLKIT.yaml","requirements.txt")) {
    Copy-Item (Join-Path $raiz $f) $pkg
}
foreach ($d in @("git","uv","python","venv","wheels","episodic","ollama","models")) {
    New-Item -ItemType Directory -Path (Join-Path $pkg $d) -Force | Out-Null
}

# --- 2. tools-seed ---------------------------------------------------------
Passo "Semeando tools-seed/ a partir do repositório"
$seed = Join-Path $pkg "tools-seed"
New-Item -ItemType Directory -Path $seed -Force | Out-Null
foreach ($d in @("tools","hooks","bin")) {
    Copy-Item (Join-Path $RepoOrigem $d) $seed -Recurse -Force
}
Get-ChildItem $seed -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force
# Bytecode obsoleto num pacote verificado por hash é ruído que muda o hash
# sem mudar o comportamento — e a primeira pergunta que gera é "mudou o quê?".

# --- 3. uv, Python, venv, wheels ------------------------------------------
Passo "Baixando o uv"
$uvZip = Join-Path $env:TEMP "uv.zip"
Invoke-WebRequest -Uri "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip" -OutFile $uvZip
Expand-Archive $uvZip -DestinationPath (Join-Path $pkg "uv") -Force
$uv = Join-Path $pkg "uv\uv.exe"
if (-not (Test-Path $uv)) { Fatal "uv.exe não apareceu em uv\ após a extração." }

Passo "Instalando o Python gerenciado dentro do pacote"
# `--managed-python` é obrigatório e não é preciosismo: sem ele, numa máquina
# de montagem que JÁ tenha Python 3.13, o uv usa o do sistema, a pasta python\
# fica vazia e o venv aponta para um interpretador que não existe no destino.
# O pacote sai aparentemente completo e quebra na outra máquina.
$env:UV_PYTHON_INSTALL_DIR = Join-Path $pkg "python"
& $uv python install --managed-python 3.13
if ($LASTEXITCODE -ne 0) { Fatal "uv python install falhou." }
if (-not (Get-ChildItem (Join-Path $pkg "python") -ErrorAction SilentlyContinue)) {
    Fatal "python\ ficou vazia — o Python do pacote não foi instalado."
}

Passo "Criando o venv RELOCÁVEL"
# `--relocatable` não é detalhe: um venv comum grava caminhos absolutos e
# quebra ao mudar de máquina ou de letra de unidade, muitas vezes com um erro
# que não diz isso. É o defeito mais provável de um pacote portátil.
# `--seed` inclui o pip: o uv não tem subcomando de download (a spec pedia
# `uv pip download`, que não existe — descoberto ao rodar isto), então quem
# baixa as rodas é o pip de dentro do próprio venv.
& $uv venv --relocatable --seed --managed-python --python 3.13 (Join-Path $pkg "venv")
if ($LASTEXITCODE -ne 0) { Fatal "uv venv --relocatable falhou." }
$cfg = Get-Content (Join-Path $pkg "venv\pyvenv.cfg") -Raw
if ($cfg -notmatch [regex]::Escape((Join-Path $pkg "python"))) {
    Fatal "o venv aponta para um Python FORA do pacote — não sobreviveria à cópia."
}

Passo "Instalando as dependências no venv do pacote"
& $uv pip install --python (Join-Path $pkg "venv") -r (Join-Path $pkg "requirements.txt")
if ($LASTEXITCODE -ne 0) { Fatal "instalação das dependências falhou." }

Passo "Guardando as rodas para reinstalação offline"
# Não é fatal: o venv já viaja com tudo instalado, e as rodas existem só para
# reconstruir o ambiente numa máquina sem rede.
& (Join-Path $pkg "venv\Scripts\python.exe") -m pip download `
    -r (Join-Path $pkg "requirements.txt") -d (Join-Path $pkg "wheels") | Out-Null
if ($LASTEXITCODE -ne 0) { Aviso "rodas não baixadas; o venv basta para o uso normal." }

# --- 4. PortableGit --------------------------------------------------------
if (-not $SemGit) {
    Passo "Baixando o PortableGit (pode demorar — ~70 MB)"
    $api = Invoke-RestMethod "https://api.github.com/repos/git-for-windows/git/releases/latest"
    $asset = $api.assets | Where-Object { $_.name -like "PortableGit-*-64-bit.7z.exe" } | Select-Object -First 1
    if (-not $asset) { Fatal "não encontrei o PortableGit na última release." }
    $exe = Join-Path $env:TEMP $asset.name
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $exe
    & $exe -o"$(Join-Path $pkg 'git')" -y | Out-Null
    if (-not (Test-Path (Join-Path $pkg "git\cmd\git.exe"))) {
        Fatal "git.exe não apareceu em git\cmd após a extração."
    }
} else { Aviso "PortableGit omitido por -SemGit." }

# --- 5. Ollama (CLI, sem modelos) -----------------------------------------
if (-not $SemOllama) {
    Aviso "CLI do Ollama não é baixada automaticamente: o instalador oficial do"
    Aviso "Windows não é portátil de fábrica. Copie ollama.exe para ollama\ à mão,"
    Aviso "ou rode com -SemOllama e deixe modelos locais para a Fase 6."
}

# --- 6. VERIFICAÇÃO DE SEGREDOS (§18.3) ------------------------------------
Passo "Verificando que nenhum segredo entrou no pacote"
# Esta é a única etapa que ABORTA a montagem. Depois da v2.6, a garantia A4
# repousa sobre assinatura por chave que existe numa máquina só; uma chave que
# viajasse aqui estaria em toda máquina que baixou o ZIP, e a marca deixaria de
# significar "esta pessoa, nesta máquina". Seria pior do que não ter assinatura,
# porque teria a aparência de garantia.
$cabecalhos = @("BEGIN OPENSSH PRIVATE KEY","BEGIN RSA PRIVATE KEY",
                "BEGIN EC PRIVATE KEY","BEGIN PRIVATE KEY","BEGIN PGP PRIVATE KEY")
$suspeitos = @()
Get-ChildItem $pkg -Recurse -File | Where-Object { $_.Length -lt 64KB } | ForEach-Object {
    $t = Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue
    if ($t) { foreach ($c in $cabecalhos) { if ($t.Contains($c)) { $suspeitos += $_.FullName; break } } }
}
Get-ChildItem $pkg -Recurse -File -Include "*.pem","*.key","id_ed25519","id_rsa",".env*","allowed_signers" |
    ForEach-Object {
        if ($_.Name -eq "allowed_signers") {
            $linhas = (Get-Content $_.FullName | Where-Object { $_.Trim() -and -not $_.StartsWith("#") })
            if ($linhas) { $suspeitos += "$($_.FullName) (contém chave registrada — deve ir VAZIO)" }
        } else { $suspeitos += $_.FullName }
    }
if ($suspeitos) {
    Write-Host "`nArquivos que não podem entrar no pacote:" -ForegroundColor Red
    $suspeitos | ForEach-Object { Write-Host "   $_" -ForegroundColor Red }
    Fatal "§18.3: nenhuma credencial, nenhuma chave. Remova e monte de novo."
}

# --- 7. TOOLKIT.yaml com os hashes ----------------------------------------
Passo "Escrevendo TOOLKIT.yaml"
function Sha($rel) {
    $p = Join-Path $pkg $rel
    if (Test-Path $p) { (Get-FileHash $p -Algorithm SHA256).Hash.ToLower() } else { "" }
}
$hoje = Get-Date -Format "yyyy-MM-dd"
$versaoGit = if (Test-Path (Join-Path $pkg "git\cmd\git.exe")) {
    (& (Join-Path $pkg "git\cmd\git.exe") --version) -replace "git version ",""
} else { "" }
$versaoUv = (& $uv --version) -replace "uv ",""
@"
# TOOLKIT.yaml — manifesto do pacote portátil (Implementação §18.4)
# GERADO por montar-pacote.ps1 em $hoje. Não editar à mão: um manifesto
# divergente do conteúdo é pior que nenhum, porque a verificação passa a
# afirmar o que não conferiu.
tag: "$Tag"
built_at: "$hoje"
platform: "windows-x64"

git: "$versaoGit"
uv: "$versaoUv"
python: "3.13"
episodic: ""
ollama: ""

# Credenciais e chaves NUNCA entram (§18.3). A etapa 6 da montagem aborta se
# encontrar qualquer uma; allowed_signers viaja VAZIO e a primeira linha nasce
# no `chaos init`, na máquina de destino.

sha256_git__cmd__git.exe: "$(Sha 'git\cmd\git.exe')"
sha256_uv__uv.exe: "$(Sha 'uv\uv.exe')"
sha256_episodic__ai-memory.exe: "$(Sha 'episodic\ai-memory.exe')"
sha256_ollama__ollama.exe: "$(Sha 'ollama\ollama.exe')"
"@ | Set-Content (Join-Path $pkg "TOOLKIT.yaml") -Encoding UTF8

# --- 8. compactar ----------------------------------------------------------
Passo "Compactando"
$zip = Join-Path $raiz "chaos-toolkit-$Tag.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path (Join-Path $pkg "*") -DestinationPath $zip
$mb = [math]::Round((Get-Item $zip).Length / 1MB, 1)

Write-Host "`nPacote pronto: $zip ($mb MB)" -ForegroundColor Green
Write-Host "Na máquina de destino: descompacte e dê duplo clique em INICIAR.cmd."
Write-Host "O que continua sendo instalação lá: o Claude Code (uma linha) e o"
Write-Host "registro do worker no logon (dois minutos no Agendador)."
