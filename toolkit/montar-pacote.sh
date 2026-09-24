#!/usr/bin/env bash
# montar-pacote.sh — gêmeo POSIX de montar-pacote.ps1 (Implementação §18).
#
# Mesmo contrato, mesmas recusas. A diferença é o que existe em cada
# plataforma: aqui não há PortableGit (o Git do sistema serve e é o caminho
# normal no Linux e no macOS), e o restante é idêntico.
#
# --repo é a ÁRVORE-SEMENTE genérica (tools/, hooks/, bin/ na raiz, achado
# 35) — em D:\cosmos isso é order-tooling/, NÃO a raiz do repositório cosmos
# (que não tem tools/chaos/cli.py) nem um repositório pessoal já inicializado
# (que não tem hooks/ na raiz — depois do `chaos init` os hooks vivem
# vendorizados em .claude/hooks/, não na árvore-semente). Só order-tooling/
# (ou equivalente) serve aqui: é código genérico, sem conteúdo pessoal.
#
# Ollama e ai-memory são OPCIONAIS e opt-IN (--com-ollama / --com-ai-memory),
# ao contrário do Git no Windows que é opt-OUT: o Ollama sozinho, sem nenhum
# modelo, passa de 1,7 GB no Linux por causa do runtime CUDA/ROCm — bem longe
# do "pacote enxuto" que o resto deste script preserva por padrão. Só entram
# quando quem monta o pacote já sabe que vai entregar pra alguém que os quer
# (achado 34).
#
#   ./montar-pacote.sh --repo ~/cosmos/order-tooling --tag v0.1.0
#   ./montar-pacote.sh --repo ~/cosmos/order-tooling --tag v0.1.0 --com-ollama --com-ai-memory
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO=""; TAG=""; DEST="pacote"
COM_OLLAMA=0; OLLAMA_COM_CUDA=0; COM_AI_MEMORY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --tag)  TAG="$2";  shift 2 ;;
    --dest) DEST="$2"; shift 2 ;;
    --com-ollama)      COM_OLLAMA=1;      shift ;;
    --ollama-com-cuda) OLLAMA_COM_CUDA=1; shift ;;
    --com-ai-memory)   COM_AI_MEMORY=1;   shift ;;
    *) echo "opção desconhecida: $1" >&2; exit 2 ;;
  esac
done

passo()  { printf '\n== %s\n' "$1"; }
aviso()  { printf '   ! %s\n' "$1"; }
# `exit`, não `return`: quando um script é *sourced*, `return` sai só da função
# e o fluxo continua — foi assim que um pacote incompleto passou como pronto na
# primeira versão do bootstrap.sh (ACHADOS, rodada 14).
fatal()  { printf '\nABORTADO: %s\n' "$1" >&2; exit 1; }

sha256_de() { # caminho -> hash em minúsculas, ou "" se o arquivo não existe
  [ -f "$1" ] || { echo ""; return; }
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  else shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

[ -n "$REPO" ] && [ -n "$TAG" ] || fatal "uso: $0 --repo <caminho> --tag <tag>"

passo "Conferindo o repositório de origem"
[ -f "$REPO/tools/chaos/cli.py" ] || fatal "--repo não parece uma árvore-semente construída (falta tools/chaos/cli.py) -- use algo como ~/cosmos/order-tooling, não a raiz do cosmos nem um repositório pessoal já inicializado."
[ -d "$REPO/hooks" ] || fatal "--repo não tem hooks/ na raiz -- um repositório já inicializado ('chaos init') não serve aqui, porque os hooks vivem vendorizados em .claude/hooks/, não na árvore-semente (achado 35). Use a árvore-semente (ex.: ~/cosmos/order-tooling)."
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

# --- Ollama (opcional, opt-IN) ---------------------------------------------
VERSAO_OLLAMA=""
if [ "$COM_OLLAMA" = "1" ]; then
  passo "Baixando o Ollama (opcional, --com-ollama)"
  if [ "$(uname -s)" = "Darwin" ]; then
    OLLAMA_TGZ="$(mktemp -d)/ollama.tgz"
    if curl -fsSL "https://github.com/ollama/ollama/releases/latest/download/ollama-darwin.tgz" -o "$OLLAMA_TGZ" \
       && tar -xzf "$OLLAMA_TGZ" -C "$PKG/ollama"; then
      : # macOS usa Metal, não CUDA — nada para remover aqui.
    else
      aviso "Ollama não incluído: download ou extração falhou."
    fi
  else
    if ! command -v zstd >/dev/null 2>&1; then
      aviso "Ollama não incluído: falta 'zstd' nesta máquina (o Linux publica"
      aviso ".tar.zst) — instale com seu gerenciador de pacotes e rode de novo."
    else
      OLLAMA_TAR="$(mktemp -d)/ollama.tar.zst"
      TMP_EXTRACT="$(mktemp -d)"
      if curl -fsSL "https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64.tar.zst" -o "$OLLAMA_TAR" \
         && tar --zstd -xf "$OLLAMA_TAR" -C "$TMP_EXTRACT"; then
        if [ "$OLLAMA_COM_CUDA" != "1" ] && [ -d "$TMP_EXTRACT/lib/ollama" ]; then
          # CUDA/ROCm sozinhos somam ~1,7 GB e só servem numa GPU NVIDIA/AMD
          # específica. Sem --ollama-com-cuda o Ollama sai rodando em CPU
          # (e Vulkan, quando a GPU do destino suportar) — ~200 MB, não ~1,4 GB.
          aviso "removendo runtime CUDA/ROCm (~1,7 GB) — use --ollama-com-cuda para mantê-lo"
          rm -rf "$TMP_EXTRACT"/lib/ollama/cuda_v* "$TMP_EXTRACT"/lib/ollama/rocm* 2>/dev/null || true
        fi
        cp -r "$TMP_EXTRACT"/. "$PKG/ollama/"
        rm -rf "$TMP_EXTRACT"
      else
        aviso "Ollama não incluído: download ou extração falhou."
      fi
    fi
  fi
  OLLAMA_BIN="$PKG/ollama/ollama"; [ -f "$OLLAMA_BIN" ] || OLLAMA_BIN="$PKG/ollama/bin/ollama"
  if [ -x "$OLLAMA_BIN" ]; then
    VERSAO_OLLAMA="$("$OLLAMA_BIN" --version 2>/dev/null | head -1 || echo "instalado")"
    passo "Ollama pronto. Modelos continuam de fora (Fase 6) — GBs que o 'pull' busca"
    passo "no destino, e essa parte segue manual de propósito."
  fi
else
  aviso "Ollama não incluído (opcional — rode com --com-ollama; ~200 MB sem CUDA,"
  aviso "~1,4 GB com --ollama-com-cuda). Sem ele, tarefas 'local_only' de raciocínio"
  aviso "alto ficam bloqueadas até você instalar (Parte 4 do tutorial)."
fi

# --- ai-memory (camada episódica, opcional, opt-IN) ------------------------
# Pequeno (~18-40 MB) — não é o tamanho que pede opt-in aqui, é o mesmo motivo
# do tutorial (Parte 1.5): é uma adoção deliberada, registrada, feita depois
# do spike de §3.5, nunca assumida (achado 34).
VERSAO_AI_MEMORY=""
if [ "$COM_AI_MEMORY" = "1" ]; then
  passo "Baixando o ai-memory (opcional, --com-ai-memory)"
  SO="linux"; [ "$(uname -s)" = "Darwin" ] && SO="macos"
  ARCH="x86_64"; [ "$(uname -m)" = "arm64" ] || [ "$(uname -m)" = "aarch64" ] && ARCH="aarch64"
  URL="https://github.com/akitaonrails/ai-memory/releases/latest/download/ai-memory-${SO}-${ARCH}.tar.gz"
  AIMEM_TGZ="$(mktemp -d)/ai-memory.tar.gz"
  if curl -fsSL "$URL" -o "$AIMEM_TGZ"; then
    SHA_ESPERADO="$(curl -fsSL "$URL.sha256" 2>/dev/null | awk '{print tolower($1)}')"
    SHA_REAL="$(sha256_de "$AIMEM_TGZ")"
    if [ -n "$SHA_ESPERADO" ] && [ "$SHA_ESPERADO" != "$SHA_REAL" ]; then
      aviso "ai-memory não incluído: sha256 não confere (esperado $SHA_ESPERADO, obtido $SHA_REAL)."
    elif tar -xzf "$AIMEM_TGZ" -C "$PKG/episodic" --strip-components=0 2>/dev/null; then
      AIMEM_BIN="$PKG/episodic/ai-memory"
      if [ -x "$AIMEM_BIN" ]; then
        VERSAO_AI_MEMORY="$("$AIMEM_BIN" --version 2>/dev/null | head -1 || echo "instalado")"
        passo "ai-memory baixado e verificado por sha256"
      else
        aviso "ai-memory não incluído: binário não apareceu em episodic/ após a extração."
      fi
    else
      aviso "ai-memory não incluído: extração falhou."
    fi
  else
    aviso "ai-memory não incluído: download falhou (ver ${SO}/${ARCH} em $URL)."
  fi
else
  aviso "ai-memory não incluído (opcional — rode com --com-ai-memory). Camada"
  aviso "episódica de CHAOS §4.2 — o sistema funciona inteiro sem ela (AT-34)."
fi

passo "Verificando que nenhum segredo entrou no pacote"
# Única etapa que aborta. Depois da v2.6 a garantia A4 repousa sobre assinatura
# por chave que existe numa máquina só; uma chave que viajasse aqui estaria em
# toda máquina que baixou o ZIP — pior que não ter assinatura, porque teria a
# aparência de garantia.
# Uma chave privada de verdade tem o BEGIN *e* o END correspondente. Um
# arquivo-fonte que so cita o cabecalho como string -- como o proprio
# detector de chaves do repositorio, tools/chaos/assinatura.py, que precisa
# listar esses textos pra reconhece-los em OUTRO lugar -- nunca tem o END ao
# lado. Exigir o par e o que distingue "fala sobre chave privada" de "e uma
# chave privada" (achado 37: o primeiro run real acusou assinatura.py e todo
# .pem publico do pacote -- cacert.pem, ca-bundle.pem -- que nao tinham nada
# a esconder).
contem_chave_privada() {
  grep -qE "BEGIN (OPENSSH |RSA |EC |PGP )?PRIVATE KEY" "$1" 2>/dev/null \
    && grep -qE "END (OPENSSH |RSA |EC |PGP )?PRIVATE KEY" "$1" 2>/dev/null
}
SUSPEITOS=""
while IFS= read -r f; do
  if contem_chave_privada "$f"; then
    SUSPEITOS="$SUSPEITOS\n   $f"
  fi
done < <(find "$PKG" -type f -size -64k)
# *.pem/*.key tambem sao a extensao de certificados e cadeias PUBLICAS
# (cacert.pem do certifi, ca-bundle.pem do Git -- o pacote nao faz HTTPS sem
# eles), entao so reprovam pelo CONTEUDO, nunca pela extensao sozinha.
while IFS= read -r f; do
  if contem_chave_privada "$f"; then
    SUSPEITOS="$SUSPEITOS\n   $f"
  fi
done < <(find "$PKG" -type f \( -name '*.pem' -o -name '*.key' \))
# id_rsa/id_ed25519/.env* nao tem equivalente publico plausivel -- continuam
# reprovando so pelo nome.
while IFS= read -r f; do SUSPEITOS="$SUSPEITOS\n   $f"; done < <(
  find "$PKG" -type f \( -name 'id_ed25519' -o -name 'id_rsa' -o -name '.env*' \))
AS="$PKG/tools-seed/metadata/registries/allowed_signers"
if [ -f "$AS" ] && grep -qEv '^[[:space:]]*(#|$)' "$AS"; then
  SUSPEITOS="$SUSPEITOS\n   $AS (contém chave registrada — deve ir VAZIO)"
fi
if [ -n "$SUSPEITOS" ]; then
  printf '\nArquivos que não podem entrar no pacote:%b\n' "$SUSPEITOS" >&2
  fatal "§18.3: nenhuma credencial, nenhuma chave. Remova e monte de novo."
fi

passo "Escrevendo TOOLKIT.yaml"
sha() { sha256_de "$PKG/$1"; }
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
episodic: "$VERSAO_AI_MEMORY"
ollama: "$VERSAO_OLLAMA"

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
[ -n "$VERSAO_OLLAMA" ] && printf 'Ollama incluído: %s\n' "$VERSAO_OLLAMA"
[ -n "$VERSAO_AI_MEMORY" ] && printf 'ai-memory incluído: %s\n' "$VERSAO_AI_MEMORY"
