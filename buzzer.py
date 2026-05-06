"""
Controle do buzzer via GPIO (BCM).

Padrões em threads separadas para não bloquear o loop principal.
Em SIMULATE_GPIO=True (ou fora de uma Pi real) apenas imprime no log.
"""

import threading
import time
import logging

import config

log = logging.getLogger("monitor")

try:
    import RPi.GPIO as GPIO
    _GPIO_AVAILABLE = True
except ImportError:
    _GPIO_AVAILABLE = False


class BuzzerController:
    def __init__(self):
        self._simulating = config.SIMULATE_GPIO or not _GPIO_AVAILABLE
        if not self._simulating:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(config.BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
        else:
            log.info("Buzzer em modo SIMULAÇÃO (GPIO não disponível ou SIMULATE_GPIO=True)")

        self._lock          = threading.Lock()
        self._stop_event    = threading.Event()
        self._active_thread: threading.Thread | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    def start_sitting_alert(self):
        """Alerta nível 1: N bipes, aguarda SITTING_REPEAT_SEC, repete."""
        self._start_pattern(self._sitting_pattern)
        log.debug("Buzzer: padrão SENTADO iniciado")

    def start_standing_alert(self):
        """Alerta nível 2: bipe contínuo até stop_alert() ou cleanup()."""
        self._start_pattern(self._standing_pattern)
        log.debug("Buzzer: padrão EM PÉ iniciado")

    def stop_alert(self):
        """Para qualquer alerta em curso e desliga o pino."""
        with self._lock:
            if self._active_thread and self._active_thread.is_alive():
                self._stop_event.set()
                self._active_thread.join(timeout=3.0)
            self._stop_event.clear()
            self._active_thread = None
        self._set_pin(False)

    def cleanup(self):
        """Encerramento limpo: para alertas e libera GPIO."""
        self.stop_alert()
        if not self._simulating:
            GPIO.cleanup()

    # ── Patterns ──────────────────────────────────────────────────────────────

    def _sitting_pattern(self, stop: threading.Event):
        while not stop.is_set():
            for _ in range(config.SITTING_BEEPS):
                if stop.is_set():
                    break
                self._beep(config.SITTING_BEEP_ON_SEC, config.SITTING_BEEP_OFF_SEC)
            # Aguarda SITTING_REPEAT_SEC em fatias de 100ms para responder ao stop
            ticks = int(config.SITTING_REPEAT_SEC * 10)
            for _ in range(ticks):
                if stop.is_set():
                    break
                time.sleep(0.1)
        self._set_pin(False)

    def _standing_pattern(self, stop: threading.Event):
        while not stop.is_set():
            self._beep(config.STANDING_BEEP_ON_SEC, config.STANDING_BEEP_OFF_SEC)
        self._set_pin(False)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _beep(self, on_sec: float, off_sec: float):
        self._set_pin(True)
        time.sleep(on_sec)
        self._set_pin(False)
        time.sleep(off_sec)

    def _set_pin(self, high: bool):
        if self._simulating:
            if high:
                log.debug("BUZZER ON")
        else:
            GPIO.output(config.BUZZER_PIN, GPIO.HIGH if high else GPIO.LOW)

    def _start_pattern(self, pattern_fn):
        with self._lock:
            # Para padrão anterior se houver
            if self._active_thread and self._active_thread.is_alive():
                self._stop_event.set()
                self._active_thread.join(timeout=3.0)
            self._stop_event = threading.Event()
            self._active_thread = threading.Thread(
                target=pattern_fn,
                args=(self._stop_event,),
                daemon=True,
                name="buzzer-pattern",
            )
            self._active_thread.start()
