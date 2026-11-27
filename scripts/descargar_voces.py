"""Descarga voces de Piper con límite de tiempo y reintentos.

Uso:  python -m scripts.descargar_voces es_MX-claude-high en_US-lessac-medium ...
      python -m scripts.descargar_voces --dir data/voices es_MX-claude-high

Sustituye a `python -m piper.download_voices`, que usa urlopen sin límite de tiempo: si Hugging
Face deja la conexión abierta sin mandar datos, se queda esperando para siempre y deja un archivo
vacío. Aquí cada descarga se rinde tras TIMEOUT segundos sin datos, reintenta hasta RETRIES veces
y escribe primero en un archivo .part, que solo se renombra al terminar completo.
"""
import argparse
import re
import sys
import time
from pathlib import Path

import requests

from app import config

URL = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/"
       "{family}/{code}/{name}/{quality}/{code}-{name}-{quality}{ext}?download=true")
VOICE = re.compile(r"^(?P<family>[^-_]+)_(?P<region>[^-]+)-(?P<name>[^-]+)-(?P<quality>.+)$")
TIMEOUT = 30   # segundos sin recibir datos antes de reintentar
RETRIES = 5
MIN_BYTES = 1024


def url_for(voice: str, ext: str) -> str:
    match = VOICE.match(voice.strip())
    if not match:
        raise ValueError(f"Nombre de voz no válido: '{voice}' (ejemplo: es_MX-claude-high)")
    family = match["family"]
    return URL.format(family=family, code=f"{family}_{match['region']}", name=match["name"],
                      quality=match["quality"], ext=ext)


def complete(path: Path) -> bool:
    return path.exists() and path.stat().st_size >= MIN_BYTES


def download(url: str, target: Path) -> None:
    """Baja `url` a `target` con reintentos. Nunca deja un archivo a medias con el nombre final."""
    partial = target.with_name(target.name + ".part")
    for attempt in range(1, RETRIES + 1):
        try:
            with requests.get(url, stream=True, timeout=(15, TIMEOUT)) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length", 0))
                received = 0
                with partial.open("wb") as f:
                    for block in resp.iter_content(1 << 20):
                        f.write(block)
                        received += len(block)
                        if total:
                            print(f"\r  {target.name}: {received / 1e6:5.1f} de {total / 1e6:.1f} MB",
                                  end="", flush=True)
            if total and received != total:
                raise OSError(f"llegaron {received} de {total} bytes")
            if received < MIN_BYTES:
                raise OSError("el archivo llegó vacío")
            partial.replace(target)
            print(f"\r  {target.name}: listo ({received / 1e6:.1f} MB)" + " " * 20)
            return
        except (requests.RequestException, OSError) as error:
            partial.unlink(missing_ok=True)
            print(f"\r  {target.name}: intento {attempt} de {RETRIES} falló ({error})" + " " * 10)
            if attempt == RETRIES:
                raise
            time.sleep(min(2 * attempt, 10))


def download_voice(voice: str, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for ext in (".onnx", ".onnx.json"):
        target = folder / f"{voice}{ext}"
        if complete(target):
            continue
        target.unlink(missing_ok=True)  # restos vacíos de una descarga anterior colgada
        download(url_for(voice, ext), target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Descarga voces de Piper con reintentos.")
    parser.add_argument("voices", nargs="+")
    parser.add_argument("--dir", default=str(config.VOICES_DIR))
    args = parser.parse_args()
    folder = Path(args.dir)
    failed = []
    for voice in args.voices:
        print(f"Voz {voice}")
        try:
            download_voice(voice, folder)
        except (requests.RequestException, OSError, ValueError) as error:
            failed.append(voice)
            print(f"  No se pudo descargar {voice}: {error}")
    if failed:
        print(f"\nFaltan {len(failed)} voces: {', '.join(failed)}. Vuelve a ejecutar para reintentarlas.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
