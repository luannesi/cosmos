#!/usr/bin/env bash
# bootstrap.sh — pacote portátil do CHAOS/ORDER (Implementação §18)
#
# Monta PATH e variáveis PARA ESTA SESSÃO e verifica a integridade do pacote.
# Não instala nada fora da própria pasta e não escreve no perfil do usuário.
#
# Uso (precisa ser *sourced* para as variáveis valerem no seu shell):
#     source ./bootstrap.sh
#     source ./bootstrap.sh --repo ~/chaos-personal
#     ./bootstrap.sh --verify          # só verifica; pode rodar direto
#
# O que ele deliberadamente NÃO faz: atualizar o pacote, baixar ferramenta que
# falte, ou "consertar" divergência de versão. Alinhar toolchain é
# `chaos tooling update <tag>`, escrita em protected path, logo humana.

_bs_sourced=0
(return 0 2>/dev/null) && _bs_sourced=1

_bs_root="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
_bs_repo=""
_bs_verify=0
_bs_skip_hashes=0

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) _bs_repo="$2"; shift 2 ;;
    --verify) _bs_verify=1; shift ;;
    --skip-hashes) _bs_skip_hashes=1; shift ;;
    *) echo "opção desconhecida: $1" >&2; shift ;;
  esac
done

_say()  { printf '  %s\n' "$1"; }
_ok()   { printf '  \033[32m[ok]\033[0m   %s\n' "$1"; }
_warn() { printf '  \033[33m[aviso]\033[0m %s\n' "$1"; }
# Marca fatal em vez de "return": quando o script é *sourced*, `return` sai
# apenas da função e o fluxo continuaria — um pacote incompleto passaria como
# pronto, que é exatamente o que este script existe para impedir.
_bs_fatal=0
_die()  { printf '  \033[31m[erro]\033[0m %s\n' "$1"; _bs_fatal=1; }
_bs_abortar_se_fatal() {
  [ "$_bs_fatal" = 0 ] && return 0
  printf '  \033[31m[erro]\033[0m pacote inutilizável — nada foi preparado.\n'
  return 1
}

printf '\n\033[36mCHAOS/ORDER — pacote portátil\033[0m\n'
printf 'raiz: %s\n\n' "$_bs_root"

# ------------------------------------------------------------------ manifesto
_bs_manifest="$_bs_root/TOOLKIT.yaml"
[ -f "$_bs_manifest" ] || _die "TOOLKIT.yaml não encontrado — este diretório não é um pacote válido."
_bs_abortar_se_fatal || { return 1 2>/dev/null || exit 1; }

# Leitura mínima de YAML plano: o pacote não pode depender de biblioteca externa,
# porque ele é justamente quem prepara o ambiente que teria essa biblioteca.
_bs_tag="$(grep -E '^\s*tag:' "$_bs_manifest" | head -1 | cut -d: -f2- | tr -d ' "')"
[ -n "$_bs_tag" ] || _die "TOOLKIT.yaml não declara \`tag\`."
_bs_abortar_se_fatal || { return 1 2>/dev/null || exit 1; }
_ok "pacote tag $_bs_tag"

# ------------------------------------------------------------------ variáveis
# Tudo para dentro do pacote: nada escrito em \$HOME.
export UV_INSTALL_DIR="$_bs_root/uv"
export UV_PYTHON_INSTALL_DIR="$_bs_root/python"
export UV_CACHE_DIR="$_bs_root/cache/uv"
export UV_TOOL_DIR="$_bs_root/tools/uv"
export UV_TOOL_BIN_DIR="$_bs_root/tools/bin"
export UV_NO_MODIFY_PATH=1
export OLLAMA_MODELS="$_bs_root/models"
export GIT_CONFIG_NOSYSTEM=1        # ignora config de máquina: o pacote é autocontido

for _d in "$_bs_root/uv" "$_bs_root/venv/bin" "$_bs_root/episodic" \
          "$_bs_root/ollama" "$_bs_root/tools/bin"; do
  [ -d "$_d" ] && PATH="$_d:$PATH"
done
export PATH
_ok "PATH e variáveis montados para esta sessão"

# Git portátil é coisa de Windows; no Linux/macOS usa-se o do sistema.
command -v git >/dev/null 2>&1 || _warn "git não encontrado no PATH — instale pelo gerenciador da distribuição"

# ------------------------------------------------------------------ presença
for _par in "uv:$_bs_root/uv/uv" "python:$_bs_root/venv/bin/python"; do
  _nome="${_par%%:*}"; _caminho="${_par#*:}"
  if [ -x "$_caminho" ]; then _ok "$_nome presente"
  else _die "$_nome ausente em $_caminho — pacote incompleto"; fi
done
_bs_abortar_se_fatal || { return 1 2>/dev/null || exit 1; }
for _par in "camada episódica:$_bs_root/episodic/ai-memory" "ollama:$_bs_root/ollama/ollama"; do
  _nome="${_par%%:*}"; _caminho="${_par#*:}"
  if [ -x "$_caminho" ]; then _ok "$_nome presente"
  else _say "[--]   $_nome ausente (opcional — o sistema funciona sem)"; fi
done

# ------------------------------------------------------------------ integridade
if [ "$_bs_skip_hashes" = 0 ] && command -v sha256sum >/dev/null 2>&1; then
  _bs_div=""
  while IFS= read -r _linha; do
    case "$_linha" in sha256_*) ;; *) continue ;; esac
    _chave="${_linha%%:*}"
    _esperado="$(printf '%s' "${_linha#*:}" | tr -d ' "')"
    _rel="$(printf '%s' "${_chave#sha256_}" | sed 's|__|/|g')"
    [ -f "$_bs_root/$_rel" ] || continue
    _real="$(sha256sum "$_bs_root/$_rel" | cut -d' ' -f1)"
    [ "$_real" = "$_esperado" ] || _bs_div="$_bs_div $_rel"
  done < "$_bs_manifest"
  if [ -n "$_bs_div" ]; then
    _warn "hash divergente em:$_bs_div"
    _warn "o download pode estar corrompido — baixe o pacote de novo antes de usar"
  else
    _ok "hashes conferem"
  fi
fi

# ------------------------------------------------------------------ versões
printf '\n'
_say "git      $(git --version 2>&1 || echo ausente)"
_say "uv       $(uv --version 2>&1 || echo ausente)"
_say "python   $(python --version 2>&1 || echo ausente)"
printf '\n'

if [ "$_bs_verify" = 1 ]; then _ok "verificação concluída"; return 0 2>/dev/null || exit 0; fi

# ------------------------------------------------------------------ repositório
if [ -n "$_bs_repo" ]; then
  [ -d "$_bs_repo" ] || _die "repositório não encontrado em $_bs_repo"
  cd "$_bs_repo" || _die "não consegui entrar em $_bs_repo"
  _ok "repositório: $_bs_repo"
  if [ -f "$_bs_repo/bin/chaos" ]; then
    printf '\n'; _say "chaos health:"
    python "$_bs_repo/bin/chaos" health || {
      _warn "toolchain divergente do vendorizado (CHAOS §21.1)."
      _warn "Alinhe com: chaos tooling update <tag>  — escrita em protected path, logo humana."
    }
  else
    _say "o repositório ainda não tem tools/chaos — rode 'chaos onboarding run' depois da Fase 0"
  fi
elif [ "${CHAOS_BOOTSTRAP_QUIET:-0}" != "1" ]; then
  printf '\033[36mPróximo passo:\033[0m\n'
  printf '  git clone <url-do-seu-repo> ~/chaos-<classe>\n'
  printf '  source ./bootstrap.sh --repo ~/chaos-<classe>\n'
fi

printf '\n'
_ok "sessão pronta. Nada foi instalado fora desta pasta."
printf '\n'

if [ "$_bs_sourced" = 0 ]; then
  _warn "executado direto: as variáveis valem só dentro deste script."
  _warn "para prepará-las no seu shell, rode: source ./bootstrap.sh"
fi
