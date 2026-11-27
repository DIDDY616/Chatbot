from app import config, documents, keyword, rag


def test_tokens_quita_acentos_y_palabras_vacias():
    # "cuántos", "tiene" y "la" no distinguen un fragmento de otro: se descartan.
    assert keyword.tokens("¿Cuántos créditos tiene la materia TC1001?") == ["creditos", "materia", "tc1001"]


def test_bm25_prefiere_la_clave_exacta():
    docs = [
        "La materia de programación se cursa en primer semestre.",
        "TC1001 Pensamiento computacional: 8 créditos.",
        "El horario de la biblioteca es de 7 a 22.",
    ]
    assert keyword.bm25_rank("¿Qué es TC1001?", docs)[0] == 1
    assert keyword.bm25_rank("", docs) == []
    assert keyword.bm25_rank("palabra inexistente", docs) == []


def test_rrf_premia_lo_que_aparece_en_las_dos_listas():
    assert keyword.rrf([["a", "b", "c"], ["c", "d"]])[0] == "c"
    assert set(keyword.rrf([["a"], ["b"]])) == {"a", "b"}


def test_busqueda_hibrida_respeta_filtros_y_marca_el_origen(env):
    documents.save("materias.md", "ITC", b"TC1001 Pensamiento computacional, primer semestre.", publish=True)
    documents.save("borrador.md", "ITC", b"TC1001 nota interna que no se debe ver.", publish=False)
    documents.save("biblio.md", "general", b"La biblioteca abre a las 7.", publish=True)
    hits = rag.retrieve("TC1001")
    assert {h["source"] for h in hits} <= {"ITC/materias.md", "general/biblio.md"}
    assert hits[0]["source"] == "ITC/materias.md"
    assert hits[0]["match"] in ("ambas", "palabras")
    only_general = rag.retrieve("TC1001", where={"category": {"$in": ["general"]}})
    assert [h["source"] for h in only_general] == ["general/biblio.md"]


def test_sin_busqueda_hibrida_solo_vectores(env, monkeypatch):
    monkeypatch.setattr(config, "HYBRID_SEARCH", False)
    documents.save("biblio.md", "general", b"La biblioteca abre a las 7.", publish=True)
    hits = rag.retrieve("biblioteca")
    assert hits and all(h["match"] == "significado" for h in hits)
