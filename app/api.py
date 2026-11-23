"""API del asistente.  Uso:  uvicorn app.api:app --port 8000

La página del avatar queda en http://localhost:8000/avatar/
"""
import base64
import json
import mimetypes

from fastapi import FastAPI, HTTPException, Response, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, lipsync, profiles, rag, voice
from .ingest import ingest_all
from .store import collection

# En Windows el registro puede asignar tipos incorrectos y el navegador rechaza los módulos JS.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("model/gltf-binary", ".glb")

app = FastAPI(title="Asistente Tec")


# ---------- Conversación ----------

class ChatRequest(BaseModel):
    session_id: str
    message: str
    language: str = "es"
    profile: str = profiles.DEFAULT_PROFILE


class ChatResponse(BaseModel):
    answer: str
    answered: bool
    sources: list[str]


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        return rag.answer(req.session_id, req.message, req.language, req.profile)
    except KeyError as e:
        raise HTTPException(404, e.args[0])


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """Igual que /chat pero por partes (una línea JSON por evento), para hablar sin esperar el final."""
    try:
        profiles.get(req.profile)
    except KeyError as e:
        raise HTTPException(404, e.args[0])
    events = rag.answer_stream(req.session_id, req.message, req.language, req.profile)
    lines = (json.dumps(event, ensure_ascii=False) + "\n" for event in events)
    return StreamingResponse(lines, media_type="application/x-ndjson")


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    rag.reset(session_id)
    return {"ok": True}


# ---------- Perfiles de asistente ----------

@app.get("/profiles")
def list_profiles() -> dict[str, profiles.Profile]:
    return profiles.load()


@app.put("/profiles/{profile_id}")
def save_profile(profile_id: str, profile: profiles.Profile):
    profiles.save(profile_id, profile)
    return {"ok": True}


@app.delete("/profiles/{profile_id}")
def delete_profile(profile_id: str):
    profiles.delete(profile_id)
    return {"ok": True}


# ---------- Voz ----------

class TTSRequest(BaseModel):
    text: str
    language: str = "es"
    voice: str | None = None
    engine: str = "piper"  # "piper" (rápido) o "chatterbox" (natural)


@app.post("/stt")
def stt(audio: UploadFile, language: str | None = None):
    """Audio -> texto. `language` es opcional (es, en, fr, sv, de); sin él se detecta."""
    return voice.transcribe(audio.file.read(), language)


@app.post("/tts")
def tts(req: TTSRequest):
    """Texto -> audio WAV."""
    try:
        audio = voice.synthesize(req.text, req.language, req.voice, req.engine)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return Response(audio, media_type="audio/wav")


@app.post("/speak")
def speak(req: TTSRequest):
    """Texto -> audio WAV en base64 más los visemas con tiempos para animar al avatar."""
    try:
        audio = voice.synthesize(req.text, req.language, req.voice, req.engine)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"audio": base64.b64encode(audio).decode("ascii"), **lipsync.visemes(audio, req.language)}


@app.get("/voices")
def voices(language: str | None = None, engine: str = "piper"):
    try:
        return voice.list_voices(language, engine)
    except ValueError as e:
        raise HTTPException(404, str(e))


class WarmupRequest(BaseModel):
    language: str = "es"
    voice: str | None = None
    engine: str = "piper"


@app.post("/warmup")
def warmup(req: WarmupRequest):
    """Carga los modelos en memoria para que la primera respuesta no tarde."""
    rag.warmup()
    voice.transcribe(voice.synthesize("Hola.", req.language))  # carga Whisper
    try:
        voice.synthesize("Hola.", req.language, req.voice, req.engine)  # carga el motor de voz
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True}


# ---------- Administración ----------

@app.post("/reindex")
def reindex():
    """Vuelve a procesar todo data/docs (lo usará la consola de administración)."""
    return ingest_all()


@app.get("/health")
def health():
    return {"llm": config.LLM_MODEL, "embeddings": config.EMBED_MODEL, "chunks": collection().count()}


# ---------- Página del avatar ----------

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/avatar/")


app.mount("/avatar", StaticFiles(directory=config.WEB_DIR, html=True), name="avatar")
