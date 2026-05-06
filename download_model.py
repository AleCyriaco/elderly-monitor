#!/usr/bin/env python3
"""
Baixa o modelo MoveNet Lightning TFLite para detecção de pose.
Execute uma vez antes de rodar o monitor:
    python download_model.py
"""

import os
import sys
import urllib.request

MODEL_FILE = "movenet_lightning.tflite"
MODEL_SIZE_MB_EXPECTED = 2.0  # ~2.8 MB

# URLs em ordem de preferência
SOURCES = [
    "https://storage.googleapis.com/tfhub-lite-models/google/lite-model/movenet/singlepose/lightning/tflite/float16/4.tflite",
    "https://tfhub.dev/google/lite-model/movenet/singlepose/lightning/tflite/float16/4?lite-format=tflite",
]


def _progress(block_num, block_size, total_size):
    if total_size > 0:
        pct = min(100, block_num * block_size * 100 // total_size)
        mb  = block_num * block_size / 1_048_576
        print(f"\r  {mb:.1f} MB  ({pct}%)", end="", flush=True)


def download():
    if os.path.exists(MODEL_FILE):
        size_mb = os.path.getsize(MODEL_FILE) / 1_048_576
        if size_mb >= MODEL_SIZE_MB_EXPECTED:
            print(f"Modelo já existe: {MODEL_FILE} ({size_mb:.1f} MB)")
            return
        print(f"Arquivo existente parece incompleto ({size_mb:.1f} MB) — rebaixando.")
        os.remove(MODEL_FILE)

    tmp = MODEL_FILE + ".tmp"
    for url in SOURCES:
        print(f"Baixando de: {url}")
        try:
            urllib.request.urlretrieve(url, tmp, reporthook=_progress)
            print()  # nova linha após progresso
            os.rename(tmp, MODEL_FILE)
            size_mb = os.path.getsize(MODEL_FILE) / 1_048_576
            print(f"Modelo salvo: {MODEL_FILE} ({size_mb:.1f} MB)")
            return
        except Exception as e:
            print(f"\n  Falhou: {e}")
            if os.path.exists(tmp):
                os.remove(tmp)

    print("\nERRO: Não foi possível baixar o modelo.")
    print("Alternativa manual:")
    print("  wget -O movenet_lightning.tflite \\")
    print(f'  "{SOURCES[0]}"')
    sys.exit(1)


if __name__ == "__main__":
    download()
