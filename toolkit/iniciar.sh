#!/usr/bin/env bash
# iniciar.sh — assistente do pacote portátil (Implementação §18.5)
#
# Prepara o ambiente e pergunta o que fazer: conectar a um repositório
# existente, criar um novo, ou parar por aqui.
#
# LIMITE DELIBERADO (opções 1, 2 e 4): por padrão não age fora da pasta do
# pacote e do repositório que você indicar. Não instala o Claude Code, não
# registra o worker e não grava credencial nenhuma — imprime os comandos no
# fim. A promessa "nada foi instalado fora desta pasta" é verificável, e um
# assistente que a quebrasse por conveniência tornaria o pacote impossível de
# auditar.
#
# A opção 3 é a exceção, deliberada e explícita: quem escolhe "automatizar
# tudo" está pedindo pra sair desse limite — delega a bootstrap_cosmos.py
# (Partes 1 a 6), que roda o Onboarding, registra as chaves, empurra pro
# remoto e registra o worker. Continua nunca guardando frase-secreta nem
# credencial: essas continuam indo direto pro prompt do terminal.

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
ESTADO="$ROOT/ULTIMO-REPO.txt"

titulo() { printf '\n\033[36m%s\033[0m\n' "$1"; }
say()    { printf '  %s\n' "$1"; }
ok()     { printf '  \033[32m[ok]\033[0m   %s\n' "$1"; }
warn()   { printf '  \033[33m[aviso]\033[0m %s\n' "$1"; }
erro()   { printf '  \033[31m[erro]\033[0m %s\n' "$1"; }

perguntar() { # texto, padrão
  local r
  if [ -n "${2:-}" ]; then read -r -p "  $1 [$2]: " r; printf '%s' "${r:-$2}"
  else read -r -p "  $1: " r; printf '%s' "$r"; fi
}

destino_valido() {
  if [ -e "$1" ] && [ -n "$(ls -A "$1" 2>/dev/null)" ]; then
    erro "$1 já existe e não está vazia."
    erro "Escolha outro destino — este assistente nunca escreve por cima de pasta com conteúdo."
    return 1
  fi
  return 0
}

concluir() {
  local repo="$1"
  local automatizado="${2:-0}"
  printf '%s\n' "$repo" > "$ESTADO"

  if [ "$automatizado" != "1" ]; then
    titulo "Verificação"
    if [ -f "$repo/bin/chaos" ]; then
      ( cd "$repo" && python "$repo/bin/chaos" health ) || {
        warn "o toolchain do pacote e o vendorizado no repositório divergem (CHAOS §21.1)."
        warn "Alinhe com:  chaos tooling update <tag>"
        warn "É escrita em caminho protegido, logo é humana — de propósito."
      }
    else
      say "o repositório ainda não tem tools/chaos (Fase 0 não construída)."
    fi
  fi

  if [ "$automatizado" = "1" ]; then
    titulo "Falta um passo, e é seu"
    printf '\n  Claude Code — uma linha, sem sudo:\n'
    printf '     curl -fsSL https://claude.ai/install.sh | bash\n\n'
    say "Onboarding, chaves, push e worker no logon já foram feitos por"
    say "bootstrap_cosmos.py — reveja o que ele fez acima."
  else
    titulo "Faltam dois passos, e os dois são seus"
    printf '\n  1) Claude Code — uma linha, sem sudo:\n'
    printf '     curl -fsSL https://claude.ai/install.sh | bash\n\n'
    printf '  2) Worker no logon — systemd de usuário (ou LaunchAgent no macOS):\n'
    printf '     veja a Parte 6 do tutorial (dois minutos)\n\n'
    say "Este assistente não executa nenhum dos dois de propósito: os dois mexem"
    say "fora desta pasta, e o pacote promete não fazer isso."
  fi
  printf '\n'
  ok "repositório pronto em $repo"
}

# ------------------------------------------------------------------ ambiente
titulo "CHAOS/ORDER — primeiro arranque"
say "pacote: $ROOT"

# shellcheck disable=SC1091
export CHAOS_BOOTSTRAP_QUIET=1
if ! source "$ROOT/bootstrap.sh"; then
  erro "o ambiente não pôde ser preparado — pacote incompleto ou corrompido no download."
  exit 1
fi

# ---------------------------------------------- estado: já há repositório?
if [ -f "$ESTADO" ]; then
  _ant="$(cat "$ESTADO")"
  if [ -d "$_ant" ]; then
    titulo "Este pacote já foi usado"
    say "repositório: $_ant"
    r="$(perguntar 'Usar esse mesmo repositório? (s/n)' 's')"
    case "$r" in [sSyY]*) concluir "$_ant"; exit 0 ;; esac
  fi
fi

# ------------------------------------------------------------------ o menu
titulo "O que você quer fazer?"
printf '\n'
printf '  [1] Conectar a um repositório Git que já tem o meu conteúdo\n'
printf '      (é o caso da segunda máquina em diante)\n\n'
printf '  [2] Criar um repositório novo do zero\n'
printf '      (abre o Onboarding pra você rodar; chaves e worker ficam por sua conta)\n\n'
printf '  [3] Criar um repositório novo e automatizar tudo\n'
printf '      (Onboarding, chaves, push e worker no logon — Partes 1 a 6; sai do\n'
printf '       limite deliberado acima, de propósito, só quando você escolhe isto)\n\n'
printf '  [4] Só preparar o ambiente, sem repositório\n\n'

escolha="$(perguntar 'Opção (1/2/3/4)' '1')"

# ------------------------------------------------------------------ opção 1
if [ "$escolha" = "1" ]; then
  titulo "Conectar a um repositório existente"
  say "A autenticação é a do seu Git (SSH ou gerenciador de credenciais)."
  say "Este assistente não pede, não guarda e não grava token nenhum."
  printf '\n'

  url="$(perguntar 'URL do repositório (ex.: git@github.com:voce/chaos-personal.git)' '')"
  [ -n "$url" ] || { erro "sem URL não há o que clonar."; exit 1; }

  nome="$(basename "$url" .git)"
  destino="$(perguntar 'Onde clonar?' "$HOME/$nome")"
  destino_valido "$destino" || exit 1

  printf '\n'; say "clonando…"
  if ! git clone "$url" "$destino"; then
    erro "o clone falhou. Causas comuns: URL errada, sem acesso à rede, ou a"
    erro "chave desta máquina ainda não tem permissão no repositório."
    exit 1
  fi
  ok "clonado"
  concluir "$destino"
  exit 0
fi

# ------------------------------------------------------------------ opção 2
if [ "$escolha" = "2" ]; then
  titulo "Criar um repositório novo"

  if [ ! -f "$ROOT/tools-seed/bin/chaos" ]; then
    erro "este pacote não traz tools-seed/ — não dá para semear um repositório novo."
    erro "Use a opção 1 com um repositório existente, ou monte o pacote com a semente."
    exit 1
  fi

  say "O repositório não é inventado aqui. Este assistente cria a pasta, roda"
  say "'chaos init' e entrega para o Onboarding (Implementação §3), que é quem"
  say "faz as perguntas que importam: classes de privacidade, áreas, identidades,"
  say "modelos e cotas. Nenhuma delas tem resposta silenciosa."
  printf '\n'

  destino="$(perguntar 'Onde criar?' "$HOME/chaos-personal")"
  destino_valido "$destino" || exit 1

  mkdir -p "$destino"
  ( cd "$destino" && git init -q -b main && python "$ROOT/tools-seed/bin/chaos" init ) || {
    erro "'chaos init' falhou — nada foi deixado pela metade em $destino"; exit 1; }
  ok "repositório semeado em $destino"

  printf '\n'
  say "Agora rode o Onboarding, que é a etapa que define o seu sistema:"
  printf '     cd %s\n' "$destino"
  printf '     python bin/chaos onboarding run\n'
  concluir "$destino"
  exit 0
fi

# ------------------------------------------------------------------ opção 3
if [ "$escolha" = "3" ]; then
  titulo "Criar um repositório novo com tudo automatizado"
  say "Isso roda bootstrap_cosmos.py (Partes 1 a 6): o Onboarding é perguntado"
  say "aqui mesmo — cada pergunta sem resposta anterior é feita a você, nada é"
  say "assumido — as chaves são registradas, o repositório vai pro remoto e o"
  say "worker é registrado no systemd de usuário."
  say "Frase-secreta de chave nunca passa por este script: vai direto pro prompt"
  say "do ssh-keygen/git commit, no terminal."
  printf '\n'

  motor="$ROOT/bootstrap_cosmos.py"
  if [ ! -f "$motor" ]; then
    erro "bootstrap_cosmos.py não encontrado em $ROOT — este pacote não tem o motor automatizado."
    exit 1
  fi

  destino="$(perguntar 'Onde criar?' "$HOME/chaos-personal")"
  destino_valido "$destino" || exit 1

  python3 "$motor" --repo-dir "$destino" --cosmos-dir "$ROOT"
  rc=$?
  if [ "$rc" -ne 0 ]; then
    erro "o instalador parou (código $rc) — rode este menu de novo e escolha [3]:"
    erro "ele retoma exatamente de onde parou, não refaz o que já foi feito."
    exit "$rc"
  fi
  concluir "$destino" 1
  exit 0
fi

# ------------------------------------------------------------------ opção 4
titulo "Ambiente preparado"
say "As ferramentas estão no PATH desta janela. Quando quiser um repositório:"
printf '\n     ./iniciar.sh        (e escolha 1, 2 ou 3)\n\n'
ok "nada foi instalado fora desta pasta."
