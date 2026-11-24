"""API del asistente.  Uso:  uvicorn app.api:app --port 8000

La página del avatar queda en http://localhost:8000/avatar/
"""
import base64
import json
import mimetypes
import uuid
from typing import Literal

import openai
from fastapi import FastAPI, Form, HTTPException, Response, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, documents, evaluation, faqs, history, lipsync, profiles, rag, voice, wake
from .ingest import ingest_all
from .store import collection

# En Windows el registro puede asignar tipos incorrectos y el navegador rechaza los módulos JS.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("model/gltf-binary", ".glb")

app = FastAPI(title="Asistente Tec")


@app.exception_handler(openai.APIConnectionError)
def llm_unreachable(request, error):
    """Ollama apagado: se responde con un mensaje claro en vez de un error interno."""
    return JSONResponse({"detail": "No se pudo conectar con Ollama. Abre la aplicación de Ollama e inténtalo de nuevo."}, 503)


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
    if len(profiles.load()) <= 1:
        raise HTTPException(400, "Debe quedar al menos un asistente")
    profiles.delete(profile_id)
    return {"ok": True}


# ---------- Voz ----------

class TTSRequest(BaseModel):
    text: str
    language: str = "es"
    voice: str | None = None
    engine: str = "piper"  # "piper" (rápido) o "chatterbox" (natural)


@app.post("/stt")
def stt(audio: UploadFile, language: str | None = None, wake_profile: str | None = None):
    """Audio -> texto. `language` es opcional (es, en, fr, sv, de); sin él se detecta.

    Con `wake_profile` (modo reunión) dice además si la frase nombra a ese asistente
    (`addressed`) y cuál es la pregunta sin el nombre (`question`).
    """
    if wake_profile is None:
        return voice.transcribe(audio.file.read(), language)
    try:
        names = profiles.get(wake_profile).wake_names()
    except KeyError as e:
        raise HTTPException(404, str(e))
    return wake.hear(audio.file.read(), language, names)


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


# ---------- Administración: base de conocimiento ----------

@app.get("/documents")
def list_documents():
    return documents.list_documents()


@app.post("/documents")
def upload_document(file: UploadFile, category: str = Form("general")):
    """Guarda el archivo en data/docs/<categoría>/ y lo indexa."""
    try:
        return documents.save(file.filename or "", category, file.file.read())
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/documents")
def delete_document(source: str):
    try:
        documents.delete(source)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True}


@app.get("/documents/chunks")
def document_chunks(source: str):
    try:
        return documents.chunks(source)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/faqs")
def list_faqs() -> dict[str, faqs.Faq]:
    return faqs.load()


@app.post("/faqs")
def create_faq(faq: faqs.Faq):
    return {"id": faqs.save(faq)}


@app.put("/faqs/{faq_id}")
def update_faq(faq_id: str, faq: faqs.Faq):
    if faq_id not in faqs.load():
        raise HTTPException(404, "Pregunta frecuente no encontrada")
    faqs.save(faq, faq_id)
    return {"ok": True}


@app.delete("/faqs/{faq_id}")
def delete_faq(faq_id: str):
    faqs.delete(faq_id)
    return {"ok": True}


@app.get("/categories")
def categories() -> list[str]:
    """Categorías en uso por documentos y preguntas frecuentes."""
    found = {d["category"] for d in documents.list_documents()} | {f.category for f in faqs.load().values()}
    return sorted(found | {"general"})


@app.post("/reindex")
def reindex():
    """Vuelve a procesar todo data/docs y las preguntas frecuentes."""
    return ingest_all()


# ---------- Administración: pruebas, historial y estadísticas ----------

class TestRequest(BaseModel):
    message: str
    language: str = "es"
    profile: str = profiles.DEFAULT_PROFILE


@app.post("/test")
def test_question(req: TestRequest):
    """Responde una pregunta suelta sin registrarla y devuelve también los fragmentos usados."""
    session = f"test-{uuid.uuid4().hex}"
    try:
        return rag.answer(session, req.message, req.language, req.profile, log=False)
    except KeyError as e:
        raise HTTPException(404, e.args[0])
    finally:
        rag.reset(session)


@app.post("/eval")
def run_evaluation():
    """Corre las preguntas de tests/preguntas.jsonl y dice cuáles pasan."""
    return evaluation.run()


@app.get("/history")
def list_history(limit: int = 200, unanswered: bool = False):
    items = history.entries()
    if unanswered:
        items = [e for e in items if not e["answered"]]
    return items[:limit]


class Feedback(BaseModel):
    rating: Literal["good", "bad"] | None = None


@app.put("/history/{entry_id}/feedback")
def rate_answer(entry_id: str, feedback: Feedback):
    history.set_feedback(entry_id, feedback.rating)
    return {"ok": True}


@app.get("/stats")
def stats():
    return history.stats()


@app.get("/health")
def health():
    return {"llm": config.LLM_MODEL, "embeddings": config.EMBED_MODEL, "chunks": collection().count()}


# ---------- Página del avatar ----------

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/avatar/")


app.mount("/avatar", StaticFiles(directory=config.WEB_DIR, html=True), name="avatar")
