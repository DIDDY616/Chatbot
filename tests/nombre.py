"""Prueba la activación por nombre del modo reunión.

Uso:  python -m tests.nombre          (solo la comparación de texto)
      python -m tests.nombre --voz    (además sintetiza frases con cada voz y las pasa por Whisper)
"""
import sys

from app import voice, wake

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

# (nombre del asistente, frase que se sintetiza, ¿debe activarlo?)
VOICE_CASES = [
    ("TecBot", "TecBot, ¿cuándo son las inscripciones?", True),
    ("TecBot", "Oye TecBot, ¿me puedes decir dónde está la biblioteca?", True),
    ("TecBot", "¿Cuánto cuesta reponer la credencial, TecBot?", True),
    ("TecBot", "TecBot.", True),
    ("TecBot", "Yo creo que la reunión del martes estuvo muy bien.", False),
    ("TecBot", "En el Tec las inscripciones son en línea.", False),
    ("TecBot", "Sí, dime.", False),
    ("Asesor", "Asesor, ¿cuántos semestres dura la carrera?", True),
    ("Asesor", "Oiga asesor, ¿dónde está la biblioteca?", True),
    ("Asesor", "Mañana tenemos examen de cálculo a las diez.", False),
    ("Lucía", "Lucía, ¿qué horario tiene la biblioteca?", True),
    ("Lucía", "Entonces nos vemos el jueves.", False),
]


def main() -> int:
    failures = 0
    for text, addressed, question in TEXT_CASES:
        got = wake.detect(text, ["TecBot"])
        ok = got["addressed"] == addressed and (question is None or got["question"] == question)
        failures += not ok
        print(f"{'OK   ' if ok else 'FALLA'} {text!r} -> {got}")
    for text, stop in STOP_CASES:
        got = wake.detect(text, ["TecBot"], "es")
        ok = got["addressed"] and got["stop"] == stop
        failures += not ok
        print(f"{'OK   ' if ok else 'FALLA'} alto={stop} {text!r} -> {got}")

    for text, ping in PING_CASES:
        got = wake.detect(text, ["TecBot"], "es")
        ok = got["addressed"] and got["ping"] == ping
        failures += not ok
        print(f"{'OK   ' if ok else 'FALLA'} ping={ping} {text!r} -> {got}")

    if "--voz" in sys.argv:
        speakers = voice.list_voices("es")
        for speaker in speakers:
            for name, text, addressed in VOICE_CASES:
                got = wake.hear(voice.synthesize(text, "es", speaker), "es", [name])
                ok = got["addressed"] == addressed
                failures += not ok
                if not ok:
                    print(f"FALLA [{speaker}] dicho {text!r} | oído {got['text']!r}")
        print(f"voz: {len(speakers)} voces x {len(VOICE_CASES)} frases")

    print(f"\n{failures} fallas")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
