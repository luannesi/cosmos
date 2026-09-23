#!/usr/bin/env bash
# montar-pacote.sh — gêmeo POSIX de montar-pacote.ps1 (Implementação §18).
#
# Mesmo contrato, mesmas recusas. A diferença é o que existe em cada
# plataforma: aqui não há PortableGit (o Git do sistema serve e é o caminho
# normal no Linux e no macOS), e o restante é idêntico.
#
#   ./montar-pacote.sh --repo ~/chaos-pessoal --tag v0.1.0
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO=""; TAG=""; DEST="pacote"

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --tag)  TAG="$2";  shift 2 ;;
    --dest) DEST="$2"; shift 2 ;;
    *) echo "opção desconhecida: $1" >&2; exit 2 ;;
  esac
done

passo()  { printf '\n== %s\n' "$1"; }
aviso()  { printf '   ! %s\n' "$1"; }
# `exit`, não `return`: quando um script é *sourced*, `return` sai só da função
# e o fluxo continua — foi assim que um pacote incompleto passou como pronto na
# primeira versão do bootstrap.sh (ACHADOS, rodada 14).
fatal()  { printf '\nABORTADO: %s\n' "$1" >&2; exit 1; }

[ -n "$REPO" ] && [ -n "$TAG" ] || fatal "uso: $0 --repo <caminho> --tag <tag>"

passo "Conferindo o repositório de origem"
[ -f "$REPO/tools/chaos/cli.py" ] || fatal "--repo não parece um repositório CHAOS construído."
if [ -f "$REPO/metadata/tooling.yaml" ]; then
  TAG_REPO="$(sed -n 's/.*vendored_tag:[[:space:]]*"\{0,1\}\([^"[:space:]]*\).*/\1/p' \
              "$REPO/metadata/tooling.yaml" | head -1)"
  [ "$TAG_REPO" = "$TAG" ] || aviso "tag pedida ($TAG) difere da vendorizada ($TAG_REPO)."
fi

PKG="$RAIZ/$DEST"
[ -e "$PKG" ] && fatal "$PKG já existe. Apague ou escolha outro --dest."
mkdir -p "$PKG"

passo "Copiando scripts e esqueleto"
for f in INICIAR.cmd iniciar.sh LEIA-ME.txt primeiro-arranque.ps1 \
         bootstrap.ps1 bootstrap.sh TOOLKIT.yaml requirements.txt \
         bootstrap_cosmos.py register-worker.ps1 register-worker.sh; do
  cp "$RAIZ/$f" "$PKG/"
done
mkdir -p "$PKG"/{uv,python,venv,wheels,episodic,ollama,models,tools-seed}

passo "Semeando tools-seed/"
for d in tools hooks bin; do cp -r "$REPO/$d" "$PKG/tools-seed/"; done
find "$PKG/tools-seed" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

passo "Baixando o uv"
UV_TGZ="$(mktemp -d)/uv.tar.gz"
ALVO="x86_64-unknown-linux-gnu"
[ "$(uname -s)" = "Darwin" ] && ALVO="aarch64-apple-darwin"
curl -fsSL "https://github.com/astral-sh/uv/releases/latest/download/uv-${ALVO}.tar.gz" -o "$UV_TGZ"
tar -xzf "$UV_TGZ" -C "$PKG/uv" --strip-components=1
UV="$PKG/uv/uv"
[ -x "$UV" ] || fatal "uv não apareceu em uv/ após a extração."

passo "Instalando o Python gerenciado dentro do pacote"
# `--managed-python` é obrigatório e não é preciosismo: sem ele, numa máquina
# de montagem que JÁ tenha Python 3.13, o uv usa o do sistema, a pasta
# python/ do pacote fica vazia e o venv aponta para um interpretador que não
# existe no destino. O pacote sai aparentemente completo e quebra na outra
# máquina. Descoberto ao rodar a montagem pela primeira vez.
export UV_PYTHON_INSTALL_DIR="$PKG/python"
"$UV" python install --managed-python 3.13 || fatal "uv python install falhou."
[ -n "$(ls -A "$PKG/python" 2>/dev/null)" ] || fatal "python/ ficou vazia — o Python do pacote não foi instalado."

passo "Criando o venv RELOCÁVEL"
# Sem --relocatable o venv grava caminhos absolutos e quebra na outra máquina,
# quase sempre com um erro que não diz isso.
# `--seed` inclui o pip: o uv não tem subcomando de download (descoberto ao
# rodar isto pela primeira vez — a spec pedia `uv pip download`, que não
# existe), então quem baixa as rodas é o pip de dentro do próprio venv.
"$UV" venv --relocatable --seed --managed-python \
    --python 3.13 "$PKG/venv" || fatal "uv venv --relocatable falhou."
grep -q "^home = $PKG/python" "$PKG/venv/pyvenv.cfg" \
    || fatal "o venv aponta para um Python FORA do pacote — não sobreviveria à cópia."

passo "Instalando as dependências no venv do pacote"
"$UV" pip install --python "$PKG/venv" \
    -r "$PKG/requirements.txt" || fatal "instalação das dependências falhou."

passo "Guardando as rodas para reinstalação offline"
# Não é fatal: o venv já viaja com tudo instalado, e as rodas existem só para
# reconstruir o ambiente numa máquina sem rede. Falhar a montagem inteira por
# causa de uma conveniência seria desproporcional.
"$PKG/venv/bin/python" -m pip download -r "$PKG/requirements.txt" \
    -d "$PKG/wheels" >/dev/null 2>&1 || aviso "rodas não baixadas; o venv basta para o uso normal."

passo "Verificando que nenhum segredo entrou no pacote"
# Única etapa que aborta. Depois da v2.6 a garantia A4 repousa sobre assinatura
# por chave que existe numa máquina só; uma chave que viajasse aqui estaria em
# toda máquina que baixou o ZIP — pior que não ter assinatura, porque teria a
# aparência de garantia.
SUSPEITOS=""
while IFS= read -r f; do
  if head -c 200 "$f" 2>/dev/null | grep -qE "BEGIN (OPENSSH|RSA|EC|PGP)? ?PRIVATE KEY"; then
    SUSPEITOS="$SUSPEITOS\n   $f"
  fi
done < <(find "$PKG" -type f -size -64k)
while IFS= read -r f; do SUSPEITOS="$SUSPEITOS\n   $f"; done < <(
  find "$PKG" -type f \( -name '*.pem' -o -name '*.key' -o -name 'id_ed25519' \
       -o -name 'id_rsa' -o -name '.env*' \))
AS="$PKG/tools-seed/metadata/registries/allowed_signers"
if [ -f "$AS" ] && grep -qEv '^[[:space:]]*(#|$)' "$AS"; then
  SUSPEITOS="$SUSPEITOS\n   $AS (contém chave registrada — deve ir VAZIO)"
fi
if [ -n "$SUSPEITOS" ]; then
  printf '\nArquivos que não podem entrar no pacote:%b\n' "$SUSPEITOS" >&2
  fatal "§18.3: nenhuma credencial, nenhuma chave. Remova e monte de novo."
fi

passo "Escrevendo TOOLKIT.yaml"
sha() { [ -f "$PKG/$1" ] && sha256sum "$PKG/$1" | cut -d' ' -f1 || echo ""; }
HOJE="$(date +%F)"
PLAT="linux-x64"; [ "$(uname -s)" = "Darwin" ] && PLAT="darwin-arm64"
cat > "$PKG/TOOLKIT.yaml" <<EOF
# TOOLKIT.yaml — manifesto do pacote portátil (Implementação §18.4)
# GERADO por montar-pacote.sh em $HOJE. Não editar à mão: um manifesto
# divergente do conteúdo é pior que nenhum, porque a verificação passa a
# afirmar o que não conferiu.
tag: "$TAG"
built_at: "$HOJE"
platform: "$PLAT"

git: ""          # no Linux/macOS usa-se o Git do sistema
uv: "$("$UV" --version | sed 's/uv //')"
python: "3.13"
episodic: ""
ollama: ""

# Credenciais e chaves NUNCA entram (§18.3). A verificação acima aborta a
# montagem se encontrar qualquer uma; allowed_signers viaja VAZIO e a primeira
# linha nasce no \`chaos init\`, na máquina de destino.

sha256_uv__uv: "$(sha uv/uv)"
sha256_episodic__ai-memory: "$(sha episodic/ai-memory)"
sha256_ollama__ollama: "$(sha ollama/ollama)"
EOF

passo "Compactando"
ZIP="$RAIZ/chaos-toolkit-$TAG.zip"
rm -f "$ZIP"
(cd "$PKG" && zip -qr "$ZIP" .)
printf '\nPacote pronto: %s (%s)\n' "$ZIP" "$(du -h "$ZIP" | cut -f1)"
printf 'Na máquina de destino: descompacte e rode ./iniciar.sh\n'
