@echo off
rem Invólucro para Windows: o script irmão `chaos` é Python com shebang, e o
rem Windows não honra shebang. Sem isto, nem a suíte nem o uso interativo
rem conseguem executar as CLIs na máquina para a qual este sistema foi
rem desenhado. Descoberto ao escrever o runbook de instalação.
py "%~dp0chaos" %*
