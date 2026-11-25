"""Conversación: lo que usan la página del avatar y la reunión de Teams."""
import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .. import history, profiles, rag

router = APIRouter(tags=["conversación"])


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=4000)
    language: str = "es"
    profile: str = profiles.DEFAULT_PROFILE


class ChatResponse(BaseModel):
    id: str | None = None
    answer: str
    answered: bool
    sources: list[str]
    intent: str = "consulta"


def _check_profile(profile_id: str) -> None:
    try:
        profiles.get(profile_id)
    except KeyError as e:
        raise HTTPException(404, e.args[0]) from e


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    _check_profile(req.profile)
    return rag.answer(req.session_id, req.message, req.language, req.profile)


@router.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """Igual que /chat pero por partes (una línea JSON por evento), para hablar sin esperar el final."""
    _check_profile(req.profile)
    events = rag.answer_stream(req.session_id, req.message, req.language, req.profile)

    def lines():
        for event in events:
            if event["type"] == "done":  # la página no necesita los fragmentos completos
                event = {k: v for k, v in event.items() if k != "chunks"}
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(lines(), media_type="application/x-ndjson")


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    rag.reset(session_id)
    return {"ok": True}


class Feedback(BaseModel):
    rating: Literal["good", "bad"] | None = None


@router.put("/feedback/{entry_id}")
def student_feedback(entry_id: str, feedback: Feedback):
    """Valoración de una respuesta desde la página del avatar (👍 / 👎)."""
    if not history.exists(entry_id):
        raise HTTPException(404, "No existe esa respuesta en el historial")
    history.set_feedback(entry_id, feedback.rating)
    return {"ok": True}
