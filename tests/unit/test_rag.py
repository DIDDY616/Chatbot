import json

from app import config, documents, rag
from app.rag import MarkerFilter
from tests.unit.conftest import write_doc

LIBRARY = "La biblioteca abre de lunes a viernes de 7:00 a 22:00 horas."


def test_marcador_no_se_envia_y_marca_sin_respuesta():
    marker = MarkerFilter()
    sent = "".join(marker.feed(piece) for piece in ["[SIN", "_RESP", "UESTA] No ", "tengo ", "ese dato."])
    assert sent == "No tengo ese dato."
    assert not marker.answered
    assert marker.text == "No tengo ese dato."


def test_texto_normal_pasa_completo():
    marker = MarkerFilter()
    sent = "".join(marker.feed(piece) for piece in ["[La", " biblioteca", " abre."])
    assert sent == "[La biblioteca abre."
    assert marker.answered


def test_responde_con_fuente_y_registra(env):
    from app.ingest import ingest_all

    write_doc("general", "servicios.md", LIBRARY)
    ingest_all()
    result = rag.answer("s1", "¿Qué horario tiene la biblioteca?")
    assert result["answered"] is True
    assert result["sources"] == ["general/servicios.md"]
    assert result["intent"] == "consulta"
    entry = json.loads(config.LOG_FILE.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["id"] == result["id"] and entry["intent"] == "consulta"


def test_sin_documentos_dice_que_no_sabe(env):
    result = rag.answer("s1", "¿Cuánto cuesta la colegiatura?")
    assert result["answered"] is False
    assert result["sources"] == []
    assert "[SIN_RESPUESTA]" not in result["answer"]


def test_saludo_no_busca_en_documentos(env):
    from app.ingest import ingest_all

    write_doc("general", "servicios.md", LIBRARY)  # existe, pero un saludo no lo consulta
    ingest_all()
    calls_before = env.embeddings.calls
    result = rag.answer("s1", "Hola")
    assert result["intent"] == "saludo"
    assert result["answered"] is True and result["sources"] == []
    assert result["chunks"] == []
    assert env.embeddings.calls == calls_before  # ni siquiera calculó el vector de la pregunta


def test_seguimiento_usa_la_conversacion(env):
    rag.answer("s1", "¿Qué horario tiene la biblioteca?", log=False)
    result = rag.answer("s1", "¿Y en exámenes?", log=False)
    assert result["search_query"] == "pregunta reescrita sobre la biblioteca"
    last = env.llm.calls[-1]["messages"]
    assert [m["role"] for m in last] == ["system", "user", "assistant", "user"]


def test_borrador_no_llega_a_estudiantes(env):
    documents.save("servicios.md", "general", LIBRARY.encode(), publish=False)
    student = rag.answer("s1", "¿Qué horario tiene la biblioteca?", log=False)
    assert student["chunks"] == [] and student["answered"] is False

    admin = rag.answer("s2", "¿Qué horario tiene la biblioteca?", log=False, include_drafts=True)
    assert [c["source"] for c in admin["chunks"]] == ["general/servicios.md"]
    assert admin["chunks"][0]["published"] is False

    documents.publish("general/servicios.md")
    again = rag.answer("s3", "¿Qué horario tiene la biblioteca?", log=False)
    assert again["sources"] == ["general/servicios.md"]


def test_acceso_por_perfil(env):
    from app import profiles

    documents.save("servicios.md", "general", LIBRARY.encode(), publish=True)
    documents.save("plan.md", "ITC", b"ITC dura 8 semestres.", publish=True)
    profiles.save("solo-itc", profiles.Profile(name="Asesor", categories=["ITC"]))
    result = rag.answer("s1", "¿Qué horario tiene la biblioteca?", profile_id="solo-itc", log=False)
    assert {c["source"] for c in result["chunks"]} == {"ITC/plan.md"}
