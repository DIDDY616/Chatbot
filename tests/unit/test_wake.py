"""Activación por nombre (solo texto). La versión con voz real: tests/integracion/nombre_voz.py."""
import pytest

from app import wake

# (frase transcrita, ¿va dirigida al asistente?, pregunta esperada o None para no comprobarla)
TEXT_CASES = [
    ("TecBot, ¿cuándo son las inscripciones?", True, "¿cuándo son las inscripciones?"),
    ("Tec Bot, ¿cuándo son las inscripciones?", True, "¿cuándo son las inscripciones?"),
    ("— TecBot, ¿cuándo son las inscripciones?", True, "¿cuándo son las inscripciones?"),
    ("Oye, Techbot, ¿dónde está la biblioteca?", True, "Oye, ¿dónde está la biblioteca?"),
    ("¿Cuánto cuesta la credencial, Tekbot?", True, "¿Cuánto cuesta la credencial?"),
    ("Tec-Bot.", True, ""),
    ("tegbot cuál es el horario", True, "cuál es el horario"),
    ("decobot cuando son las inscripciones", True, "cuando son las inscripciones"),
    ("Tech boat, when is the enrollment period?", True, "when is the enrollment period?"),
    ("Tech bought, where is the library?", True, "where is the library?"),
    ("Hey, tick bot, where is the library?", True, "Hey, where is the library?"),
    ("Tag-Bot, wann ist die Einschreibung?", True, "wann ist die Einschreibung?"),
    ("Yo estudio en el Tec desde hace dos años.", False, None),
    ("¿Cuánto te cobró la reposición?", False, None),
    ("Mañana voy al Tec por la mañana.", False, None),
    ("En el Tec voy en tercer semestre.", False, None),
    ("Si no te boto la basura yo.", False, None),
    ("You should take both courses.", False, None),
    ("We will take about ten minutes.", False, None),
    ("Puede ser en el Tec o en otro lado.", False, None),
    ("El techo del salón tiene goteras.", False, None),
    ("El robot de la clase no funcionó.", False, None),
    ("Entonces nos vemos el martes en el Tec, ¿va?", False, None),
    ("", False, None),
]

# (frase transcrita, ¿es una orden de callarse?)
STOP_CASES = [
    ("TecBot, espera.", True),
    ("TecBot, espera un momento, por favor.", True),
    ("Gracias, TecBot.", True),
    ("Muchas gracias, TecBot, eso es todo.", True),
    ("Ya, TecBot.", True),
    ("TecBot, para.", True),
    ("TecBot, ¿para qué sirve la credencial?", False),
    ("TecBot, espera, ¿y los sábados a qué hora abre?", False),
    ("TecBot, gracias, ¿y cuánto cuesta el estacionamiento?", False),
    ("TecBot.", False),
    ("TecBot, por favor.", False),
]

# (frase transcrita, ¿solo preguntan si está oyendo?)
PING_CASES = [
    ("TecBot, ¿me escuchas?", True),
    ("Hola, TecBot, ¿me oyes?", True),
    ("TecBot, ¿estás ahí?", True),
    ("TecBot, ¿me escuchas? Quiero saber el horario de la biblioteca y cuánto cuesta la credencial.", False),
    ("TecBot, ¿cuándo son las inscripciones?", False),
]


@pytest.mark.parametrize("text, addressed, question", TEXT_CASES)
def test_detecta_el_nombre(text, addressed, question):
    got = wake.detect(text, ["TecBot"])
    assert got["addressed"] == addressed
    if question is not None:
        assert got["question"] == question


@pytest.mark.parametrize("text, stop", STOP_CASES)
def test_ordenes_de_alto(text, stop):
    got = wake.detect(text, ["TecBot"], "es")
    assert got["addressed"] and got["stop"] == stop


@pytest.mark.parametrize("text, ping", PING_CASES)
def test_preguntas_de_presencia(text, ping):
    got = wake.detect(text, ["TecBot"], "es")
    assert got["addressed"] and got["ping"] == ping


def test_varios_nombres():
    assert wake.detect("Asesor, ¿cuántos semestres dura?", ["TecBot", "Asesor"])["addressed"]
