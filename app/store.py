"""Acceso a la base vectorial (Chroma) y al modelo de embeddings."""
import chromadb
from openai import OpenAI

from . import config

_embed_client = OpenAI(base_url=config.EMBED_BASE_URL, api_key=config.EMBED_API_KEY)
_chroma = None


def embed(texts: list[str]) -> list[list[float]]:
    resp = _embed_client.embeddings.create(model=config.EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def collection():
    global _chroma
    if _chroma is None:
        _chroma = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return _chroma.get_or_create_collection(
        "conocimiento", metadata={"hnsw:space": "cosine"}
    )
