<#
    montar-pacote.ps1 — monta o pacote portátil (Implementação §18).

    Roda UMA vez, na máquina que já funciona, e produz o ZIP que as outras
    máquinas consomem. Não é o assistente de primeiro arranque
    (`primeiro-arranque.ps1`) — aquele roda no destino; este, na origem.

    -RepoOrigem é a ÁRVORE-SEMENTE genérica (tools/, hooks/, bin/ na raiz,
    achado 35) — em D:\cosmos isso é order-tooling\, NÃO a raiz de
    D:\cosmos (que não tem tools\chaos\cli.py) nem um repositório pessoal já
    inicializado como D:\personal-assistant (que não tem hooks\ na raiz —
    depois do `chaos init` os hooks vivem vendorizados em .claude\hooks\,
    não na árvore-semente). Só order-tooling\ (ou equivalente) serve aqui:
    é código genérico, sem nada do conteúdo pessoal de ninguém.

    O que ele NÃO faz, e é deliberado:
      - não baixa modelos do Ollama (gigabytes que o `pull` busca no destino);
      - não inclui credencial nem chave de assinatura — e verifica isso antes
        de compactar, recusando o pacote se encontrar qualquer uma (§18.3);
      - não instala nada fora da pasta do pacote.

    Ollama e ai-memory são OPCIONAIS e opt-IN (ao contrário do Git, que é
    opt-OUT com -SemGit): o Ollama sozinho, sem nenhum modelo, já passa de
    1,7 GB por causa do runtime CUDA/ROCm — bem longe do "pacote enxuto" que
    o resto deste script preserva por padrão. Só entram quando quem monta o
    pacote pede -ComOllama / -ComAiMemory, exatamente pra quem já sabe que
    vai entregar pra alguém que os quer (achado 34).

    Uso:
        .\montar-pacote.ps1 -RepoOrigem D:\cosmos\order-tooling -Tag v0.1.0
        .\montar-pacote.ps1 -RepoOrigem D:\cosmos\order-tooling -Tag v0.1.0 -ComOllama -ComAiMemory
#>
param(
    [Parameter(Mandatory = $true)][string]$RepoOrigem,
    [Parameter(Mandatory = $true)][string]$Tag,
    [string]$Destino = "pacote",
    [switch]$SemGit,
    [switch]$ComOllama,
    [switch]$OllamaComCuda,
    [switch]$ComAiMemory
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path

function Passo($t) { Write-Host "`n== $t" -ForegroundColor Cyan }
function Aviso($t) { Write-Host "   ! $t" -ForegroundColor Yellow }
function Fatal($t) { Write-Host "`nABORTADO: $t" -ForegroundColor Red; exit 1 }

# --- 0. origem -------------------------------------------------------------
Passo "Conferindo o repositório de origem"
if (-not (Test-Path (Join-Path $RepoOrigem "tools\chaos\cli.py"))) {
    Fatal "`$RepoOrigem não parece uma árvore-semente construída (falta tools\chaos\cli.py) — use algo como D:\cosmos\order-tooling, não a raiz de D:\cosmos nem um repositório pessoal já inicializado."
}
if (-not (Test-Path (Join-Path $RepoOrigem "hooks"))) {
    Fatal "`$RepoOrigem não tem hooks\ na raiz — um repositório já inicializado (`chaos init`) não serve aqui, porque os hooks vivem vendorizados em .claude\hooks\, não na árvore-semente (achado 35). Use a árvore-semente (ex.: D:\cosmos\order-tooling)."
}
$tagYaml = Join-Path $RepoOrigem "metadata\tooling.yaml"
if (Test-Path $tagYaml) {
    $tagRepo = (Select-String -Path $tagYaml -Pattern 'vendored_tag:\s*"?([^"\s]+)"?').Matches.Groups[1].Value
    if ($tagRepo -ne $Tag) {
        # Não é fatal, mas é exatamente o descasamento que `chaos health` vai
        # reportar como `drift` em toda máquina que receber este pacote.
        Aviso "tag pedida ($Tag) difere da vendorizada no repositório ($tagRepo)."
    }
} else {
    # A árvore-semente canônica (ex.: order-tooling\) não carrega
    # metadata\tooling.yaml — esse arquivo só existe em repositório já
    # inicializado (achado 35). Sem ele não há o que comparar; não é erro.
    Aviso "`$RepoOrigem não tem metadata\tooling.yaml — pulando a conferência de tag"
    Aviso "(normal quando a origem é a árvore-semente, ex.: order-tooling\)."
}

$pkg = Join-Path $raiz $Destino
if (Test-Path $pkg) { Fatal "`$Destino já existe: $pkg. Apague ou escolha outro." }
New-Item -ItemType Directory -Path $pkg | Out-Null
# Join-Path não normaliza segmentos "." — se $Destino vier com ".\" (era o
# padrão), $pkg carrega esse ".\" literal daqui em diante. Isso não incomoda
# o Windows na hora de criar/achar arquivos, mas o `uv` grava no pyvenv.cfg o
# caminho já canonicalizado (sem o "."), e a checagem de string mais abaixo
# comparava contra o $pkg "sujo" — abortando um venv que na verdade estava
# certo, dentro do pacote (achado 36). Resolvendo uma vez aqui, com a pasta
# já criada, elimina a divergência para o resto do script.
$pkg = (Resolve-Path $pkg).Path

# --- 1. esqueleto e scripts ------------------------------------------------
Passo "Copiando scripts e esqueleto"
foreach ($f in @("INICIAR.cmd","iniciar.sh","LEIA-ME.txt","primeiro-arranque.ps1",
                 "bootstrap.ps1","bootstrap.sh","TOOLKIT.yaml","requirements.txt",
                 "bootstrap_cosmos.py","register-worker.ps1","register-worker.sh")) {
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

# --- 5. Ollama (opcional, opt-IN) ------------------------------------------
# Diferente do Git: aqui o padrão é NÃO baixar. O zip do Windows sozinho, com
# o runtime CUDA/ROCm completo, passa de 1,4 GB — sem nenhum modelo ainda.
# Isso não é o "pacote enxuto" que o resto deste script entrega por padrão,
# então só entra quando -ComOllama é pedido explicitamente (achado 34).
$versaoOllama = ""
if ($ComOllama) {
    Passo "Baixando o Ollama (opcional, -ComOllama)"
    try {
        $ollamaZip = Join-Path $env:TEMP "ollama.zip"
        Invoke-WebRequest -Uri "https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip" -OutFile $ollamaZip
        $tmp = Join-Path $env:TEMP "ollama-extract-$([guid]::NewGuid())"
        Expand-Archive $ollamaZip -DestinationPath $tmp -Force
        if (-not $OllamaComCuda) {
            # CUDA/ROCm sozinhos somam ~1,7 GB e só servem numa GPU NVIDIA/AMD
            # específica. Sem -OllamaComCuda o Ollama sai rodando em CPU (e
            # Vulkan, quando a GPU do destino suportar) — ~200 MB, não ~1,4 GB.
            Aviso "removendo runtime CUDA/ROCm (~1,7 GB) — use -OllamaComCuda para mantê-lo"
            $libOllama = Join-Path $tmp "lib\ollama"
            if (Test-Path $libOllama) {
                Get-ChildItem $libOllama -Directory -Filter "cuda_v*" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
                Get-ChildItem $libOllama -Directory -Filter "rocm*"  -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
            }
        }
        Copy-Item (Join-Path $tmp "*") (Join-Path $pkg "ollama") -Recurse -Force
        Remove-Item $tmp -Recurse -Force
        if (-not (Test-Path (Join-Path $pkg "ollama\ollama.exe"))) {
            throw "ollama.exe não apareceu em ollama\ após a extração"
        }
        try { $versaoOllama = (& (Join-Path $pkg "ollama\ollama.exe") --version | Select-Object -First 1) } catch { $versaoOllama = "instalado" }
        Passo "Ollama pronto. Modelos continuam de fora (Fase 6) — GBs que o 'pull' busca"
        Passo "no destino, e essa parte segue manual de propósito."
    } catch {
        Aviso "Ollama não incluído: $($_.Exception.Message)"
        Aviso "rode de novo com -ComOllama, ou copie ollama.exe pra ollama\ à mão depois."
    }
} else {
    Aviso "Ollama não incluído (opcional — rode com -ComOllama; ~200 MB sem CUDA,"
    Aviso "~1,4 GB com -OllamaComCuda). Sem ele, tarefas 'local_only' de raciocínio"
    Aviso "alto ficam bloqueadas até você instalar (Parte 4 do tutorial)."
}

# --- 5b. ai-memory (camada episódica, opcional, opt-IN) --------------------
# Pequeno (~18 MB) — não é o tamanho que pede opt-in aqui, é o mesmo motivo
# do tutorial (Parte 1.5): é uma adoção deliberada, registrada, feita depois
# do spike de §3.5, nunca assumida (achado 34).
$versaoAiMemory = ""
if ($ComAiMemory) {
    Passo "Baixando o ai-memory (opcional, -ComAiMemory — caminho nativo, experimental no Windows)"
    try {
        $url = "https://github.com/akitaonrails/ai-memory/releases/latest/download/ai-memory-windows-x86_64.zip"
        $zip = Join-Path $env:TEMP "ai-memory.zip"
        Invoke-WebRequest -Uri $url -OutFile $zip
        $shaTxt = (Invoke-WebRequest -Uri "$url.sha256").Content
        $shaEsperado = ($shaTxt -split '\s+')[0].ToLower()
        $shaReal = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
        if ($shaEsperado -and $shaReal -ne $shaEsperado) {
            throw "sha256 não confere (esperado $shaEsperado, obtido $shaReal) — download corrompido"
        }
        Expand-Archive $zip -DestinationPath (Join-Path $pkg "episodic") -Force
        if (-not (Test-Path (Join-Path $pkg "episodic\ai-memory.exe"))) {
            throw "ai-memory.exe não apareceu em episodic\ após a extração"
        }
        try { $versaoAiMemory = (& (Join-Path $pkg "episodic\ai-memory.exe") --version | Select-Object -First 1) } catch { $versaoAiMemory = "instalado" }
        Passo "ai-memory baixado e verificado por sha256"
    } catch {
        Aviso "ai-memory não incluído: $($_.Exception.Message)"
        Aviso "rode de novo com -ComAiMemory, ou copie o binário pra episodic\ à mão depois."
    }
} else {
    Aviso "ai-memory não incluído (opcional — rode com -ComAiMemory). Camada episódica"
    Aviso "de CHAOS §4.2 — o sistema funciona inteiro sem ela (AT-34)."
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
# Uma chave privada de verdade sempre tem o BEGIN *e* o END correspondente.
# Um arquivo-fonte que só cita o cabeçalho como string — como o próprio
# detector de chaves do repositório, tools/chaos/assinatura.py, que precisa
# listar esses textos para reconhecê-los em OUTRO lugar — nunca tem o END ao
# lado. Exigir o par é o que distingue "fala sobre chave privada" de "é uma
# chave privada" (achado 37: o primeiro run real acusou assinatura.py e todo
# .pem público do pacote — cacert.pem, ca-bundle.pem — que não tinham nada a
# esconder).
function ContemChavePrivada($caminho) {
    $t = Get-Content -LiteralPath $caminho -Raw -ErrorAction SilentlyContinue
    if (-not $t) { return $false }
    foreach ($c in $cabecalhos) {
        $fim = $c -replace "^BEGIN ", "END "
        if ($t.Contains("-----$c-----") -and $t.Contains("-----$fim-----")) { return $true }
    }
    return $false
}
$suspeitos = @()
Get-ChildItem $pkg -Recurse -File | Where-Object { $_.Length -lt 64KB } | ForEach-Object {
    if (ContemChavePrivada $_.FullName) { $suspeitos += $_.FullName }
}
# *.pem/*.key também são a extensão de certificados e cadeias PÚBLICAS
# (cacert.pem do certifi, ca-bundle.pem do Git — o pacote não faz HTTPS sem
# eles) — por isso não reprovam pela extensão sozinha, só quando o CONTEÚDO é
# mesmo uma chave privada. Sem limite de tamanho aqui: já sabemos pela
# extensão que vale a pena olhar, e nenhum .pem/.key de verdade é gigante.
Get-ChildItem $pkg -Recurse -File -Include "*.pem","*.key" | ForEach-Object {
    if (ContemChavePrivada $_.FullName) { $suspeitos += $_.FullName }
}
# id_rsa/id_ed25519/.env* não têm equivalente público plausível — continuam
# reprovando só pelo nome.
Get-ChildItem $pkg -Recurse -File -Include "id_ed25519","id_rsa",".env*" | ForEach-Object {
    $suspeitos += $_.FullName
}
Get-ChildItem $pkg -Recurse -File -Include "allowed_signers" | ForEach-Object {
    $linhas = (Get-Content -LiteralPath $_.FullName | Where-Object { $_.Trim() -and -not $_.StartsWith("#") })
    if ($linhas) { $suspeitos += "$($_.FullName) (contém chave registrada — deve ir VAZIO)" }
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
episodic: "$versaoAiMemory"
ollama: "$versaoOllama"

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
if ($ComOllama -and $versaoOllama) { Write-Host "Ollama incluído: $versaoOllama" -ForegroundColor Green }
if ($ComAiMemory -and $versaoAiMemory) { Write-Host "ai-memory incluído: $versaoAiMemory" -ForegroundColor Green }
