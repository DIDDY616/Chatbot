"""Chroma simulado en memoria, para computadoras donde Chroma no puede correr.

Solo se usa con PRUEBAS_CHROMA=simulado (ver conftest.py). Implementa lo que usa el proyecto
con las mismas reglas que Chroma: un filtro `where` tiene una sola clave por nivel (varias
condiciones van en $and / $or), una clave ausente no coincide con nada y `query` devuelve la
distancia coseno. Por omisión las pruebas usan el Chroma real.
"""
import math


def _matches(meta: dict, where: dict | None) -> bool:
    if where is None:
        return True
    if len(where) != 1:
        raise ValueError(f"Expected where to have exactly one operator, got {where}")
    (key, cond), = where.items()
    if key == "$and":
        return all(_matches(meta, c) for c in cond)
    if key == "$or":
        return any(_matches(meta, c) for c in cond)
    if key not in meta:
        return False
    value = meta[key]
    if isinstance(cond, dict):
        (op, arg), = cond.items()
        if op == "$in":
            return value in arg
        if op == "$nin":
            return value not in arg
        if op == "$eq":
            return value == arg
        if op == "$ne":
            return value != arg
        raise ValueError(f"Operador no simulado: {op}")
    return value == cond and type(value) is type(cond)


class FakeCollection:
    def __init__(self):
        self.rows: dict[str, dict] = {}

    def count(self) -> int:
        return len(self.rows)

    def add(self, ids, embeddings, documents=None, metadatas=None):
        self.upsert(ids, embeddings, documents, metadatas)

    def upsert(self, ids, embeddings, documents=None, metadatas=None):
        for i, row_id in enumerate(ids):
            self.rows[row_id] = {
                "embedding": list(embeddings[i]),
                "document": documents[i] if documents else None,
                "metadata": dict(metadatas[i]) if metadatas else {},
            }

    def update(self, ids, metadatas=None, embeddings=None, documents=None):
        for i, row_id in enumerate(ids):
            row = self.rows[row_id]
            if metadatas is not None:
                row["metadata"] = dict(metadatas[i])
            if documents is not None:
                row["document"] = documents[i]
            if embeddings is not None:
                row["embedding"] = list(embeddings[i])

    def delete(self, ids=None, where=None):
        for row_id in self._select(ids, where):
            del self.rows[row_id]

    def _select(self, ids=None, where=None) -> list[str]:
        candidates = [i for i in (ids if ids is not None else self.rows) if i in self.rows]
        return [i for i in candidates if _matches(self.rows[i]["metadata"], where)]

    def get(self, ids=None, where=None, include=("metadatas", "documents")):
        selected = self._select(ids, where)
        result = {"ids": selected}
        if "metadatas" in include:
            result["metadatas"] = [dict(self.rows[i]["metadata"]) for i in selected]
        if "documents" in include:
            result["documents"] = [self.rows[i]["document"] for i in selected]
        return result

    def query(self, query_embeddings, n_results=10, where=None):
        out = {"ids": [], "documents": [], "metadatas": [], "distances": []}
        for vector in query_embeddings:
            scored = sorted((self._distance(vector, self.rows[i]["embedding"]), i) for i in self._select(None, where))
            top = scored[:n_results]
            out["ids"].append([i for _, i in top])
            out["documents"].append([self.rows[i]["document"] for _, i in top])
            out["metadatas"].append([dict(self.rows[i]["metadata"]) for _, i in top])
            out["distances"].append([d for d, _ in top])
        return out

    @staticmethod
    def _distance(a, b) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) or 1.0
        return 1.0 - dot / norm


class FakeClient:
    def __init__(self):
        self.collections: dict[str, FakeCollection] = {}

    def get_or_create_collection(self, name, metadata=None):
        return self.collections.setdefault(name, FakeCollection())
