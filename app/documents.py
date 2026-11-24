"""Gestión de documentos de la base de conocimiento (para la consola de administración)."""
import re
from collections import Counter
from pathlib import Path

from . import config
from .ingest import SUPPORTED, ingest_file
from .store import collection


def _clean(name: str) -> str:
    """Nombre seguro para archivo o carpeta: sin rutas ni caracteres que Windows rechaza."""
    name = re.sub(r'[\\/:*?"<>|]+', " ", Path(name).name).strip(" .")
    if not name:
        raise ValueError("Nombre vacío o no válido")
    return name


def _path(source: str) -> Path:
    """Ruta de un documento ya existente, comprobando que esté dentro de data/docs."""
    path = (config.DOCS_DIR / source).resolve()
    if not path.is_relative_to(config.DOCS_DIR.resolve()) or not path.is_file():
        raise ValueError(f"Documento no encontrado: '{source}'")
    return path


def list_documents() -> list[dict]:
    """Documentos en data/docs con su categoría, tamaño y número de fragmentos indexados."""
    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    counts = Counter(m["source"] for m in collection().get(include=["metadatas"])["metadatas"])
    documents = []
    for path in sorted(config.DOCS_DIR.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED:
            source = path.relative_to(config.DOCS_DIR).as_posix()
            documents.append({
                "source": source,
                "name": path.name,
                "category": source.split("/")[0] if "/" in source else "general",
                "kilobytes": round(path.stat().st_size / 1024, 1),
                "chunks": counts.get(source, 0),
            })
    return documents


def save(filename: str, category: str, content: bytes) -> dict:
    """Guarda un archivo subido en data/docs/<categoría>/ y lo indexa."""
    filename, category = _clean(filename), _clean(category or "general")
    if Path(filename).suffix.lower() not in SUPPORTED:
        raise ValueError(f"Formato no soportado. Usa: {', '.join(sorted(SUPPORTED))}")
    path = config.DOCS_DIR / category / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    try:
        chunks = ingest_file(path)
    except Exception as error:
        path.unlink()
        raise ValueError(f"No se pudo leer el archivo: {error}") from error
    return {"source": path.relative_to(config.DOCS_DIR).as_posix(), "chunks": chunks}


def delete(source: str) -> None:
    path = _path(source)
    try:
        path.unlink()
    except PermissionError as error:
        raise ValueError(f"No se pudo borrar '{source}': el archivo está en uso") from error
    collection().delete(where={"source": source})
    if path.parent != config.DOCS_DIR and not any(path.parent.iterdir()):
        path.parent.rmdir()


def chunks(source: str) -> list[str]:
    """Fragmentos indexados de un documento, en orden."""
    _path(source)
    found = collection().get(where={"source": source}, include=["documents"])
    ordered = sorted(zip(found["ids"], found["documents"]), key=lambda pair: int(pair[0].rsplit("#", 1)[1]))
    return [text for _, text in ordered]
