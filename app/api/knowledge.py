"""Administración de la base de conocimiento: documentos, preguntas frecuentes y publicación."""
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .. import documents, faqs, publication
from ..ingest import ingest_all
from .security import require_admin

router = APIRouter(tags=["base de conocimiento"], dependencies=[Depends(require_admin)])


@router.get("/documents")
def list_documents():
    return documents.list_documents()


@router.post("/documents")
def upload_document(file: UploadFile, category: str = Form("general"), publish: bool = Form(False)):
    """Guarda el archivo en data/docs/<categoría>/ y lo indexa. Sin `publish` queda en borrador."""
    try:
        return documents.save(file.filename or "", category, file.file.read(), publish)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/documents")
def delete_document(source: str):
    try:
        documents.delete(source)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return {"ok": True}


@router.get("/documents/chunks")
def document_chunks(source: str):
    try:
        return documents.chunks(source)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


class PublishRequest(BaseModel):
    published: bool = True


@router.put("/documents/publish")
def publish_document(source: str, req: PublishRequest):
    try:
        return {"changed": documents.publish(source, req.published)}
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/faqs")
def list_faqs() -> dict[str, faqs.Faq]:
    return faqs.load()


@router.post("/faqs")
def create_faq(faq: faqs.Faq):
    return {"id": faqs.save(faq)}


@router.put("/faqs/{faq_id}")
def update_faq(faq_id: str, faq: faqs.Faq):
    if faq_id not in faqs.load():
        raise HTTPException(404, "Pregunta frecuente no encontrada")
    faqs.save(faq, faq_id)
    return {"ok": True}


@router.put("/faqs/{faq_id}/publish")
def publish_faq(faq_id: str, req: PublishRequest):
    try:
        faqs.set_published(faq_id, req.published)
    except KeyError as e:
        raise HTTPException(404, "Pregunta frecuente no encontrada") from e
    return {"ok": True}


@router.delete("/faqs/{faq_id}")
def delete_faq(faq_id: str):
    faqs.delete(faq_id)
    return {"ok": True}


@router.post("/publish-all")
def publish_all():
    """Publica todos los borradores (documentos y preguntas frecuentes)."""
    count = 0
    for doc in documents.list_documents():
        if not doc["published"]:
            documents.publish(doc["source"])
            count += 1
    for faq_id, faq in faqs.load().items():
        if not faq.published:
            faqs.set_published(faq_id, True)
            count += 1
    return {"published": count}


@router.get("/categories")
def categories() -> list[str]:
    """Categorías en uso por documentos y preguntas frecuentes."""
    found = {d["category"] for d in documents.list_documents()} | {f.category for f in faqs.load().values()}
    return sorted(found | {"general"})


@router.post("/reindex")
def reindex():
    """Vuelve a procesar todo data/docs y las preguntas frecuentes."""
    result = ingest_all()
    publication.sync_index()
    return result
