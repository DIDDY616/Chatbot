"""Voz: reconocimiento con faster-whisper y síntesis con Piper o Chatterbox.

Motores de síntesis:
- piper:      rápido, corre en CPU, voz sintética.
- chatterbox: más natural y clona voces, pero usa GPU y tarda más.
"""
import io
import os
import site
import threading
import wave
from pathlib import Path

from . import config

# faster-whisper en GPU necesita las DLL de cuBLAS y cuDNN en el PATH antes de cargar
# el modelo. Si PyTorch está instalado deben ser las suyas (torch/lib, que queda primero
# en el PATH): dos versiones de cuDNN en el mismo proceso tumban el servidor. Sin
# PyTorch se usan las de los paquetes nvidia-*-cu12.
for _sp in site.getsitepackages():
    for _dir in ("nvidia/cublas/bin", "nvidia/cudnn/bin", "torch/lib"):
        _bin = Path(_sp) / _dir
        if _bin.is_dir():
            os.environ["PATH"] = f"{_bin}{os.pathsep}{os.environ['PATH']}"

ENGINES = ("piper", "chatterbox")
DEFAULT_CLONE = "predeterminada"  # voz incluida en Chatterbox, sin audio de referencia
LANGUAGE_CODES = ("es", "en", "fr", "sv", "de")

_whisper = None
_piper_voices: dict = {}
_chatterbox = None
_chatterbox_lock = threading.Lock()  # una síntesis a la vez en la GPU


def _get_whisper():
    global _whisper
    if _whisper is None:
        try:
            import torch  # noqa: F401  (debe cargar su cuDNN antes que faster-whisper cargue el suyo)
        except ImportError:
            pass
        from faster_whisper import WhisperModel

        _whisper = WhisperModel(
            config.WHISPER_MODEL, device=config.WHISPER_DEVICE, compute_type=config.WHISPER_COMPUTE
        )
    return _whisper


def transcribe(audio: bytes, language: str | None = None, prompt: str | None = None) -> dict:
    """Audio (wav, webm, mp3...) -> texto. Si no se indica idioma, Whisper lo detecta.

    `prompt` es un texto de ejemplo que orienta a Whisper (p. ej. cómo se escribe un nombre).
    """
    segments, info = _get_whisper().transcribe(
        io.BytesIO(audio), language=language, vad_filter=True, initial_prompt=prompt or None,
    )
    return {
        "text": " ".join(s.text.strip() for s in segments).strip(),
        "language": info.language,
        "language_probability": round(float(info.language_probability or 0.0), 3),
    }


def detect_supported(result: dict, current: str) -> str:
    """Idioma con el que conviene contestar tras transcribir sin idioma fijo.

    Solo se cambia si Whisper detectó uno de los cinco idiomas del asistente con suficiente
    seguridad; en frases muy cortas a veces confunde el español con el portugués o el gallego.
    """
    detected = result.get("language")
    if detected in LANGUAGE_CODES and result.get("language_probability", 0) >= config.LANGUAGE_DETECT_CONFIDENCE:
        return detected
    return current


def word_times(audio: bytes, language: str) -> list[tuple[str, float, float]]:
    """Palabras del audio con su inicio y fin en segundos (para sincronizar los labios)."""
    segments, _ = _get_whisper().transcribe(
        io.BytesIO(audio), language=language, word_timestamps=True,
        beam_size=1, condition_on_previous_text=False,
    )
    return [(w.word.strip(), float(w.start), float(w.end)) for s in segments for w in s.words or []]


def list_voices(language: str | None = None, engine: str = "piper") -> list[str]:
    """Voces disponibles para un motor, con la predeterminada primero."""
    if engine == "chatterbox":
        # Cada .wav en data/voces_clonadas es una voz clonable. Si el nombre empieza con un
        # idioma (es_, en_...) solo se ofrece en ese idioma y va primero, porque trae el
        # acento nativo; los demás nombres sirven para cualquier idioma.
        native, general = [], []
        for name in sorted(p.stem for p in config.CLONE_DIR.glob("*.wav")):
            prefix = name.split("_")[0]
            if prefix not in LANGUAGE_CODES:
                general.append(name)
            elif language is None or prefix == language:
                native.append(name)
        return native + general + [DEFAULT_CLONE]
    if engine != "piper":
        raise ValueError(f"Motor de voz desconocido: '{engine}'")
    names = [p.stem for p in config.VOICES_DIR.glob("*.onnx")]
    names = [n for n in names if language is None or n.startswith(f"{language}_")]
    return sorted(names, key=lambda n: (n not in config.DEFAULT_VOICES.values(), n))


def synthesize(text: str, language: str = "es", voice: str | None = None, engine: str = "piper") -> bytes:
    """Texto -> audio WAV."""
    available = list_voices(language, engine)
    if not available:
        raise ValueError(f"No hay voces instaladas para el idioma '{language}'")
    if voice not in available:
        voice = available[0]
    return _chatterbox_wav(text, language, voice) if engine == "chatterbox" else _piper_wav(text, voice)


def _piper_wav(text: str, voice: str) -> bytes:
    if voice not in _piper_voices:
        from piper import PiperVoice

        _piper_voices[voice] = PiperVoice.load(config.VOICES_DIR / f"{voice}.onnx")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        _piper_voices[voice].synthesize_wav(text, wav_file)
    return buffer.getvalue()


def _chatterbox_wav(text: str, language: str, voice: str) -> bytes:
    global _chatterbox
    reference = None if voice == DEFAULT_CLONE else str(config.CLONE_DIR / f"{voice}.wav")
    with _chatterbox_lock:
        if _chatterbox is None:
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS

            _chatterbox = ChatterboxMultilingualTTS.from_pretrained(device=config.CHATTERBOX_DEVICE)
        samples = _chatterbox.generate(text, language_id=language, audio_prompt_path=reference)
        sample_rate = _chatterbox.sr
        if config.CHATTERBOX_DEVICE == "cuda":
            import torch

            torch.cuda.empty_cache()  # devuelve la memoria temporal: la GPU va justa con el LLM cargado
    pcm = (samples.squeeze().clamp(-1, 1) * 32767).short().cpu().numpy().tobytes()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
    return buffer.getvalue()
