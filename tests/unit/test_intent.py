import pytest

from app import intent


@pytest.mark.parametrize("message, expected", [
    ("Hola", "saludo"),
    ("Buenos días", "saludo"),
    ("hello there", "consulta"),       # "there" no es de cortesía: mejor buscar
    ("Hi", "saludo"),
    ("Bonjour", "saludo"),
    ("Hallo", "saludo"),
    ("¡Muchas gracias!", "agradecimiento"),
    ("Gracias, muy amable", "consulta"),  # "amable" no está en la lista: se trata como consulta
    ("Thank you so much", "agradecimiento"),
    ("Merci beaucoup", "agradecimiento"),
    ("Danke", "agradecimiento"),
    ("Tack så mycket", "agradecimiento"),
    ("Adiós", "despedida"),
    ("Hasta luego", "despedida"),
    ("Goodbye", "despedida"),
    ("Hola, ¿qué horario tiene la biblioteca?", "consulta"),
    ("hola cuando son las inscripciones", "consulta"),
    ("¿Hasta cuándo puedo dar de baja una materia?", "consulta"),
    ("Gracias, ¿y cuánto cuesta?", "consulta"),
    ("ok", "consulta"),
    ("", "consulta"),
])
def test_clasifica(message, expected):
    assert intent.classify(message) == expected


def test_frase_larga_siempre_es_consulta():
    assert intent.classify("hola " * 20) == "consulta"
