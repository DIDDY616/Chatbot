"""Gestión de documentos de la base de conocimiento (para la consola de administración)."""
import re
import unicodedata
from collections import Counter
from pathlib import Path

from . import config, publication
from .ingest import SUPPORTED, ingest_file, source_of
from .store import collection


def clean_name(name: str) -> str:
    """Nombre seguro para archivo o carpeta: sin rutas ni caracteres que Windows rechaza."""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", Path(name).name).strip(" .")
    if not name or name in (".", ".."):
        raise ValueError("Nombre vacío o no válido")
    return name


def slugify(text: str, default: str = "documento", limit: int = 80) -> str:
    """Texto para nombre de archivo o identificador: "Ingeniería en TC" -> "ingenieria-en-tc"."""
    plain = "".join(c for c in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:limit].strip("-") or default


def _path(source: str) -> Path:
    """Ruta de un documento ya existente, comprobando que esté dentro de data/docs."""
    path = (config.DOCS_DIR / source).resolve()
    if not path.is_relative_to(config.DOCS_DIR.resolve()) or not path.is_file():
        raise ValueError(f"Documento no encontrado: '{source}'")
    return path


def list_documents() -> list[dict]:
    """Documentos en data/docs con su categoría, tamaño, fragmentos indexados y estado."""
    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    counts = Counter(m["source"] for m in collection().get(include=["metadatas"])["metadatas"])
    states = publication.states()
    documents = []
    for path in sorted(config.DOCS_DIR.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED:
            source, category = source_of(path)
            documents.append({
                "source": source,
                "name": path.name,
                "category": category,
                "kilobytes": round(path.stat().st_size / 1024, 1),
                "chunks": counts.get(source, 0),
                "published": states.get(source, True),
            })
    return documents


def save(filename: str, category: str, content: bytes, publish: bool = False) -> dict:
    """Guarda un archivo subido en data/docs/<categoría>/ y lo indexa.

    Sin `publish` queda en borrador. Si ya existía un archivo con ese nombre y el nuevo no se
    puede leer, se restaura el anterior.
    """
    filename, category = clean_name(filename), clean_name(category or "general")
    if Path(filename).suffix.lower() not in SUPPORTED:
        raise ValueError(f"Formato no soportado. Usa: {', '.join(sorted(SUPPORTED))}")
    if len(content) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(f"El archivo pasa de {config.MAX_UPLOAD_MB} MB")
    path = config.DOCS_DIR / category / filename
    source = path.relative_to(config.DOCS_DIR).as_posix()
    previous = path.read_bytes() if path.exists() else None
    was_published = publication.is_published(source)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    publication.set_document(source, publish)
    try:
        chunks = ingest_file(path)
    except Exception as error:
        if previous is None:
            path.unlink()
            publication.forget(source)
        else:
            path.write_bytes(previous)
            publication.set_document(source, was_published)
        raise ValueError(f"No se pudo leer el archivo: {error}") from error
    return {"source": source, "chunks": chunks, "published": publish}


def publish(source: str, published: bool = True) -> int:
    _path(source)
    return publication.set_document(source, published)


def delete(source: str) -> None:
    path = _path(source)
    try:
        path.unlink()
    except PermissionError as error:
        raise ValueError(f"No se pudo borrar '{source}': el archivo está en uso") from error
    collection().delete(where={"source": source})
    publication.forget(source)
    if path.parent != config.DOCS_DIR and not any(path.parent.iterdir()):
        path.parent.rmdir()


def chunks(source: str) -> list[str]:
    """Fragmentos indexados de un documento, en orden."""
    _path(source)
    found = collection().get(where={"source": source}, include=["documents"])
    ordered = sorted(zip(found["ids"], found["documents"]), key=lambda pair: int(pair[0].rsplit("#", 1)[1]))
    return [text for _, text in ordered]
