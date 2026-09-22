"""
Guard — allowlist de comandos e protected paths (ORDER §16).

A tabela é organizada por FAMÍLIA de comando, não por plataforma, e vale em
qualquer host: um Windows com Git Bash executa `sed -i`; um Linux com PowerShell
executa `Set-Content`. Detectar a plataforma e negar só a metade correspondente
abriria a outra na máquina que tivesse os dois shells — o caso comum de quem usa
Git no Windows.

O critério, escrito: é negado todo comando que escreva arquivo ou execute código
arbitrário sem passar pela CLI.
"""
from __future__ import annotations

import re

INTERPRETADORES = re.compile(
    r"\b(python3?|node|deno|bun|ruby|perl|php|powershell|pwsh|cmd)\b", re.I)
FLAGS_INLINE = re.compile(r"(^|\s)-(c|e)\b|-Command\b|-EncodedCommand\b|/c\b", re.I)
REDIRECIONAMENTO = re.compile(r">>?\s*\S+|\bOut-File\b|\bSet-Content\b|\bAdd-Content\b", re.I)
EDITORES = re.compile(r"\b(sed\s+-i|tee|dd|truncate|Set-Content|Add-Content)\b", re.I)
GIT_ESCRITA = re.compile(r"\bgit\s+(commit|push|merge|rebase|reset|checkout|tag|am|apply)\b", re.I)
SHELL_ANINHADO = re.compile(r"\b(bash|sh|zsh|dash|cmd|powershell|pwsh)\b.*\b(-c|/c|-Command)\b", re.I)

ALLOWLIST = re.compile(r"^\s*(chaos|order|git\s+(status|log|diff|show|ls-files|rev-parse|fetch)"
                       r"|ls|cat|head|tail|grep|rg|find|wc|echo)\b")


ACOES_DE_ESCRITA = {"write", "edit", "append", "delete"}


def avaliar_comando(argv: list[str]) -> tuple[bool, str]:
    """(permitido, motivo). O motivo é o que o EVT registra e o teste procura."""
    if argv and argv[0] in ACOES_DE_ESCRITA and len(argv) > 1:
        # forma `write <recurso>`: é tentativa de escrita, avaliada por caminho
        from tools.chaos.repo import eh_protegido
        alvo = argv[1]
        if eh_protegido(alvo):
            return False, (f"`{alvo}` é protected path (CHAOS §4.1): governa o "
                           "comportamento de agentes futuros e só humano escreve")
        return True, ""

    linha = " ".join(argv)

    if SHELL_ANINHADO.search(linha) and not ALLOWLIST.match(linha):
        # um shell dentro do outro é a via mais barata de contornar a allowlist
        if INTERPRETADORES.search(linha) or FLAGS_INLINE.search(linha) or \
           REDIRECIONAMENTO.search(linha) or EDITORES.search(linha) or \
           GIT_ESCRITA.search(linha) or re.search(r"\b(sh|bash|powershell|pwsh|cmd)\b.*\b(-c|/c|-Command)\b", linha, re.I):
            return False, "fora da allowlist: shell aninhado executando código arbitrário"

    if GIT_ESCRITA.search(linha):
        return False, ("fora da allowlist: `git` de escrita — o único caminho de "
                       "commit de agente é `chaos commit` (§16)")
    if INTERPRETADORES.search(linha) and FLAGS_INLINE.search(linha):
        return False, "fora da allowlist: interpretador executando código inline"
    if REDIRECIONAMENTO.search(linha):
        return False, "fora da allowlist: redirecionamento de saída para arquivo"
    if EDITORES.search(linha):
        return False, "fora da allowlist: edição de arquivo em lugar, fora da CLI"
    if not ALLOWLIST.match(linha):
        return False, "fora da allowlist: comando não declarado (§16)"
    return True, ""
