"""Acceso al almacén de vectores y al modelo de embeddings.

Dos almacenes posibles (VECTOR_STORE en .env):
- "local" (por omisión): app/vectorstore.py, un archivo en data/vectores con búsqueda en numpy.
  Sin código nativo propio, así que no tiene el fallo de Chroma en Windows.
- "chroma": Chroma en data/chroma, para bases de conocimiento muy grandes.

Todo se crea la primera vez que se usa: importar este módulo no abre el almacén ni se conecta
a Ollama, lo que permite probar el resto del código sin los modelos.
"""
import threading

from . import config

COLLECTION = "conocimiento"

_embed_client = None
_chroma = None
_local = None
_lock = threading.Lock()


def _client():
    global _embed_client
    if _embed_client is None:
        from openai import OpenAI

        _embed_client = OpenAI(base_url=config.EMBED_BASE_URL, api_key=config.EMBED_API_KEY)
    return _embed_client


def embed(texts: list[str]) -> list[list[float]]:
    """Un vector por texto. Se manda en tandas para no saturar al servidor con documentos largos."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), config.EMBED_BATCH):
        batch = texts[start:start + config.EMBED_BATCH]
        resp = _client().embeddings.create(model=config.EMBED_MODEL, input=batch)
        vectors += [d.embedding for d in sorted(resp.data, key=lambda d: getattr(d, "index", 0))]
    return vectors


def collection():
    global _chroma, _local
    with _lock:
        if config.VECTOR_STORE == "chroma":
            if _chroma is None:
                import chromadb

                _chroma = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
            return _chroma.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
        if _local is None:
            from .vectorstore import LocalCollection

            _local = LocalCollection(config.VECTORS_DIR)
        return _local


def reset() -> None:
    """Olvida las conexiones (la siguiente llamada abre de nuevo el almacén configurado). Para pruebas."""
    global _chroma, _local, _embed_client
    with _lock:
        _chroma = None
        _local = None
        _embed_client = None
