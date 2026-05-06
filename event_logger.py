"""
Log de eventos com timestamp para arquivo e terminal.
"""

import logging
import sys

import config


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("monitor")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Arquivo
    fh = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console (stdout para não misturar com stderr do MediaPipe)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


class EventLogger:
    def __init__(self):
        self._log = setup_logger()

    def startup(self):
        self._log.info("=" * 60)
        self._log.info("Sistema de Monitoramento Noturno — iniciado")
        self._log.info("=" * 60)

    def shutdown(self):
        self._log.info("Sistema encerrado.")

    def state_change(self, old_state, new_state):
        self._log.info(f"Estado: {old_state.value} → {new_state.value}")

    def alert(self, level: int, state_name: str):
        self._log.warning(f"ALERTA nível {level} — {state_name}")

    def quiet_suppressed(self, state_name: str):
        self._log.info(f"Horário silencioso: buzzer suprimido ({state_name})")

    def ack_received(self, silence_sec: int):
        self._log.info(f"ACK recebido — buzzer silenciado por {silence_sec}s")

    def camera_error(self, msg: str):
        self._log.error(f"Câmera: {msg}")

    def info(self, msg: str):
        self._log.info(msg)

    def error(self, msg: str):
        self._log.error(msg)
