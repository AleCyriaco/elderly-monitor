#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# install.sh — instala dependências do Monitor Noturno na Raspberry Pi
# Execute com: bash install.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

echo "=== Monitor Noturno: instalação ==="
echo ""

# ── 1. Dependências do sistema ────────────────────────────────────────────────
echo "[1/4] Instalando dependências do sistema..."
sudo apt-get update -y -q
sudo apt-get install -y -q \
    python3-pip \
    python3-venv \
    libatlas-base-dev \
    libhdf5-dev \
    libjpeg-dev \
    libopenjp2-7 \
    libcamera-dev \
    v4l-utils \
    ffmpeg

# ── 2. Ambiente virtual Python ────────────────────────────────────────────────
echo ""
echo "[2/4] Criando ambiente virtual Python..."
python3 -m venv venv
source venv/bin/activate

# ── 3. Pacotes Python ─────────────────────────────────────────────────────────
echo ""
echo "[3/4] Instalando pacotes Python..."
pip install --upgrade pip --quiet

pip install -r requirements.txt

# ── 4. Pacotes específicos da Pi ──────────────────────────────────────────────
echo ""
echo "[4/4] Verificando pacotes específicos da Raspberry Pi..."

if [ -f /proc/device-tree/model ]; then
    MODEL=$(tr -d '\0' < /proc/device-tree/model)
    echo "    Modelo detectado: $MODEL"

    # RPi.GPIO geralmente já vem no Raspberry Pi OS, instala se necessário
    python3 -c "import RPi.GPIO" 2>/dev/null || pip install RPi.GPIO

    # picamera2 — tenta instalar via pip (Pi OS recente já inclui)
    python3 -c "import picamera2" 2>/dev/null || \
        pip install picamera2 || \
        echo "    AVISO: picamera2 não instalada. Use câmera USB (USE_PICAMERA2=False)."
else
    echo "    Raspberry Pi não detectada — pulando pacotes GPIO/picamera2."
    echo "    Execute com SIMULATE_GPIO=True em config.py para testar no PC."
fi

echo ""
echo "=== Instalação concluída! ==="
echo ""
echo "Para iniciar o monitor:"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
echo "Para rodar como serviço (auto-start na inicialização):"
echo "  sudo cp monitor.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable monitor.service"
echo "  sudo systemctl start monitor.service"
