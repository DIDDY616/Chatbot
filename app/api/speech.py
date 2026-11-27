"""Voz: reconocimiento, síntesis y labios del avatar."""
import base64

from fastapi import APIRouter, HTTPException, Response, UploadFile
from pydantic import BaseModel

from .. import lipsync, profiles, rag, voice, wake

router = APIRouter(tags=["voz"])


class TTSRequest(BaseModel):
    text: str
    language: str = "es"
    voice: str | None = None
    engine: str = "piper"  # "piper" (rápido) o "chatterbox" (natural)


@router.post("/stt")
def stt(audio: UploadFile, language: str | None = None, current: str = "es", wake_profile: str | None = None):
    """Audio -> texto.

    Con `language` (es, en, fr, sv, de) se transcribe en ese idioma. Sin él, Whisper lo
    detecta y `reply_language` dice en qué idioma conviene contestar (el detectado si es uno
    de los cinco y está seguro; si no, `current`).

    Con `wake_profile` (modo reunión) dice además si la frase nombra a ese asistente
    (`addressed`) y cuál es la pregunta sin el nombre (`question`).
    """
    data = audio.file.read()
    if wake_profile is not None:
        try:
            names = profiles.get(wake_profile).wake_names()
        except KeyError as e:
            raise HTTPException(404, str(e)) from e
        return wake.hear(data, language, names)
    result = voice.transcribe(data, language)
    result["reply_language"] = language or voice.detect_supported(result, current)
    return result


def _synthesize(req: TTSRequest) -> bytes:
    try:
        return voice.synthesize(req.text, req.language, req.voice, req.engine)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.post("/tts")
def tts(req: TTSRequest):
    """Texto -> audio WAV."""
    return Response(_synthesize(req), media_type="audio/wav")


@router.post("/speak")
def speak(req: TTSRequest):
    """Texto -> audio WAV en base64 más los visemas con tiempos para animar al avatar."""
    audio = _synthesize(req)
    return {"audio": base64.b64encode(audio).decode("ascii"), **lipsync.visemes(audio, req.language)}


@router.get("/voices")
def voices(language: str | None = None, engine: str = "piper"):
    try:
        return voice.list_voices(language, engine)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


class WarmupRequest(BaseModel):
    language: str = "es"
    voice: str | None = None
    engine: str = "piper"


@router.post("/warmup")
def warmup(req: WarmupRequest):
    """Carga los modelos en memoria para que la primera respuesta no tarde."""
    rag.warmup()
    voice.transcribe(voice.synthesize("Hola.", req.language))  # carga Whisper
    _synthesize(TTSRequest(text="Hola.", language=req.language, voice=req.voice, engine=req.engine))
    return {"ok": True}
