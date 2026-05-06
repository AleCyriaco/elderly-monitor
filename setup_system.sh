#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup_system.sh — configura a Pi para o Monitor Noturno
#
# O que faz:
#   1. Desativa boot gráfico (inicia em modo texto/CLI)
#      → para voltar ao desktop: startx
#   2. Cria regra sudoers para nmcli (gerenciar WiFi sem senha via web)
#   3. Garante que o usuário de instalação está nos grupos certos
#
# Execute com: sudo bash setup_system.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

USUARIO="${MONITOR_USER:-${SUDO_USER:-$(logname 2>/dev/null || whoami)}}"

echo "=== Monitor Noturno: configuração do sistema ==="
echo "Usuário: $USUARIO"
echo ""

# ── 1. Boot em modo texto (CLI) ───────────────────────────────────────────────
echo "[1/3] Desativando boot gráfico (padrão: multi-user / CLI)..."
systemctl set-default multi-user.target
echo "    ✓ Boot configurado para modo texto."
echo "    → Para iniciar o desktop manualmente: startx"
echo "    → Para reverter ao boot gráfico: sudo systemctl set-default graphical.target"
echo ""

# ── 2. Sudoers para nmcli (gerenciamento WiFi sem senha) ─────────────────────
echo "[2/3] Configurando permissão sudo para nmcli..."
SUDOERS_FILE="/etc/sudoers.d/monitor-nmcli"
cat > "$SUDOERS_FILE" << EOF
# Permite que o usuário $USUARIO gerencie WiFi via nmcli sem senha
# (necessário para a interface web do Monitor Noturno)
$USUARIO ALL=(ALL) NOPASSWD: /usr/bin/nmcli dev wifi connect *
$USUARIO ALL=(ALL) NOPASSWD: /usr/bin/nmcli dev wifi connect * password *
$USUARIO ALL=(ALL) NOPASSWD: /usr/bin/nmcli dev disconnect *
EOF
chmod 440 "$SUDOERS_FILE"
visudo -c -f "$SUDOERS_FILE" && echo "    ✓ Regra sudoers criada: $SUDOERS_FILE" || {
    echo "    ✗ Erro na regra sudoers — removendo"
    rm "$SUDOERS_FILE"
    exit 1
}
echo ""

# ── 3. Grupos do usuário ──────────────────────────────────────────────────────
echo "[3/3] Verificando grupos do usuário $USUARIO..."
for grp in video gpio i2c spi; do
    if groups "$USUARIO" | grep -qw "$grp"; then
        echo "    ✓ Grupo $grp: OK"
    else
        usermod -aG "$grp" "$USUARIO"
        echo "    + Adicionado ao grupo $grp"
    fi
done
echo ""

# ── Resumo ────────────────────────────────────────────────────────────────────
echo "=== Configuração concluída! ==="
echo ""
echo "Próximos passos:"
echo "  1. Reinicie a Pi para aplicar boot em modo texto:"
echo "     sudo reboot"
echo ""
echo "  2. Após reinício, o monitor inicia automaticamente."
echo "     Interface web: http://$(hostname -I | awk '{print $1}'):8080/"
echo ""
echo "  3. Para abrir o desktop (quando necessário):"
echo "     startx"
