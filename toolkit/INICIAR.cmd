@echo off
REM ===================================================================
REM  CHAOS/ORDER - pacote portatil
REM
REM  Duplo clique aqui. Este arquivo existe porque o Windows abre .ps1
REM  no Bloco de Notas em vez de executar, e porque a politica de
REM  execucao bloqueia script baixado da internet. Ele so chama o
REM  assistente com a politica liberada apenas para esta execucao -
REM  nada e alterado na maquina.
REM ===================================================================
chcp 65001 >nul
cd /d "%~dp0"

where powershell >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [erro] PowerShell nao encontrado. Este pacote precisa do PowerShell,
    echo         que acompanha o Windows desde a versao 7.
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0primeiro-arranque.ps1" %*
set RC=%ERRORLEVEL%

echo.
if %RC% neq 0 (
    echo  O assistente terminou com erro ^(codigo %RC%^).
) 
pause
exit /b %RC%
