"""Borradores y publicación de la base de conocimiento.

Un documento recién subido queda en borrador: se puede probar en la consola, pero los
estudiantes no lo ven hasta que alguien lo publica. Las preguntas frecuentes guardan su
estado en data/faqs.json; los documentos, en data/publicacion.json.

Los documentos que no aparecen en data/publicacion.json se consideran publicados, así que
una base creada antes de esta función sigue funcionando igual.

El estado también se copia a los metadatos de cada fragmento ("published"), para que el
filtro se aplique en la búsqueda y un borrador nunca llegue al modelo.
"""
import json
import threading

from . import config
from .store import collection

_lock = threading.Lock()


def _load() -> dict[str, bool]:
    if not config.PUBLICATION_FILE.exists():
        return {}
    return json.loads(config.PUBLICATION_FILE.read_text(encoding="utf-8")).get("documents", {})


def _write(states: dict[str, bool]) -> None:
    config.PUBLICATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {"documents": dict(sorted(states.items()))}
    config.PUBLICATION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_published(source: str) -> bool:
    return _load().get(source, True)


def states() -> dict[str, bool]:
    return _load()


def set_document(source: str, published: bool) -> int:
    """Publica o pasa a borrador un documento. Devuelve cuántos fragmentos cambió."""
    with _lock:
        current = _load()
        current[source] = published
        _write(current)
    return _mark(collection().get(where={"source": source}, include=["metadatas"]), published)


def forget(source: str) -> None:
    """Quita el registro de un documento borrado."""
    with _lock:
        current = _load()
        if current.pop(source, None) is not None:
            _write(current)


def _mark(found: dict, published: bool) -> int:
    ids = [i for i, meta in zip(found["ids"], found["metadatas"]) if meta.get("published") != published]
    if ids:
        metas = {i: meta for i, meta in zip(found["ids"], found["metadatas"])}
        collection().update(ids=ids, metadatas=[{**metas[i], "published": published} for i in ids])
    return len(ids)


def visible_to_students(where: dict | None) -> dict:
    """Agrega al filtro de búsqueda la condición de estar publicado."""
    published = {"published": True}
    return published if where is None else {"$and": [where, published]}


def sync_index() -> int:
    """Copia a los fragmentos el estado de publicación guardado. Devuelve cuántos corrigió.

    Sirve para índices creados antes de que existieran los borradores (sin el metadato) y
    para cuando alguien edita data/publicacion.json o data/faqs.json a mano.
    """
    from . import faqs

    documents = _load()
    faq_states = {faq_id: faq.published for faq_id, faq in faqs.load().items()}
    found = collection().get(include=["metadatas"])
    fixes: dict[str, dict] = {}
    for chunk_id, meta in zip(found["ids"], found["metadatas"]):
        if "faq_id" in meta:
            wanted = faq_states.get(meta["faq_id"], True)
        else:
            wanted = documents.get(meta.get("source", ""), True)
        if meta.get("published") != wanted:
            fixes[chunk_id] = {**meta, "published": wanted}
    if fixes:
        collection().update(ids=list(fixes), metadatas=list(fixes.values()))
    return len(fixes)
