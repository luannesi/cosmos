<#
.SYNOPSIS
    Registra o worker do CHAOS/ORDER para iniciar automaticamente no logon
    (Windows), via Agendador de Tarefas.

.DESCRIPTION
    Equivalente scriptado da Parte 6 (Windows) de TUTORIAL_Instalacao_e_Configuracao.md.
    Usa `bin\order-worker` — NÃO `-m order.worker` (esse módulo não existe;
    veja order-tooling/ACHADOS.md, achado 29) — como ExecStart/ação da tarefa.

    Idempotente: se a tarefa já existir, ela é atualizada (Register-ScheduledTask
    -Force), não duplicada.

    Não lida com nenhum dado sensível: só recebe o caminho do repositório e
    monta os caminhos derivados dele (bin\order-worker(.cmd), pythonw.exe do
    ambiente ativo). Nada é gravado fora da própria tarefa agendada do Windows.

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
$action = New-ScheduledTaskAction -Execute $exe -Argument ($exeArgs -join " ") -WorkingDirectory $RepoDir
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName `
    -Action $action -Trigger $trigger -Settings $settings `
    -Description "Worker CHAOS/ORDER de $RepoDir — processa a fila local no logon (Parte 6)." `
    -Force | Out-Null

Write-Host "  Tarefa registrada/atualizada."
Write-Host ""
Write-Host "Pra testar agora sem esperar o próximo logon:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Pra conferir o estado:"
Write-Host "  Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo"
Write-Host "Pra remover:"
Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
