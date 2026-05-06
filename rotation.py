"""
Gerencia a rotação da câmera em tempo real.
Valor é persistido em .camera_rotation (inteiro: 0, 90, 180 ou 270).
"""

import os
import threading

import cv2

_FILE = os.path.join(os.path.dirname(__file__), '.camera_rotation')
_LOCK = threading.Lock()
_DEG  = 0   # valor atual em memória

_CV2_MAP = {
     90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}


def _load() -> None:
    global _DEG
    try:
        with open(_FILE) as f:
            _DEG = int(f.read().strip()) % 360
    except Exception:
        _DEG = 0


def get() -> int:
    with _LOCK:
        return _DEG


def set_rotation(degrees: int) -> None:
    global _DEG
    deg = int(degrees) % 360
    with _LOCK:
        _DEG = deg
    try:
        with open(_FILE, 'w') as f:
            f.write(str(deg))
    except Exception:
        pass


def apply(frame):
    """Aplica a rotação atual ao frame. Retorna o frame (possivelmente rotacionado)."""
    deg = get()
    code = _CV2_MAP.get(deg)
    if code is not None:
        return cv2.rotate(frame, code)
    return frame


# Carrega valor salvo ao importar
_load()
