"""Almacén de vectores propio: un archivo en disco y búsqueda con numpy.

Por qué existe: Chroma (la base vectorial que se usaba) se cae en algunas computadoras con
Windows al guardar el primer fragmento ("access violation" en su núcleo en Rust; ver
https://github.com/chroma-core/chroma/issues/5392 y #6052, sin solución). Este proyecto se usa
sobre todo en Windows, así que el almacén por omisión es este, que no tiene código nativo propio.

Para el tamaño de una base de conocimiento de un MVP (cientos o pocos miles de fragmentos) una
búsqueda exhaustiva con numpy tarda milisegundos. Imita la parte de la API de Chroma que usa el
proyecto, con sus mismas reglas: un filtro `where` tiene una sola clave por nivel (varias
condiciones van en $and / $or), una clave ausente no coincide con nada, `update` combina los
metadatos y `query` devuelve la distancia coseno. Con VECTOR_STORE=chroma se vuelve a Chroma.

En disco: data/vectores/fragmentos.json (ids, textos y metadatos) y vectores.npy.
"""
import json
import os
import threading
from pathlib import Path

import numpy as np

INDEX_FILE = "fragmentos.json"
VECTORS_FILE = "vectores.npy"


def matches(meta: dict, where: dict | None) -> bool:
    if where is None:
        return True
    if len(where) != 1:
        raise ValueError(f"Expected where to have exactly one operator, got {where}")
    ((key, cond),) = where.items()
    if key == "$and":
        return all(matches(meta, c) for c in cond)
    if key == "$or":
        return any(matches(meta, c) for c in cond)
    if key not in meta:
        return False
    value = meta[key]
    if isinstance(cond, dict):
        ((op, arg),) = cond.items()
        if op == "$in":
            return value in arg
        if op == "$nin":
            return value not in arg
        if op == "$eq":
            return value == arg and type(value) is type(arg)
        if op == "$ne":
            return value != arg
        raise ValueError(f"Operador no soportado: {op}")
    return value == cond and type(value) is type(cond)


class LocalCollection:
    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self._lock = threading.RLock()
        self.ids: list[str] = []
        self.documents: list[str | None] = []
        self.metadatas: list[dict] = []
        self.vectors = np.zeros((0, 0), dtype=np.float32)
        self._load()

    # ---------- disco ----------

    def _load(self) -> None:
        index = self.folder / INDEX_FILE
        if not index.exists():
            return
        data = json.loads(index.read_text(encoding="utf-8"))
        self.ids, self.documents, self.metadatas = data["ids"], data["documents"], data["metadatas"]
        vectors = self.folder / VECTORS_FILE
        self.vectors = np.load(vectors) if vectors.exists() and self.ids else np.zeros((0, 0), dtype=np.float32)
        if len(self.vectors) != len(self.ids):
            raise ValueError(f"El índice de {self.folder} está dañado: reindexa desde la consola")

    def _save(self) -> None:
        """Escribe en archivos temporales y los cambia de nombre: un apagón no deja el índice a medias."""
        self.folder.mkdir(parents=True, exist_ok=True)
        tmp_vectors = self.folder / (VECTORS_FILE + ".tmp")
        with tmp_vectors.open("wb") as f:
            np.save(f, self.vectors)
        tmp_index = self.folder / (INDEX_FILE + ".tmp")
        tmp_index.write_text(json.dumps({"ids": self.ids, "documents": self.documents,
                                         "metadatas": self.metadatas}, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_vectors, self.folder / VECTORS_FILE)
        os.replace(tmp_index, self.folder / INDEX_FILE)

    # ---------- API tipo Chroma ----------

    def count(self) -> int:
        return len(self.ids)

    def add(self, ids, embeddings, documents=None, metadatas=None):
        self.upsert(ids, embeddings, documents, metadatas)

    def upsert(self, ids, embeddings, documents=None, metadatas=None):
        new = np.asarray(embeddings, dtype=np.float32)
        if new.ndim != 2 or len(new) != len(ids):
            raise ValueError("Hace falta un vector por id")
        with self._lock:
            if len(self.ids) and new.shape[1] != self.vectors.shape[1]:
                raise ValueError(f"Los vectores miden {new.shape[1]} y el índice {self.vectors.shape[1]}: "
                                 "¿cambió el modelo de embeddings? Reindexa desde la consola")
            position = {chunk_id: i for i, chunk_id in enumerate(self.ids)}
            rows = []
            for i, chunk_id in enumerate(ids):
                doc = documents[i] if documents else None
                meta = dict(metadatas[i]) if metadatas else {}
                if chunk_id in position:
                    j = position[chunk_id]
                    self.vectors[j], self.documents[j], self.metadatas[j] = new[i], doc, meta
                else:
                    position[chunk_id] = len(self.ids) + len(rows)
                    rows.append(i)
                    self.ids.append(chunk_id)
                    self.documents.append(doc)
                    self.metadatas.append(meta)
            if rows:
                block = new[rows]
                self.vectors = block if self.vectors.size == 0 else np.vstack([self.vectors, block])
            self._save()

    def update(self, ids, metadatas=None, embeddings=None, documents=None):
        with self._lock:
            position = {chunk_id: i for i, chunk_id in enumerate(self.ids)}
            for i, chunk_id in enumerate(ids):
                j = position[chunk_id]
                if metadatas is not None:
                    self.metadatas[j] = {**self.metadatas[j], **metadatas[i]}  # como Chroma: combina
                if documents is not None:
                    self.documents[j] = documents[i]
                if embeddings is not None:
                    self.vectors[j] = np.asarray(embeddings[i], dtype=np.float32)
            self._save()

    def delete(self, ids=None, where=None):
        with self._lock:
            doomed = set(self._select(ids, where))
            if not doomed:
                return
            keep = [i for i, chunk_id in enumerate(self.ids) if chunk_id not in doomed]
            self.ids = [self.ids[i] for i in keep]
            self.documents = [self.documents[i] for i in keep]
            self.metadatas = [self.metadatas[i] for i in keep]
            self.vectors = self.vectors[keep] if keep else np.zeros((0, 0), dtype=np.float32)
            self._save()

    def _select(self, ids=None, where=None) -> list[str]:
        if ids is not None:
            known = set(self.ids)
            candidates = [i for i in ids if i in known]
            metas = {chunk_id: meta for chunk_id, meta in zip(self.ids, self.metadatas)}
            return [i for i in candidates if matches(metas[i], where)]
        return [chunk_id for chunk_id, meta in zip(self.ids, self.metadatas) if matches(meta, where)]

    def get(self, ids=None, where=None, include=("metadatas", "documents")):
        with self._lock:
            selected = self._select(ids, where)
            position = {chunk_id: i for i, chunk_id in enumerate(self.ids)}
            rows = [position[i] for i in selected]
            result = {"ids": selected}
            if "metadatas" in include:
                result["metadatas"] = [dict(self.metadatas[j]) for j in rows]
            if "documents" in include:
                result["documents"] = [self.documents[j] for j in rows]
            if "embeddings" in include:
                result["embeddings"] = [self.vectors[j].tolist() for j in rows]
            return result

    def query(self, query_embeddings, n_results=10, where=None):
        out = {"ids": [], "documents": [], "metadatas": [], "distances": []}
        with self._lock:
            rows = [j for j, meta in enumerate(self.metadatas) if matches(meta, where)]
            matrix = self.vectors[rows] if rows else None
            for vector in query_embeddings:
                if matrix is None:
                    for key in out:
                        out[key].append([])
                    continue
                q = np.asarray(vector, dtype=np.float32)
                norms = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(q) or 1.0)
                distances = 1.0 - (matrix @ q) / np.where(norms == 0, 1.0, norms)
                order = np.argsort(distances, kind="stable")[:n_results]
                out["ids"].append([self.ids[rows[k]] for k in order])
                out["documents"].append([self.documents[rows[k]] for k in order])
                out["metadatas"].append([dict(self.metadatas[rows[k]]) for k in order])
                out["distances"].append([float(distances[k]) for k in order])
        return out
