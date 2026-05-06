"""
Detecção de postura via MoveNet Lightning (TFLite / ai-edge-litert).

Classifica 3 estados usando múltiplos indicadores combinados:
  1. Ângulo do torso (ombros→quadril) em relação à horizontal
  2. Posição vertical da cabeça no frame (alto = em pé, baixo = deitado)
  3. Proporção do bounding box do corpo (largo = deitado, alto = em pé)
  4. Visibilidade dos tornozelos (visíveis e baixos = em pé)

Ângulos de referência (câmera lateral à cama):
  DEITADO  < LYING_ANGLE_MAX   graus
  SENTADO  entre os dois limiares
  EM PÉ    > SITTING_ANGLE_MAX graus
"""

import math
import os
from collections import deque
from enum import Enum

import cv2
import numpy as np

import config

# ── Backend TFLite ────────────────────────────────────────────────────────────
try:
    from ai_edge_litert.interpreter import Interpreter as _Interp
except ImportError:
    try:
        from tflite_runtime.interpreter import Interpreter as _Interp  # type: ignore
    except ImportError:
        _Interp = None  # type: ignore

# ── Índices MoveNet (COCO 17 pontos) ─────────────────────────────────────────
_NOSE  = 0
_L_EAR = 3; _R_EAR  = 4
_L_SH  = 5; _R_SH   = 6
_L_HIP = 11; _R_HIP = 12
_L_KN  = 13; _R_KN  = 14
_L_ANK = 15; _R_ANK = 16

# Conexões para desenhar esqueleto
_SKELETON = [
    (_NOSE,3),(_NOSE,4),(3,5),(4,6),          # cabeça
    (_L_SH,_R_SH),(_L_SH,_L_HIP),(_R_SH,_R_HIP),(_L_HIP,_R_HIP),  # tronco
    (_L_SH,7),(7,9),(_R_SH,8),(8,10),          # braços
    (_L_HIP,_L_KN),(_L_KN,_L_ANK),            # perna esquerda
    (_R_HIP,_R_KN),(_R_KN,_R_ANK),            # perna direita
]

_COLORS = {
    "DEITADO":      (0, 210, 0),
    "SENTADO":      (0, 150, 255),
    "EM PÉ":        (0, 0, 240),
    "DESCONHECIDO": (100, 100, 100),
}


class PostureState(Enum):
    UNKNOWN  = "DESCONHECIDO"
    LYING    = "DEITADO"
    SITTING  = "SENTADO"
    STANDING = "EM PÉ"


class PoseDetector:
    MODEL_FILE = "movenet_lightning.tflite"
    INPUT_SIZE = 192

    def __init__(self):
        if _Interp is None:
            raise RuntimeError("Backend TFLite não encontrado. pip install ai-edge-litert")
        if not os.path.exists(self.MODEL_FILE):
            raise RuntimeError(f"Modelo '{self.MODEL_FILE}' não encontrado. Execute: python download_model.py")

        self._interp = _Interp(model_path=self.MODEL_FILE)
        self._interp.allocate_tensors()
        self._in      = self._interp.get_input_details()
        self._out     = self._interp.get_output_details()
        self._in_dtype = self._in[0]['dtype']

        self._history  = deque(maxlen=config.SMOOTHING_WINDOW)
        self._scores   = deque(maxlen=config.SMOOTHING_WINDOW)  # confiança média por frame
        self.current_state = PostureState.UNKNOWN
        self._last_debug   = 0.0
        self._last_angle   = 0.0
        self._last_raw     = PostureState.UNKNOWN

    # ── Processamento principal ───────────────────────────────────────────────

    def process(self, bgr_frame: np.ndarray) -> tuple[PostureState, np.ndarray]:
        h, w = bgr_frame.shape[:2]

        # Pré-processamento: recorte quadrado centralizado → preserva proporções
        side   = min(h, w)
        top    = (h - side) // 2
        left   = (w - side) // 2
        square = bgr_frame[top:top+side, left:left+side]

        rgb = cv2.cvtColor(
            cv2.resize(square, (self.INPUT_SIZE, self.INPUT_SIZE)),
            cv2.COLOR_BGR2RGB,
        )
        inp = np.expand_dims(
            rgb.astype(np.float32 if self._in_dtype == np.float16 else self._in_dtype),
            axis=0,
        )

        self._interp.set_tensor(self._in[0]['index'], inp)
        self._interp.invoke()

        # [1, 1, 17, 3] → [17, 3] com (y, x, conf) normalizados 0-1
        kps = self._interp.get_tensor(self._out[0]['index'])[0, 0]

        raw, angle, score = self._classify(kps)
        self._last_angle = angle
        self._last_raw   = raw
        self._history.append(raw)
        self._scores.append(score)

        smoothed = self._smooth()
        self.current_state = smoothed

        annotated = bgr_frame.copy()
        self._draw_skeleton(annotated, kps, w, h, top, left, side)
        self._draw_overlay(annotated, smoothed, angle, score)
        return smoothed, annotated

    # ── Classificação multi-critério ──────────────────────────────────────────

    def _classify(self, kps: np.ndarray) -> tuple[PostureState, float, float]:
        """
        Retorna (estado, ângulo_torso, confiança_média).

        Câmera no pé da cama capturando perfil lateral:
          DEITADO  — torso horizontal → ângulo baixo  (Stage 1)
          SENTADO  — torso vertical, joelhos/tornozelos em altura média (Stage 2)
          EM PÉ    — torso vertical, tornozelos muito baixos no frame   (Stage 2)
        """
        def conf(i): return float(kps[i, 2])
        def y(i):    return float(kps[i, 0])
        def x(i):    return float(kps[i, 1])

        sh_c  = (conf(_L_SH)  + conf(_R_SH))  / 2
        hip_c = (conf(_L_HIP) + conf(_R_HIP)) / 2

        if sh_c < 0.20 or hip_c < 0.20:
            return PostureState.UNKNOWN, 0.0, max(sh_c, hip_c)

        avg_conf = (sh_c + hip_c) / 2

        sy = (y(_L_SH)  + y(_R_SH))  / 2
        sx = (x(_L_SH)  + x(_R_SH))  / 2
        hy = (y(_L_HIP) + y(_R_HIP)) / 2
        hx = (x(_L_HIP) + x(_R_HIP)) / 2

        angle = math.degrees(math.atan2(abs(hy - sy), abs(hx - sx)))

        # ── Stage 1: DEITADO ──────────────────────────────────────────────────
        # Câmera lateral: corpo horizontal → ângulo do torso próximo de 0°
        # bbox como confirmação: corpo mais largo que alto quando deitado
        vis = [(y(i), x(i)) for i in range(17) if conf(i) > 0.15]
        bbox_ratio = 1.0
        if len(vis) >= 4:
            ys = [p[0] for p in vis]; xs = [p[1] for p in vis]
            bw = max(xs) - min(xs)
            if bw > 0.01:
                bbox_ratio = (max(ys) - min(ys)) / bw

        if angle < config.LYING_ANGLE_MAX and bbox_ratio < 1.4:
            return PostureState.LYING, angle, avg_conf

        # Ângulo alto mas bbox muito largo ainda sugere deitado
        if bbox_ratio < 0.6:
            return PostureState.LYING, angle, avg_conf

        # ── Stage 2: SENTADO vs EM PÉ ────────────────────────────────────────
        # Torso é vertical nos dois casos — usar apenas membros inferiores.
        # Em pé: tornozelos no fundo do frame (pessoa no chão)
        # Sentado: tornozelos em altura média (pernas penduradas na beirada da cama)

        ank_c = (conf(_L_ANK) + conf(_R_ANK)) / 2
        ank_score = 0.5  # neutro quando tornozelos não visíveis
        if ank_c > 0.20:
            ank_y = (y(_L_ANK) + y(_R_ANK)) / 2
            # 0.55 = neutro, 0.85 = muito baixo (em pé)
            ank_score = min(1.0, max(0.0, (ank_y - 0.55) / 0.30))

        kn_c = (conf(_L_KN) + conf(_R_KN)) / 2
        knee_score = 0.5  # neutro quando joelhos não visíveis
        if kn_c > 0.20:
            kn_y  = (y(_L_KN) + y(_R_KN)) / 2
            # queda absoluta no frame: em pé → joelhos bem abaixo do quadril
            knee_drop  = kn_y - hy
            knee_score = min(1.0, max(0.0, knee_drop / 0.25))

        # Score de EM PÉ — só membros inferiores (ângulo do torso ignorado aqui)
        standing_score = ank_score * 0.60 + knee_score * 0.40

        state = PostureState.STANDING if standing_score > 0.65 else PostureState.SITTING

        return state, angle, avg_conf

    def _smooth(self) -> PostureState:
        if not self._history:
            return PostureState.UNKNOWN
        counts: dict[PostureState, int] = {}
        for s in self._history:
            counts[s] = counts.get(s, 0) + 1
        # Maioria simples (>40% dos frames) — menos restritivo que 50%
        majority = max(counts, key=counts.get)
        if counts[majority] >= max(2, len(self._history) * 0.40):
            return majority
        return PostureState.UNKNOWN

    # ── Visualização ──────────────────────────────────────────────────────────

    def _draw_skeleton(self, frame, kps, w, h, crop_top, crop_left, crop_side):
        """Desenha esqueleto ajustando coordenadas ao recorte quadrado."""
        scale = crop_side
        pts = []
        for i in range(17):
            if kps[i, 2] >= 0.15:
                px = int(kps[i, 1] * scale + crop_left)
                py = int(kps[i, 0] * scale + crop_top)
                pts.append((px, py))
                cv2.circle(frame, (px, py), 5, (80, 220, 80), -1)
            else:
                pts.append(None)
        for a, b in _SKELETON:
            if b < len(pts) and pts[a] and pts[b]:
                cv2.line(frame, pts[a], pts[b], (80, 80, 220), 2)

    def _draw_overlay(self, frame, state: PostureState, angle: float, score: float):
        color = _COLORS.get(state.value, (100, 100, 100))
        ov = frame.copy()
        cv2.rectangle(ov, (0, 0), (frame.shape[1], 68), (0, 0, 0), -1)
        cv2.addWeighted(ov, 0.5, frame, 0.5, 0, frame)
        cv2.putText(frame, state.value, (12, 48),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.4, color, 3, cv2.LINE_AA)
        if config.DEBUG_OVERLAY:
            info = f"{angle:.0f}deg  conf:{score:.2f}"
            cv2.putText(frame, info, (frame.shape[1] - 200, 48),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.85, (180, 180, 180), 2, cv2.LINE_AA)
