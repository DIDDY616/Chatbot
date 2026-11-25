"""Preguntas frecuentes: se guardan en data/faqs.json y cada una se indexa como un fragmento."""
import json
import threading
import uuid

from pydantic import BaseModel, Field

from . import config
from .store import collection, embed

_lock = threading.Lock()


class Faq(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    category: str = "general"
    published: bool = True  # las anteriores a los borradores ya estaban a la vista


def load() -> dict[str, Faq]:
    if not config.FAQS_FILE.exists():
        return {}
    raw = json.loads(config.FAQS_FILE.read_text(encoding="utf-8") or "{}")
    return {key: Faq(**value) for key, value in raw.items()}


def _write(faqs: dict[str, Faq]) -> None:
    config.FAQS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {key: value.model_dump() for key, value in faqs.items()}
    config.FAQS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _index(faq_id: str, faq: Faq) -> None:
    text = f"Pregunta frecuente: {faq.question}\nRespuesta: {faq.answer}"
    collection().upsert(
        ids=[f"faq#{faq_id}"],
        documents=[text],
        embeddings=embed([text]),
        metadatas=[{"source": f"FAQ: {faq.question[:80]}", "category": faq.category,
                    "faq_id": faq_id, "published": faq.published}],
    )


def save(faq: Faq, faq_id: str | None = None) -> str:
    """Crea o actualiza una pregunta frecuente y la indexa."""
    faq_id = faq_id or uuid.uuid4().hex[:10]
    _index(faq_id, faq)  # primero el índice: si el modelo falla no queda guardada a medias
    with _lock:
        faqs = load()
        faqs[faq_id] = faq
        _write(faqs)
    return faq_id


def set_published(faq_id: str, published: bool) -> None:
    with _lock:
        faqs = load()
        if faq_id not in faqs:
            raise KeyError(faq_id)
        faqs[faq_id].published = published
        _write(faqs)
    found = collection().get(ids=[f"faq#{faq_id}"], include=["metadatas"])
    if found["ids"]:
        collection().update(ids=found["ids"], metadatas=[{**found["metadatas"][0], "published": published}])


def delete(faq_id: str) -> None:
    with _lock:
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
