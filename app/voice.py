"""Voz: reconocimiento con faster-whisper y síntesis con Piper."""
import io
import os
import site
import wave
from pathlib import Path

from . import config

# faster-whisper en GPU necesita las DLL de cuBLAS y cuDNN que instalan los
# paquetes nvidia-*-cu12; hay que ponerlas en el PATH antes de cargar el modelo.
for _sp in site.getsitepackages():
    for _lib in ("cublas", "cudnn"):
        _bin = Path(_sp) / "nvidia" / _lib / "bin"
        if _bin.is_dir():
            os.environ["PATH"] = f"{_bin}{os.pathsep}{os.environ['PATH']}"

_whisper = None
_voices: dict = {}


def _get_whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel

        _whisper = WhisperModel(
            config.WHISPER_MODEL, device=config.WHISPER_DEVICE, compute_type=config.WHISPER_COMPUTE
        )
    return _whisper


def transcribe(audio: bytes, language: str | None = None) -> dict:
    """Audio (wav, webm, mp3...) -> texto. Si no se indica idioma, Whisper lo detecta."""
    segments, info = _get_whisper().transcribe(io.BytesIO(audio), language=language, vad_filter=True)
    return {"text": " ".join(s.text.strip() for s in segments).strip(), "language": info.language}


def list_voices(language: str | None = None) -> list[str]:
    """Voces instaladas en data/voices (p. ej. es_MX-claude-high), opcionalmente por idioma."""
    names = [p.stem for p in config.VOICES_DIR.glob("*.onnx")]
    names = [n for n in names if language is None or n.startswith(f"{language}_")]
    return sorted(names, key=lambda n: (n not in config.DEFAULT_VOICES.values(), n))  # predeterminada primero


def synthesize(text: str, language: str = "es", voice: str | None = None) -> bytes:
    """Texto -> audio WAV."""
    available = list_voices(language)
    if not available:
        raise ValueError(f"No hay voces instaladas para el idioma '{language}'")
    if voice not in available:
        preferred = config.DEFAULT_VOICES.get(language)
        voice = preferred if preferred in available else available[0]
    if voice not in _voices:
        from piper import PiperVoice

        _voices[voice] = PiperVoice.load(config.VOICES_DIR / f"{voice}.onnx")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        _voices[voice].synthesize_wav(text, wav_file)
    return buffer.getvalue()
