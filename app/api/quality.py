"""Pruebas antes de publicar, evaluación, historial y estadísticas (consola)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from .. import evaluation, history, profiles, rag
from .conversation import Feedback
from .security import require_admin

router = APIRouter(tags=["calidad"], dependencies=[Depends(require_admin)])


class TestRequest(BaseModel):
    message: str
    language: str = "es"
    profile: str = profiles.DEFAULT_PROFILE
    include_drafts: bool = True


@router.post("/test")
def test_question(req: TestRequest):
    """Responde una pregunta suelta sin registrarla y devuelve también los fragmentos usados.

    Por omisión incluye los borradores: es la forma de probar un cambio antes de publicarlo.
    """
    session = f"test-{uuid.uuid4().hex}"
    try:
        return rag.answer(session, req.message, req.language, req.profile, log=False,
                          include_drafts=req.include_drafts)
    except KeyError as e:
        raise HTTPException(404, e.args[0]) from e
    finally:
        rag.reset(session)


@router.post("/eval")
def run_evaluation(include_drafts: bool = False):
    """Corre las preguntas de tests/preguntas.jsonl y dice cuáles pasan."""
    return evaluation.run(include_drafts)


@router.get("/history")
def list_history(limit: int = Query(200, ge=1, le=5000), unanswered: bool = False):
    items = history.entries()
    if unanswered:
        items = [e for e in items if not e["answered"]]
    return items[:limit]


@router.get("/history.csv")
def export_history():
    return Response(history.to_csv(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="historial.csv"'})


@router.put("/history/{entry_id}/feedback")
def rate_answer(entry_id: str, feedback: Feedback):
    history.set_feedback(entry_id, feedback.rating)
    return {"ok": True}


@router.get("/stats")
def stats():
    return history.stats()
