"""Ingesta: lee los documentos de data/docs, los parte en fragmentos y los indexa.

Uso:  python -m app.ingest
La primera subcarpeta dentro de data/docs se usa como categoría (p. ej. data/docs/ITC/plan.pdf).
"""
import re
from pathlib import Path

from . import config, faqs
from .store import collection, embed

SUPPORTED = {".txt", ".md", ".pdf", ".docx", ".xlsx"}


def read_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        from pypdf import PdfReader

        return "\n\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    if suffix == ".docx":
        import docx

        doc = docx.Document(str(path))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text.strip() for cell in row.cells))
        return "\n\n".join(parts)
    if suffix == ".xlsx":
        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True, data_only=True)
        try:
            parts = []
            for ws in wb.worksheets:
                rows = [
                    " | ".join(str(c) for c in row if c is not None)
                    for row in ws.iter_rows(values_only=True)
                ]
                parts.append(f"Hoja: {ws.title}\n" + "\n".join(r for r in rows if r))
            return "\n\n".join(parts)
        finally:
            wb.close()  # en modo de solo lectura el archivo queda abierto y Windows no deja borrarlo
    raise ValueError(f"Formato no soportado: {path.name}")


def chunk(text: str, size: int = config.CHUNK_SIZE, overlap: int = config.CHUNK_OVERLAP) -> list[str]:
    """Agrupa párrafos hasta ~size caracteres, con un traslape entre fragmentos."""
    pieces = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        while len(para) > size:
            pieces.append(para[:size])
            para = para[size - overlap:]
        if para:
            pieces.append(para)

    chunks, current = [], ""
    for piece in pieces:
        if current and len(current) + len(piece) + 2 > size:
            chunks.append(current)
            current = current[-overlap:] + "\n\n" + piece
        else:
            current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks


def ingest_file(path: Path) -> int:
    """Indexa (o reindexa) un archivo. Devuelve el número de fragmentos."""
    rel = path.relative_to(config.DOCS_DIR).as_posix()
    category = rel.split("/")[0] if "/" in rel else "general"
    col = collection()
    col.delete(where={"source": rel})
    chunks = chunk(read_file(path))
    if not chunks:
        return 0
    col.add(
        ids=[f"{rel}#{i}" for i in range(len(chunks))],
        documents=chunks,
        embeddings=embed(chunks),
        metadatas=[{"source": rel, "category": category} for _ in chunks],
    )
    return len(chunks)


def ingest_all() -> dict[str, int]:
    """Reindexa data/docs y las preguntas frecuentes; quita del índice los archivos que ya no existen."""
    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    files = [p for p in config.DOCS_DIR.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED]
    result = {p.relative_to(config.DOCS_DIR).as_posix(): ingest_file(p) for p in files}

    col = collection()
    indexed = {m["source"] for m in col.get(include=["metadatas"])["metadatas"] if "faq_id" not in m}
    for gone in indexed - result.keys():
        col.delete(where={"source": gone})
    faqs.index_all()
    return result


if __name__ == "__main__":
    for source, n in ingest_all().items():
        print(f"{n:4d} fragmentos  {source}")
