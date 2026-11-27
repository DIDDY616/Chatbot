"""Documentos, preguntas frecuentes y publicación contra un Chroma real en carpeta temporal."""
import pytest

from app import config, documents, faqs, publication, store
from app.ingest import ingest_all
from tests.unit.conftest import write_doc


def metas(where):
    return store.collection().get(where=where, include=["metadatas"])["metadatas"]


def test_subir_queda_en_borrador_y_se_publica(env):
    saved = documents.save("plan.md", "ITC", b"El plan dura 8 semestres.")
    assert saved == {"source": "ITC/plan.md", "chunks": 1, "published": False}
    [doc] = documents.list_documents()
    assert doc["published"] is False and doc["chunks"] == 1
    assert all(m["published"] is False for m in metas({"source": "ITC/plan.md"}))

    assert documents.publish("ITC/plan.md") == 1
    assert documents.list_documents()[0]["published"] is True
    assert all(m["published"] is True for m in metas({"source": "ITC/plan.md"}))


def test_reemplazo_fallido_conserva_la_version_anterior(env, monkeypatch):
    documents.save("plan.md", "ITC", b"Version uno.", publish=True)

    def broken(_texts):
        raise RuntimeError("Ollama apagado")

    monkeypatch.setattr("app.ingest.embed", broken)
    with pytest.raises(ValueError, match="No se pudo leer"):
        documents.save("plan.md", "ITC", b"Version dos.", publish=False)
    assert (config.DOCS_DIR / "ITC" / "plan.md").read_bytes() == b"Version uno."
    assert documents.chunks("ITC/plan.md") == ["Version uno."]
    assert documents.list_documents()[0]["published"] is True


def test_archivo_nuevo_que_falla_no_deja_rastro(env, monkeypatch):
    monkeypatch.setattr("app.ingest.embed", lambda _t: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(ValueError):
        documents.save("nuevo.md", "general", b"Texto.")
    assert documents.list_documents() == []
    assert publication.states() == {}


def test_nombres_peligrosos(env):
    saved = documents.save("../../fuera.md", "general", b"hola")  # la ruta se descarta, queda el nombre
    assert saved["source"] == "general/fuera.md"
    assert (config.DOCS_DIR / saved["source"]).resolve().is_relative_to(config.DOCS_DIR.resolve())
    with pytest.raises(ValueError):
        documents.save("a.md", "../..", b"hola")  # una categoría que solo es ruta no vale
    with pytest.raises(ValueError):
        documents.save("virus.exe", "general", b"MZ")
    with pytest.raises(ValueError):
        documents.chunks("../../perfiles.json")


def test_limite_de_tamano(env, monkeypatch):
    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 0)
    with pytest.raises(ValueError, match="MB"):
        documents.save("grande.md", "general", b"x")


def test_borrar_quita_archivo_indice_y_estado(env):
    documents.save("plan.md", "ITC", b"Texto.")
    documents.delete("ITC/plan.md")
    assert documents.list_documents() == []
    assert metas({"source": "ITC/plan.md"}) == []
    assert publication.states() == {}
    assert not (config.DOCS_DIR / "ITC").exists()


def test_reindexar_quita_documentos_borrados_a_mano(env):
    path = write_doc("general", "viejo.md", "Dato viejo.")
    ingest_all()
    path.unlink()
    ingest_all()
    assert metas({"source": "general/viejo.md"}) == []


def test_faq_borrador_publicar_y_borrar(env):
    faq_id = faqs.save(faqs.Faq(question="¿Hay estacionamiento?", answer="Sí, en el sótano.", published=False))
    [meta] = metas({"faq_id": faq_id})
    assert meta["published"] is False and meta["category"] == "general"
    faqs.set_published(faq_id, True)
    assert metas({"faq_id": faq_id})[0]["published"] is True
    assert faqs.load()[faq_id].published is True
    faqs.delete(faq_id)
    assert metas({"faq_id": faq_id}) == [] and faqs.load() == {}


def test_faq_sin_texto_no_es_valida():
    with pytest.raises(ValueError):
        faqs.Faq(question="", answer="x")


def test_sync_index_migra_indices_viejos(env):
    """Un índice creado antes de los borradores no tiene el metadato "published"."""
    write_doc("general", "viejo.md", "Dato.")
    ingest_all()
    # Chroma no borra claves con update (las combina), así que se recrean los fragmentos sin ella.
    col = store.collection()
    found = col.get(include=["metadatas", "documents", "embeddings"])
    col.delete(ids=found["ids"])
    col.add(ids=found["ids"], documents=found["documents"], embeddings=found["embeddings"],
            metadatas=[{k: v for k, v in m.items() if k != "published"} for m in found["metadatas"]])
    assert "published" not in metas({"source": "general/viejo.md"})[0]
    assert publication.sync_index() == 1
    assert metas({"source": "general/viejo.md"})[0]["published"] is True


def test_update_combina_metadatos(env):
    """Comportamiento de Chroma del que depende publication.py: update agrega o cambia claves, no borra."""
    write_doc("general", "a.md", "Dato.")
    ingest_all()
    col = store.collection()
    [chunk_id] = col.get(include=[])["ids"]
    col.update(ids=[chunk_id], metadatas=[{"published": False}])
    meta = col.get(ids=[chunk_id], include=["metadatas"])["metadatas"][0]
    assert meta == {"source": "general/a.md", "category": "general", "published": False}


def test_filtro_para_estudiantes():
    assert publication.visible_to_students(None) == {"published": True}
    access = {"category": {"$in": ["ITC"]}}
    assert publication.visible_to_students(access) == {"$and": [access, {"published": True}]}
