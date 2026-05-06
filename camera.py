"""
Abstração de câmera: suporta Picamera2 (módulo nativo da Pi) e USB cam via OpenCV.
Selecione via USE_PICAMERA2 em config.py.
"""

import cv2
import config
import rotation


class Camera:
    def __init__(self):
        self._cap = None
        self._picam = None

    def start(self):
        if config.USE_PICAMERA2:
            self._start_picamera2()
        else:
            self._start_opencv()

    def _start_picamera2(self):
        try:
            from picamera2 import Picamera2
        except ImportError:
            raise RuntimeError(
                "picamera2 não encontrada.\n"
                "Instale com: sudo apt install python3-picamera2\n"
                "Ou configure USE_PICAMERA2 = False para usar câmera USB."
            )
        cameras = Picamera2.global_camera_info()
        if not cameras:
            raise RuntimeError(
                "Nenhuma câmera CSI detectada pelo libcamera.\n"
                "→ Verifique se o cabo flat da câmera está bem encaixado.\n"
                "→ Para câmera USB, configure USE_PICAMERA2 = False em config.py\n"
                "→ Reinicie a Pi após conectar a câmera."
            )
        self._picam = Picamera2()
        # Usa video configuration para melhor qualidade contínua e menor latência
        cam_config = self._picam.create_preview_configuration(
            main={
                "size": (config.FRAME_WIDTH, config.FRAME_HEIGHT),
                "format": "RGB888",
            },
        )
        self._picam.configure(cam_config)
        # Otimizações para câmera NoIR em ambiente escuro com LEDs IR
        self._picam.set_controls({
            "AwbEnable":      False,  # sem balanço de branco (IR é monocromático)
            "AeMeteringMode": 0,      # exposição pela área central
            "AeExposureMode": 1,      # modo noturno (permite exposição mais longa)
            "Sharpness":      2.0,    # aguça bordas (ajuda a detectar postura)
            "Contrast":       1.2,    # leve aumento de contraste para visão noturna
        })
        self._picam.start()

    def _start_opencv(self):
        self._cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Não foi possível abrir câmera USB (índice {config.CAMERA_INDEX}).\n"
                "→ Verifique se a câmera USB está plugada.\n"
                "→ Para câmera nativa Pi (CSI), configure USE_PICAMERA2 = True em config.py"
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
        self._cap.set(cv2.CAP_PROP_FPS, config.FPS_CAP)
        # Reduz buffer interno para minimizar latência
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def read(self):
        """Retorna frame BGR (já rotacionado) como numpy array, ou None em caso de falha."""
        if config.USE_PICAMERA2 and self._picam:
            frame_rgb = self._picam.capture_array()
            frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        elif self._cap:
            ok, frame = self._cap.read()
            if not ok:
                return None
        else:
            return None

        return rotation.apply(frame)

    def release(self):
        if self._picam:
            self._picam.stop()
        if self._cap:
            self._cap.release()
