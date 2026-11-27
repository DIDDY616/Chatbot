"""Activación por nombre con voz real: sintetiza frases con cada voz y las pasa por Whisper.

Uso:  python -m tests.integracion.nombre_voz      (necesita Whisper y las voces de Piper)

La comparación de texto (sin modelos) está en tests/unit/test_wake.py y corre con pytest.
"""
import sys

from app import voice, wake

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
    sys.stdout.reconfigure(encoding="utf-8")
    failures = 0
    speakers = voice.list_voices("es")
    for speaker in speakers:
        for name, text, addressed in VOICE_CASES:
            got = wake.hear(voice.synthesize(text, "es", speaker), "es", [name])
            ok = got["addressed"] == addressed
            failures += not ok
            if not ok:
                print(f"FALLA [{speaker}] dicho {text!r} | oído {got['text']!r}")
    total = len(speakers) * len(VOICE_CASES)
    print(f"\n{total - failures} de {total} correctas ({len(speakers)} voces x {len(VOICE_CASES)} frases)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
