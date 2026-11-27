import json

import pytest

from app import config, history, profiles


def test_filtro_de_acceso():
    assert profiles.Profile(name="A").access_filter() is None
    assert profiles.Profile(name="A", categories=["ITC"]).access_filter() == {"category": {"$in": ["ITC"]}}
    both = profiles.Profile(name="A", categories=["ITC"], documents=["general/x.md"]).access_filter()
    assert both == {"$or": [{"category": {"$in": ["ITC"]}}, {"source": {"$in": ["general/x.md"]}}]}


def test_valida_idioma_motor_e_identificador():
    with pytest.raises(ValueError):
        profiles.Profile(name="A", language="pt")
    with pytest.raises(ValueError):
        profiles.Profile(name="A", engine="otro")
    assert profiles.valid_id("asesor-imt")
    assert not profiles.valid_id("Asesor IMT")
    assert not profiles.valid_id("../x")


def test_guardar_cargar_y_no_borrar_el_ultimo(env):
    assert list(profiles.load()) == [profiles.DEFAULT_PROFILE]  # sin archivo: el predeterminado
    profiles.save("uno", profiles.Profile(name="Uno"))
    assert profiles.get("uno").name == "Uno"
    profiles.delete(profiles.DEFAULT_PROFILE)
    assert profiles.get(profiles.DEFAULT_PROFILE).name == "Uno"  # sin "tecbot", vale el primero
    with pytest.raises(ValueError):
        profiles.delete("uno")
    with pytest.raises(ValueError):
        profiles.save("con espacio", profiles.Profile(name="X"))
    with pytest.raises(KeyError):
        profiles.get("no-existe")


def test_nombres_de_activacion():
    assert profiles.Profile(name="TecBot").wake_names() == ["TecBot"]
    assert profiles.Profile(name="TecBot", wake_words=["Tec"]).wake_names() == ["Tec"]


def _log(entries):
    config.LOG_FILE.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
                               encoding="utf-8")


def test_historial_estadisticas_y_linea_cortada(env):
    _log([
        {"id": "a1", "time": "2026-11-01T10:00:00", "session": "s1", "profile": "tecbot", "language": "es",
         "question": "¿Becas?", "answer": "No sé", "answered": False, "sources": [], "intent": "consulta"},
        {"id": "a2", "time": "2026-11-02T10:00:00", "session": "s2", "profile": "tecbot", "language": "en",
         "question": "Hi", "answer": "Hello", "answered": True, "sources": [], "intent": "saludo"},
    ])
    with config.LOG_FILE.open("a", encoding="utf-8") as f:
        f.write('{"id": "cortada", "time": ')  # apagón a media escritura
    history.set_feedback("a1", "bad")
    stats = history.stats()
    assert stats["total"] == 2 and stats["unanswered"] == 1 and stats["bad"] == 1
    assert stats["by_intent"] == {"consulta": 1, "saludo": 1}
    assert stats["top_unanswered"] == [("¿Becas?", 1)]
    assert history.exists("a2") and not history.exists("cortada")


def test_historial_antiguo_sin_id_ni_intencion(env):
    _log([{"time": "2026-11-01T10:00:00", "session": "abcdefghij", "language": "es",
           "question": "x", "answer": "y", "answered": True, "sources": []}])
    [entry] = history.entries()
    assert entry["id"] == "2026-11-01T10:00:00-abcdefgh"
    assert entry["intent"] == "consulta" and entry["profile"] == ""


def test_valoracion_invalida(env):
    with pytest.raises(ValueError):
        history.set_feedback("a1", "excelente")


def test_csv_con_bom_y_fuentes(env):
    _log([{"id": "a1", "time": "2026-11-01T10:00:00", "session": "s", "profile": "tecbot", "language": "es",
           "question": "¿Horario?", "answer": "7:00", "answered": True, "sources": ["a.md", "b.md"]}])
    text = history.to_csv()
    assert text.startswith("﻿time,")
    assert "a.md, b.md" in text and "¿Horario?" in text
