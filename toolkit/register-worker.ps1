<#
.SYNOPSIS
    Registra o worker do CHAOS/ORDER para iniciar automaticamente no logon
    (Windows), via Agendador de Tarefas — com fallback pra pasta Inicializar.

.DESCRIPTION
    Equivalente scriptado da Parte 6 (Windows) de TUTORIAL_Instalacao_e_Configuracao.md.
    Usa `bin\order-worker` — NÃO `-m order.worker` (esse módulo não existe;
    veja order-tooling/ACHADOS.md, achado 29) — como ExecStart/ação da tarefa.

    Idempotente: se a tarefa já existir, ela é atualizada (Register-ScheduledTask
    -Force), não duplicada.

    Em máquina corporativa é comum o Agendador de Tarefas recusar o registro
    pra usuário sem privilégio de administrador (Acesso negado, achado 33).
    Quando isso acontece, o script cai automaticamente pra um atalho na pasta
    Inicializar do usuário (`shell:startup`) — não precisa de nenhum
    privilégio especial, só grava um arquivo na pasta de perfil do próprio
    usuário. A diferença prática: a tarefa agendada roda em qualquer logon
    (inclusive sem sessão interativa, dependendo da configuração); o atalho
    só roda quando você faz logon interativo de verdade — o suficiente pro
    worker de uso pessoal.

    Não lida com nenhum dado sensível: só recebe o caminho do repositório e
    monta os caminhos derivados dele (bin\order-worker(.cmd), pythonw.exe do
    ambiente ativo). Nada é gravado fora da própria tarefa agendada do Windows
    ou da pasta Inicializar do usuário atual.

.PARAMETER RepoDir
    Caminho do repositório CHAOS pessoal já inicializado (ex.: D:\personal-assistant).

.PARAMETER TaskName
    Nome da tarefa no Agendador. Default: "COSMOS Worker (<nome da pasta>)".

.EXAMPLE
    .\register-worker.ps1 -RepoDir D:\personal-assistant
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepoDir,

    [string]$TaskName
)

$ErrorActionPreference = "Stop"

$RepoDir = (Resolve-Path -LiteralPath $RepoDir).ProviderPath

if (-not $TaskName) {
    $TaskName = "COSMOS Worker ($(Split-Path -Leaf $RepoDir))"
}

Write-Host "== Registrando worker no logon =="
Write-Host "  Repositório: $RepoDir"
Write-Host "  Tarefa:      $TaskName"

# --- localizar o executável do worker vendorizado no próprio repositório ---
$wrapperCmd = Join-Path $RepoDir "bin\order-worker.cmd"
$wrapperPy = Join-Path $RepoDir "bin\order-worker"

if (Test-Path $wrapperCmd) {
    $exe = $wrapperCmd
    $exeArgs = @()
} elseif (Test-Path $wrapperPy) {
    # sem invólucro .cmd (achado 26): chama o Python diretamente pelo wrapper,
    # já que ele é um script Python executável, não um .py solto.
    $py = (Get-Command python -ErrorAction SilentlyContinue)
    if (-not $py) {
        throw "Não achei 'python' no PATH nem $wrapperCmd — confira a instalação do Python (Parte 1)."
    }
    $exe = $py.Source
    $exeArgs = @($wrapperPy)
} else {
    throw ("Não encontrei bin\order-worker(.cmd) em $RepoDir — rode 'chaos init' antes " +
           "(o worker vendorizado só existe depois da Parte 4.2).")
}

# --- montar a ação, o gatilho e as configurações da tarefa ---
# -Argument não aceita string vazia (nem $null): quando o wrapper .cmd já
# resolve tudo sozinho (sem argumento nenhum pro Execute), o parâmetro tem
# que ser omitido, não passado como "".
if ($exeArgs.Count -gt 0) {
    $action = New-ScheduledTaskAction -Execute $exe -Argument ($exeArgs -join " ") -WorkingDirectory $RepoDir
} else {
    $action = New-ScheduledTaskAction -Execute $exe -WorkingDirectory $RepoDir
}
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

# --- registrar no Agendador de Tarefas, com fallback pra pasta Inicializar ---
# `-ErrorAction Stop` aqui, explícito na chamada: já vimos em máquina real
# que o Agendador pode devolver "Acesso negado" como erro NÃO-terminante,
# que $ErrorActionPreference = "Stop" no escopo do script não intercepta —
# sem isso, o script seguia adiante como se tivesse dado certo (achado 33).
$registrado = $false
try {
    Register-ScheduledTask -TaskName $TaskName `
        -Action $action -Trigger $trigger -Settings $settings `
        -Description "Worker CHAOS/ORDER de $RepoDir — processa a fila local no logon (Parte 6)." `
        -Force -ErrorAction Stop | Out-Null
    $registrado = $true
} catch {
    Write-Host ""
    Write-Host "  [aviso] Agendador de Tarefas recusou o registro: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "  Comum em máquina corporativa com política que restringe o Agendador" -ForegroundColor Yellow
    Write-Host "  pra quem não é administrador. Caindo pro atalho na pasta Inicializar." -ForegroundColor Yellow
}

if ($registrado) {
    Write-Host "  Tarefa registrada/atualizada no Agendador de Tarefas."
    Write-Host ""
    Write-Host "Pra testar agora sem esperar o próximo logon:"
    Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
    Write-Host "Pra conferir o estado:"
    Write-Host "  Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo"
    Write-Host "Pra remover:"
    Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
} else {
    # Atalho .lnk na pasta Inicializar do usuário atual — não exige nenhum
    # privilégio: é uma escrita comum na própria pasta de perfil.
    $startupDir = [Environment]::GetFolderPath('Startup')
    $lnkPath = Join-Path $startupDir "$TaskName.lnk"

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($lnkPath)
    $shortcut.TargetPath = $exe
    if ($exeArgs.Count -gt 0) {
        $shortcut.Arguments = ($exeArgs -join " ")
    }
    $shortcut.WorkingDirectory = $RepoDir
    $shortcut.Description = "Worker CHAOS/ORDER de $RepoDir (Parte 6, via pasta Inicializar)"
    $shortcut.Save()

    Write-Host "  Atalho criado: $lnkPath"
    Write-Host ""
    Write-Host "  Isso roda o worker a cada logon interativo — não em segundo plano sem"
    Write-Host "  sessão aberta, ao contrário do Agendador, mas não exige privilégio"
    Write-Host "  nenhum, e basta pro uso pessoal."
    Write-Host ""
    Write-Host "Pra testar agora sem esperar o próximo logon, abra o atalho:"
    Write-Host "  Invoke-Item '$lnkPath'"
    Write-Host "Pra remover:"
    Write-Host "  Remove-Item '$lnkPath'"
}
