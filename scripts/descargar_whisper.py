"""Descarga el modelo de reconocimiento de voz (WHISPER_MODEL en .env) con límite de tiempo y reintentos.

Uso:  python -m scripts.descargar_whisper

faster-whisper lo baja solo la primera vez que se usa, pero si Hugging Face deja la conexión
abierta sin mandar datos se queda esperando para siempre: el avatar muestra la respuesta y se
queda en "Pensando…" sin hablar (los labios se calculan con Whisper). Por eso el instalador lo
baja antes, con un límite de 30 s sin datos y reintentos; lo ya bajado se conserva.
"""
import os
import sys
import time

# Deben definirse antes de importar huggingface_hub (lo importa faster-whisper).
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "30")
os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "30")

from faster_whisper import download_model  # noqa: E402

from app import config  # noqa: E402

RETRIES = 8


def main() -> int:
    for attempt in range(1, RETRIES + 1):
        try:
            path = download_model(config.WHISPER_MODEL)
            print(f"Modelo de Whisper '{config.WHISPER_MODEL}' listo en {path}")
            return 0
        except Exception as error:  # noqa: BLE001  (red caída, tiempo agotado, etc.)
            print(f"Intento {attempt} de {RETRIES} falló ({error}); reintentando…", flush=True)
            time.sleep(min(3 * attempt, 15))
    print("No se pudo descargar el modelo de Whisper. Vuelve a ejecutar este comando.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
