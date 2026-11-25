"""Acceso a la base vectorial (Chroma) y al modelo de embeddings.

Todo se crea la primera vez que se usa: importar este módulo no abre la base ni se conecta
a Ollama, lo que permite probar el resto del código sin los modelos.
"""
import threading

from . import config

COLLECTION = "conocimiento"

_embed_client = None
_chroma = None
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
    global _chroma
    with _lock:
        if _chroma is None:
            import chromadb

            _chroma = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        client = _chroma
    return client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})


def reset() -> None:
    """Olvida la conexión (la siguiente llamada abre config.CHROMA_DIR de nuevo). Para pruebas."""
    global _chroma, _embed_client
    with _lock:
        _chroma = None
        _embed_client = None
