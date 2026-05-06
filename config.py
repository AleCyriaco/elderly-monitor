"""
Configurações do sistema de monitoramento noturno.
Edite este arquivo para ajustar o comportamento sem tocar no código principal.
"""

# ── Câmera ────────────────────────────────────────────────────────────────────
USE_PICAMERA2   = True    # True = Pi Camera Module (picamera2), False = USB cam
CAMERA_INDEX    = 0       # índice da câmera USB (ignorado se USE_PICAMERA2=True)
FRAME_WIDTH     = 1280
FRAME_HEIGHT    = 720
FPS_CAP         = 10      # limita FPS para reduzir carga de CPU na Pi
LOCAL_DISPLAY   = False   # True = exibe frame no monitor HDMI local via framebuffer

# ── Detecção de pose (MediaPipe) ──────────────────────────────────────────────
MODEL_COMPLEXITY         = 0     # 0=leve (recomendado Pi), 1=completo, 2=pesado
MIN_DETECTION_CONFIDENCE = 0.40  # reduzido para capturar em condições difíceis
MIN_TRACKING_CONFIDENCE  = 0.40
SMOOTHING_WINDOW         = 8     # frames para confirmar estado (8 @ 10fps = 0.8s)
DEBUG_OVERLAY            = True  # mostrar ângulo e confiança no frame anotado

# ── GPIO / Buzzer ─────────────────────────────────────────────────────────────
BUZZER_PIN    = 18    # pino BCM
SIMULATE_GPIO = True  # True = modo simulação (sem hardware real — útil para dev)

# Padrão SENTADO (alerta nível 1): N bipes, pausa, repete
SITTING_BEEPS         = 3
SITTING_BEEP_ON_SEC   = 0.15
SITTING_BEEP_OFF_SEC  = 0.20
SITTING_REPEAT_SEC    = 10    # reemite alerta a cada N segundos se continuar sentado

# Padrão EM PÉ (alerta nível 2): bipe contínuo até voltar para cama ou confirmação
STANDING_BEEP_ON_SEC  = 0.10
STANDING_BEEP_OFF_SEC = 0.35

# Silêncio após /ack via web — retoma buzzer se ainda em alerta após este tempo
ACK_SILENCE_SEC = 60

# ── Horário silencioso (apenas log, sem buzzer) ───────────────────────────────
# Horário em que a família está acordada e pode monitorar pessoalmente
QUIET_HOURS_ENABLED = True
QUIET_START_HOUR    = 6   # 06:00
QUIET_END_HOUR      = 22  # 22:00

# ── Log ───────────────────────────────────────────────────────────────────────
LOG_FILE = "monitor.log"

# ── Stream MJPEG e interface web ──────────────────────────────────────────────
STREAM_ENABLED = True
STREAM_PORT    = 8080

# ── Limiares de postura (ajuste conforme ângulo da câmera) ───────────────────
# Ângulo do torso (ombros→quadril) em relação à horizontal
# 0° = perfeitamente deitado, 90° = perfeitamente em pé
# Câmera lateral (lado da cama) é o cenário de referência.
LYING_ANGLE_MAX   = 35.0   # abaixo deste ângulo → DEITADO
SITTING_ANGLE_MAX = 68.0   # entre LYING_ANGLE_MAX e este → SENTADO, acima → EM PÉ
