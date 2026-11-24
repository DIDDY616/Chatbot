"""Mide Chatterbox: tiempo, memoria de GPU y si Whisper entiende lo que dijo.

Uso:  python -m tests.voz_natural
Guarda las muestras en data/muestras/ para escucharlas.
"""
import sys
import time
import wave
import io

import torch

from app import config, voice

sys.stdout.reconfigure(encoding="utf-8")
FRASES = {
    "es": "La baja de una materia se realiza desde el portal de Servicios Escolares antes de la "
          "semana diez del semestre. Después de esa fecha se requiere autorización de la dirección del programa.",
    "en": "You can drop a course until week ten of the semester. After that, you need authorization.",
    "sv": "Biblioteket är öppet måndag till fredag från klockan sju till tjugotvå.",
}
out_dir = config.BASE_DIR / "data" / "muestras"
out_dir.mkdir(parents=True, exist_ok=True)


def vram() -> str:
    free, total = torch.cuda.mem_get_info()
    return f"{(total - free) / 2**30:.1f} de {total / 2**30:.1f} GB"


print("GPU en uso antes de cargar:", vram())
voice.transcribe(voice.synthesize("Prueba.", "es"))
print("GPU con Whisper cargado:   ", vram())
voice.synthesize("Prueba.", "es", engine="chatterbox")
print("GPU con Chatterbox cargado:", vram(), "\n")

for lang, frase in FRASES.items():
    t0 = time.time()
    audio = voice.synthesize(frase, lang, engine="chatterbox")
    seconds = time.time() - t0
    with wave.open(io.BytesIO(audio)) as w:
        duration = w.getnframes() / w.getframerate()
    (out_dir / f"chatterbox_{lang}.wav").write_bytes(audio)
    (out_dir / f"piper_{lang}.wav").write_bytes(voice.synthesize(frase, lang))
    heard = voice.transcribe(audio, lang)["text"]
    print(f"[{lang}] {seconds:.1f}s para generar {duration:.1f}s de audio")
    print(f"     dicho:     {frase}")
    print(f"     escuchado: {heard}\n")

print("GPU al final:", vram())
