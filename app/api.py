"""API del asistente.  Uso:  uvicorn app.api:app --port 8000"""
from fastapi import FastAPI, HTTPException, Response, UploadFile
from pydantic import BaseModel

from . import config, rag, voice
from .ingest import ingest_all
from .store import collection

app = FastAPI(title="Asistente Tec")


class ChatRequest(BaseModel):
    session_id: str
    message: str
    language: str = "es"


class ChatResponse(BaseModel):
    answer: str
    answered: bool
    sources: list[str]


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    return rag.answer(req.session_id, req.message, req.language)


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    rag.reset(session_id)
    return {"ok": True}


class TTSRequest(BaseModel):
    text: str
    language: str = "es"
    voice: str | None = None


@app.post("/stt")
def stt(audio: UploadFile, language: str | None = None):
    """Audio -> texto. `language` es opcional (es, en, fr, sv, de); sin él se detecta."""
    return voice.transcribe(audio.file.read(), language)


@app.post("/tts")
def tts(req: TTSRequest):
    """Texto -> audio WAV."""
    try:
        return Response(voice.synthesize(req.text, req.language, req.voice), media_type="audio/wav")
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/voices")
def voices(language: str | None = None):
    return voice.list_voices(language)


@app.post("/reindex")
def reindex():
    """Vuelve a procesar todo data/docs (lo usará la consola de administración)."""
    return ingest_all()


@app.get("/health")
def health():
    return {"llm": config.LLM_MODEL, "embeddings": config.EMBED_MODEL, "chunks": collection().count()}
