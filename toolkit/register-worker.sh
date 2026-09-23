#!/usr/bin/env bash
# register-worker.sh — registra o worker do CHAOS/ORDER como serviço systemd
# --user, iniciando automaticamente no logon (Linux).
#
# Equivalente scriptado da Parte 6 (Linux) de TUTORIAL_Instalacao_e_Configuracao.md.
# Usa `bin/order-worker` — não `-m order.worker` (não existe; achado 29) —
# como ExecStart, seguindo o mesmo template de unit file já documentado no
# tutorial. Idempotente: sobrescreve o unit file se já existir e refaz o
# `daemon-reload`/`enable --now`.
#
# Não lida com nenhum dado sensível: só recebe o caminho do repositório.
#
# Uso:
#   bash register-worker.sh /caminho/para/personal-assistant

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "uso: $0 <caminho-do-repositorio>" >&2
    exit 1
fi

REPO_DIR="$(cd "$1" && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT_NAME="chaos-worker.service"
UNIT_PATH="$UNIT_DIR/$UNIT_NAME"

WRAPPER="$REPO_DIR/bin/order-worker"
if [ ! -f "$WRAPPER" ]; then
    echo "Não encontrei $WRAPPER — rode 'chaos init' antes (o worker vendorizado" >&2
    echo "só existe depois da Parte 4.2)." >&2
    exit 1
fi
if [ ! -x "$WRAPPER" ]; then
    chmod +x "$WRAPPER"
fi

PYTHON_BIN="$(command -v python3 || true)"
if [ -z "$PYTHON_BIN" ]; then
    echo "Não encontrei 'python3' no PATH — confira a instalação do Python (Parte 1)." >&2
    exit 1
fi

echo "== Registrando worker no logon =="
echo "  Repositório: $REPO_DIR"
echo "  Unit:        $UNIT_PATH"

mkdir -p "$UNIT_DIR"

cat > "$UNIT_PATH" <<EOF
[Unit]
Description=Worker CHAOS/ORDER de $REPO_DIR — processa a fila local no logon (Parte 6)
After=default.target

[Service]
Type=simple
WorkingDirectory=$REPO_DIR
ExecStart=$PYTHON_BIN $WRAPPER
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now "$UNIT_NAME"

echo "  Serviço registrado e iniciado."
echo ""
echo "Pra conferir o estado:"
echo "  systemctl --user status $UNIT_NAME"
echo "Pra ver os logs:"
echo "  journalctl --user -u $UNIT_NAME -f"
echo "Pra remover:"
echo "  systemctl --user disable --now $UNIT_NAME && rm $UNIT_PATH && systemctl --user daemon-reload"
echo ""
echo "Nota: pra este serviço --user rodar mesmo sem sessão gráfica aberta"
echo "(ex.: servidor sem monitor), talvez seja preciso também:"
echo "  sudo loginctl enable-linger \$USER"
