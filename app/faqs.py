"""Preguntas frecuentes: se guardan en data/faqs.json y cada una se indexa como un fragmento."""
import json
import uuid

from pydantic import BaseModel

from . import config
from .store import collection, embed


class Faq(BaseModel):
    question: str
    answer: str
    category: str = "general"


def load() -> dict[str, Faq]:
    if not config.FAQS_FILE.exists():
        return {}
    raw = json.loads(config.FAQS_FILE.read_text(encoding="utf-8"))
    return {key: Faq(**value) for key, value in raw.items()}


def _write(faqs: dict[str, Faq]) -> None:
    data = {key: value.model_dump() for key, value in faqs.items()}
    config.FAQS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _index(faq_id: str, faq: Faq) -> None:
    text = f"Pregunta frecuente: {faq.question}\nRespuesta: {faq.answer}"
    collection().upsert(
        ids=[f"faq#{faq_id}"],
        documents=[text],
        embeddings=embed([text]),
        metadatas=[{"source": f"FAQ: {faq.question[:80]}", "category": faq.category, "faq_id": faq_id}],
    )


def save(faq: Faq, faq_id: str | None = None) -> str:
    """Crea o actualiza una pregunta frecuente y la deja disponible para el asistente."""
    faqs = load()
    faq_id = faq_id or uuid.uuid4().hex[:10]
    faqs[faq_id] = faq
    _write(faqs)
    _index(faq_id, faq)
    return faq_id


def delete(faq_id: str) -> None:
    faqs = load()
    if faqs.pop(faq_id, None) is not None:
        _write(faqs)
    collection().delete(ids=[f"faq#{faq_id}"])


def index_all() -> int:
    """Vuelve a indexar todas las preguntas frecuentes y quita del índice las que ya no existen."""
    faqs = load()
    col = collection()
    indexed = [i for i in col.get(include=[])["ids"] if i.startswith("faq#")]
    stale = [i for i in indexed if i.removeprefix("faq#") not in faqs]
    if stale:
        col.delete(ids=stale)
    for faq_id, faq in faqs.items():
        _index(faq_id, faq)
    return len(faqs)
