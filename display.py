"""
Display local da câmera na tela HDMI da Pi.

Modos suportados (detectados automaticamente):
  - framebuffer /dev/fb0  → CLI sem X11 (modo padrão após desativar GUI)
  - X11 cv2.imshow        → quando X está rodando (após startx)

Para não bloquear o loop principal, a escrita no framebuffer roda em thread
separada com FPS limitado (padrão: 5fps — suficiente para monitoramento).
"""

import os
import threading
import time
import logging

import cv2
import numpy as np

import config

log = logging.getLogger("monitor")

# FPS máximo para o display local (independente do FPS de detecção)
_DISPLAY_FPS = 5


class LocalDisplay:
    def __init__(self):
        self._method: str | None = None
        self._fb_file = None
        self._fb_w = 0
        self._fb_h = 0
        self._bpp  = 32

        self._lock      = threading.Lock()
        self._pending   = None           # próximo frame a exibir
        self._thread: threading.Thread | None = None
        self._running   = False

        self._detect_and_init()

    # ── Inicialização ──────────────────────────────────────────────────────────

    def _detect_and_init(self):
        if not config.LOCAL_DISPLAY:
            return  # display local desativado em config.py

        if os.environ.get('DISPLAY'):
            try:
                cv2.namedWindow('Monitor Noturno', cv2.WINDOW_NORMAL)
                cv2.resizeWindow('Monitor Noturno', 960, 540)
                self._method = 'x11'
                log.info("Display local: X11")
                return
            except Exception:
                pass

        fb = '/dev/fb0'
        if os.path.exists(fb):
            try:
                sz_path  = '/sys/class/graphics/fb0/virtual_size'
                bpp_path = '/sys/class/graphics/fb0/bits_per_pixel'
                with open(sz_path) as f:
                    self._fb_w, self._fb_h = map(int, f.read().strip().split(','))
                with open(bpp_path) as f:
                    self._bpp = int(f.read().strip())
                self._fb_file = open(fb, 'rb+')
                self._method  = 'fb'
                log.info(
                    f"Display local: framebuffer {self._fb_w}x{self._fb_h} "
                    f"{self._bpp}bpp ({fb})"
                )
            except PermissionError:
                log.warning(
                    "Display local: sem permissão em /dev/fb0 "
                    "(adicione o usuário ao grupo 'video': sudo usermod -aG video monitor)"
                )
            except Exception as e:
                log.warning(f"Display local: falhou ao abrir framebuffer — {e}")
            return

        log.info("Display local: nenhum disponível (sem DISPLAY e sem /dev/fb0)")

    # ── API pública ────────────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return self._method is not None

    def start(self):
        if not self.available:
            return
        self._running = True
        self._thread  = threading.Thread(
            target=self._display_loop, daemon=True, name="local-display"
        )
        self._thread.start()

    def update(self, frame: np.ndarray):
        """Recebe um novo frame. Será exibido no próximo ciclo do loop."""
        if not self.available:
            return
        with self._lock:
            self._pending = frame

    def stop(self):
        self._running = False
        if self._fb_file:
            self._fb_file.close()
        if self._method == 'x11':
            cv2.destroyAllWindows()

    # ── Loop de exibição (thread separada) ────────────────────────────────────

    def _display_loop(self):
        interval = 1.0 / _DISPLAY_FPS
        while self._running:
            t0 = time.time()
            with self._lock:
                frame = self._pending
                self._pending = None

            if frame is not None:
                try:
                    self._render(frame)
                except Exception as e:
                    log.debug(f"Display render: {e}")

            elapsed = time.time() - t0
            time.sleep(max(0.0, interval - elapsed))

    def _render(self, frame: np.ndarray):
        if self._method == 'x11':
            cv2.imshow('Monitor Noturno', frame)
            cv2.waitKey(1)

        elif self._method == 'fb':
            # Redimensiona para resolução do framebuffer
            resized = cv2.resize(frame, (self._fb_w, self._fb_h),
                                 interpolation=cv2.INTER_LINEAR)
            self._write_fb(resized)

    def _write_fb(self, frame: np.ndarray):
        if self._bpp == 32:
            data = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA).tobytes()
        elif self._bpp == 16:
            # RGB565
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(np.uint16)
            r5  = (rgb[:, :, 0] >> 3).astype(np.uint16)
            g6  = (rgb[:, :, 1] >> 2).astype(np.uint16)
            b5  = (rgb[:, :, 2] >> 3).astype(np.uint16)
            data = ((r5 << 11) | (g6 << 5) | b5).tobytes()
        else:
            return
        self._fb_file.seek(0)
        self._fb_file.write(data)
