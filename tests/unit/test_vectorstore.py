"""Almacén de vectores propio (app/vectorstore.py): persistencia, filtros y búsqueda."""
import pytest

from app.vectorstore import LocalCollection, matches


def fill(folder):
    col = LocalCollection(folder)
    col.add(ids=["a#0", "b#0", "faq#1"],
            embeddings=[[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]],
            documents=["biblioteca", "plan ITC", "faq"],
            metadatas=[{"source": "a", "category": "general", "published": True},
                       {"source": "b", "category": "ITC", "published": False},
                       {"source": "FAQ", "category": "general", "faq_id": "1", "published": True}])
    return col


def test_busca_por_coseno_y_filtra(tmp_path):
    col = fill(tmp_path)
    res = col.query([[1.0, 0.1]], n_results=2)
    assert res["ids"][0] == ["a#0", "faq#1"]
    assert res["distances"][0][0] < res["distances"][0][1]
    only_published = col.query([[0.0, 1.0]], n_results=5, where={"published": True})
    assert "b#0" not in only_published["ids"][0]
    both = {"$and": [{"category": {"$in": ["ITC", "general"]}}, {"published": True}]}
    assert set(col.query([[0.0, 1.0]], n_results=5, where=both)["ids"][0]) == {"a#0", "faq#1"}
    assert col.query([[1.0, 0.0]], where={"category": "nada"})["ids"] == [[]]


def test_se_guarda_y_se_vuelve_a_cargar(tmp_path):
    fill(tmp_path)
    again = LocalCollection(tmp_path)
    assert again.count() == 3
    assert again.get(ids=["b#0"], include=["documents"])["documents"] == ["plan ITC"]
    assert not list(tmp_path.glob("*.tmp"))  # no quedan archivos temporales


def test_update_combina_y_delete_por_filtro(tmp_path):
    col = fill(tmp_path)
    col.update(ids=["b#0"], metadatas=[{"published": True}])
    assert col.get(ids=["b#0"])["metadatas"][0] == {"source": "b", "category": "ITC", "published": True}
    col.delete(where={"category": "general"})
    assert col.get(include=[])["ids"] == ["b#0"]
    col.delete(ids=["b#0"])
    assert col.count() == 0 and LocalCollection(tmp_path).count() == 0


def test_upsert_reemplaza_el_mismo_id(tmp_path):
    col = fill(tmp_path)
    col.upsert(ids=["a#0"], embeddings=[[0.0, 1.0]], documents=["nuevo"], metadatas=[{"source": "a"}])
    assert col.count() == 3
    assert col.get(ids=["a#0"], include=["documents"])["documents"] == ["nuevo"]


def test_reglas_iguales_a_chroma():
    meta = {"published": True, "category": "ITC"}
    assert matches(meta, {"published": True})
    assert not matches(meta, {"published": 1})          # el tipo cuenta, como en Chroma
    assert not matches({"category": "ITC"}, {"published": True})  # clave ausente no coincide
    with pytest.raises(ValueError):
        matches(meta, {"published": True, "category": "ITC"})  # dos claves sin $and


def test_cambio_de_modelo_de_embeddings_da_un_error_claro(tmp_path):
    col = fill(tmp_path)
    with pytest.raises(ValueError, match="Reindexa"):
        col.add(ids=["c#0"], embeddings=[[1.0, 0.0, 0.0]], documents=["x"], metadatas=[{}])


def test_indice_vacio(tmp_path):
    col = LocalCollection(tmp_path / "nuevo")
    assert col.count() == 0
    assert col.query([[1.0, 0.0]]) == {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    col.delete(where={"source": "x"})  # borrar en vacío no falla
