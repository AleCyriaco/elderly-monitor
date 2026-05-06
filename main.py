#!/usr/bin/env python3
"""
Monitor Noturno para Idoso — Ponto de entrada principal.

Fluxo:
  captura frame → detecta pose → classifica estado → aciona buzzer → loga → stream

Uso:
  python main.py

Acesso à interface web (na mesma rede):
  http://<ip-da-pi>:8080/
"""

import signal
import socket
import sys
import time
import threading
from datetime import datetime

import config
from camera import Camera
from detector import PoseDetector, PostureState
from buzzer import BuzzerController
from event_logger import EventLogger
from stream import MJPEGServer
from display import LocalDisplay


def is_quiet_hours() -> bool:
    if not config.QUIET_HOURS_ENABLED:
        return False
    h = datetime.now().hour
    return config.QUIET_START_HOUR <= h < config.QUIET_END_HOUR


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    log     = EventLogger()
    camera  = Camera()
    buzzer  = BuzzerController()
    detect  = PoseDetector()
    display = LocalDisplay()

    # ── ACK: silencia buzzer temporariamente ─────────────────────────────────
    _ack_until: list[float] = [0.0]  # lista para mutabilidade em closure

    def handle_ack():
        log.ack_received(config.ACK_SILENCE_SEC)
        _ack_until[0] = time.time() + config.ACK_SILENCE_SEC
        buzzer.stop_alert()

    stream = MJPEGServer(on_ack=handle_ack)

    # ── Encerramento limpo ────────────────────────────────────────────────────
    def shutdown(sig=None, frame=None):
        print()  # nova linha após o status inline
        log.shutdown()
        buzzer.cleanup()
        camera.release()
        display.stop()
        stream.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # ── Inicialização ─────────────────────────────────────────────────────────
    log.startup()

    camera_ok = False
    for attempt in range(1, 4):
        try:
            camera.start()
            log.info("Câmera iniciada com sucesso.")
            camera_ok = True
            break
        except RuntimeError as e:
            log.error(f"Câmera (tentativa {attempt}/3): {e}")
            if attempt < 3:
                log.info("Aguardando 5s para nova tentativa...")
                time.sleep(5)

    if not camera_ok:
        log.error("Câmera não disponível. O servidor web continuará rodando.")
        log.error("Conecte a câmera e reinicie o serviço: sudo systemctl restart monitor")
        stream.update_state("SEM CÂMERA", False)
        # Mantém o web server ativo para não perder o acesso à interface
        signal.pause()  # bloqueia até SIGTERM/SIGINT

    display.start()
    if display.available:
        log.info("Display local iniciado (tela HDMI).")

    stream.start()
    if config.STREAM_ENABLED:
        ip = get_local_ip()
        log.info(f"Interface web disponível em: http://{ip}:{config.STREAM_PORT}/")

    if config.SIMULATE_GPIO:
        log.info("Buzzer em modo simulação — pino GPIO não será acionado.")

    log.info("Monitoramento iniciado. Ctrl+C para encerrar.")
    print("-" * 60)

    # ── Estado da máquina de alertas ─────────────────────────────────────────
    prev_state    = PostureState.UNKNOWN
    alert_state   = None     # PostureState atualmente em alerta
    frame_count   = 0
    fps_tick      = time.time()
    frame_time    = time.time()

    while True:
        # ── Captura ──────────────────────────────────────────────────────────
        frame = camera.read()
        if frame is None:
            # Throttle: loga erro de câmera no máximo 1x a cada 30s
            now = time.time()
            if not hasattr(main, '_last_cam_err') or now - main._last_cam_err > 30:
                log.camera_error("sem frame da câmera — aguardando...")
                main._last_cam_err = now
            time.sleep(0.5)
            continue

        # ── Detecção ─────────────────────────────────────────────────────────
        state, annotated = detect.process(frame)

        # ── Atualiza stream e display local ───────────────────────────────────
        is_alert = alert_state is not None
        stream.update_frame(annotated)
        stream.update_state(state.value, is_alert)
        display.update(annotated)

        # ── Transição de estado ───────────────────────────────────────────────
        if state != prev_state:
            log.state_change(prev_state, state)
            prev_state = state
            _apply_alert(state, alert_state, buzzer, log, _ack_until)
            alert_state = state if state in (PostureState.SITTING, PostureState.STANDING) else None

        # ── FPS display ───────────────────────────────────────────────────────
        frame_count += 1
        elapsed = time.time() - fps_tick
        if elapsed >= 2.0:
            fps = frame_count / elapsed
            quiet_tag = " [SILENCIOSO]" if is_quiet_hours() else ""
            print(
                f"\r[{datetime.now().strftime('%H:%M:%S')}] "
                f"{state.value:<15} | {fps:.1f} fps{quiet_tag}   ",
                end="",
                flush=True,
            )
            frame_count = 0
            fps_tick    = time.time()

        # ── Throttle FPS ──────────────────────────────────────────────────────
        target_interval = 1.0 / config.FPS_CAP
        sleep_time = target_interval - (time.time() - frame_time)
        if sleep_time > 0:
            time.sleep(sleep_time)
        frame_time = time.time()


def _apply_alert(
    state: PostureState,
    current_alert: PostureState | None,
    buzzer: BuzzerController,
    log: EventLogger,
    ack_until: list[float],
):
    """Decide se aciona, troca ou para o buzzer baseado na nova postura."""
    quiet = is_quiet_hours()
    silenced = time.time() < ack_until[0]

    if state in (PostureState.LYING, PostureState.UNKNOWN):
        buzzer.stop_alert()
        return

    if state == PostureState.SITTING:
        if current_alert == PostureState.SITTING:
            return  # já em alerta correto
        buzzer.stop_alert()
        if quiet or silenced:
            log.quiet_suppressed(state.value)
        else:
            log.alert(1, state.value)
            buzzer.start_sitting_alert()

    elif state == PostureState.STANDING:
        buzzer.stop_alert()  # cancela qualquer padrão anterior
        if quiet or silenced:
            log.quiet_suppressed(state.value)
        else:
            log.alert(2, state.value)
            buzzer.start_standing_alert()


if __name__ == "__main__":
    main()
