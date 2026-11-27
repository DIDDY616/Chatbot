"""Revisa que la instalación esté completa y dice qué falta.

Uso:  python -m scripts.revisar
Termina con código 1 si falta algo indispensable.
"""
import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests

from app import config

# Memoria de video aproximada que pide cada modelo de lenguaje junto con bge-m3 y Whisper.
VRAM_BY_MODEL = {"gemma3:12b": 12, "gemma3:4b": 6, "gemma3:1b": 4}
MIN_VRAM_GB = VRAM_BY_MODEL.get(config.LLM_MODEL, 12)
MODELS = [config.LLM_MODEL, config.EMBED_MODEL]
PACKAGES = ["fastapi", "chromadb", "faster_whisper", "piper", "streamlit", "playwright", "pptx"]
BROWSERS = [
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app",
    "/Applications/Microsoft Edge.app",
]
MAC = sys.platform == "darwin"

missing = 0


def report(level: str, text: str) -> None:
    global missing
    missing += level == "FALTA"
    print(f"{level:6s} {text}")


def check_config() -> None:
    if config.ENV_FILE.exists():
        report("OK", f".env encontrado: modelo {config.LLM_MODEL}, reconocimiento de voz {config.WHISPER_MODEL} "
                     f"en {config.WHISPER_DEVICE}")
    else:
        report("AVISO", "no hay .env: se usan los valores por omisión (copia .env.example como .env)")
    if not config.ADMIN_TOKEN:
        report("AVISO", "sin ADMIN_TOKEN: la consola no pide clave (defínela en .env si otros pueden llegar a esta computadora)")


def check_python() -> None:
    version = sys.version_info
    # En Windows tiene que ser el de python.org (compilado con MSVC); el de MSYS2 no sirve.
    official = "MSC" in sys.version if sys.platform == "win32" else True
    level = "OK" if (3, 10) <= version[:2] < (3, 14) and official else "FALTA"
    report(level, f"Python {version.major}.{version.minor}.{version.micro}"
                  f"{'' if official else ' (no es el de python.org)'}: se necesita 3.10 a 3.13")
    for name in PACKAGES:
        try:
            importlib.import_module(name)
        except ImportError as error:
            if "DLL load failed" in str(error):
                report("FALTA", f"paquete {name} instalado pero no carga: falta el Visual C++ Redistributable "
                                "(winget install -e --id Microsoft.VCRedist.2015+.x64)")
            else:
                report("FALTA", f"paquete {name}: ejecuta pip install -r requirements.txt")


def check_gpu() -> None:
    if MAC:
        # En Apple Silicon Ollama usa la GPU por Metal; faster-whisper no tiene Metal y va en el procesador.
        memory = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout or 0) / 1024**3
        needed = {"gemma3:12b": 24, "gemma3:4b": 16}.get(config.LLM_MODEL, 16)
        report("OK" if memory >= needed else "AVISO",
               f"Mac con {memory:.0f} GB de memoria unificada (recomendado {needed} GB o más para {config.LLM_MODEL})")
        cpu = config.WHISPER_DEVICE == "cpu"
        report("OK" if cpu else "FALTA", "reconocimiento de voz en procesador" + (
            "" if cpu else ": en Mac pon WHISPER_DEVICE=cpu y WHISPER_COMPUTE=int8 en .env"))
        return
    if not shutil.which("nvidia-smi"):
        report("AVISO", "no se encontró una GPU NVIDIA: el reconocimiento de voz y el modelo irán por CPU, muy lentos")
        return
    out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout.strip().splitlines()
    name, total = (part.strip() for part in out[0].split(","))
    gigabytes = int(total) / 1024
    level = "OK" if gigabytes >= MIN_VRAM_GB else "AVISO"
    report(level, f"GPU {name} con {gigabytes:.0f} GB de memoria (recomendado {MIN_VRAM_GB} GB o más)")
    try:
        import ctranslate2
        usable = ctranslate2.get_cuda_device_count() > 0
    except Exception:  # noqa: BLE001
        usable = False
    report("OK" if usable else "AVISO", "reconocimiento de voz en GPU" + ("" if usable else ": no disponible, usa WHISPER_DEVICE=cpu"))


def check_ollama() -> None:
    base = config.LLM_BASE_URL.removesuffix("/v1")
    try:
        names = {m["name"] for m in requests.get(f"{base}/api/tags", timeout=5).json()["models"]}
    except requests.RequestException:
        report("FALTA", f"Ollama no responde en {base}: ábrelo o instálalo desde ollama.com")
        return
    report("OK", "Ollama responde")
    for model in MODELS:
        found = model in names or f"{model}:latest" in names
        report("OK" if found else "FALTA", f"modelo {model}" + ("" if found else f": ejecuta ollama pull {model}"))


def check_files() -> None:
    voices = [p.stem for p in config.VOICES_DIR.glob("*.onnx")]
    for language in ("es", "en"):
        found = [v for v in voices if v.startswith(f"{language}_")]
        report("OK" if found else "FALTA", f"voces en {language}: {len(found)}")
    others = [lang for lang in ("fr", "sv", "de") if not any(v.startswith(f"{lang}_") for v in voices)]
    if others:
        report("AVISO", f"sin voz para: {', '.join(others)} (idiomas opcionales)")

    avatars = list(config.AVATARS_DIR.glob("*.glb"))
    report("OK" if avatars else "FALTA", f"personajes 3D: {len(avatars)}")
    three = config.WEB_DIR / "vendor" / "three" / "build" / "three.module.js"
    report("OK" if three.exists() else "FALTA", "three.js local" + ("" if three.exists() else
                                                                    ": ejecuta python -m scripts.vendorizar_three"))

    documents = [p for p in config.DOCS_DIR.rglob("*") if p.is_file()]
    report("OK" if documents else "AVISO", f"documentos en la base de conocimiento: {len(documents)}")
    try:
        from app.store import collection
        chunks = collection().count()
    except Exception as error:  # noqa: BLE001
        report("FALTA", f"índice de búsqueda: {error}")
        return
    report("OK" if chunks else "AVISO", f"fragmentos indexados: {chunks}" + ("" if chunks else " (ejecuta python -m app.ingest)"))


def check_browser() -> None:
    found = [p for p in BROWSERS if Path(os.path.expandvars(p)).exists()]
    report("OK" if found else "AVISO", "Chrome o Edge para entrar a reuniones de Teams" + ("" if found else ": no encontrado"))


def main() -> int:
    for check in (check_config, check_python, check_gpu, check_ollama, check_files, check_browser):
        check()
    print()
    print("Todo listo." if not missing else f"Faltan {missing} cosas indispensables (las marcadas con FALTA).")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
