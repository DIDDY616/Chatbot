"""Prueba de voz ida y vuelta: Piper genera audio y Whisper lo transcribe.

Uso:  python -m tests.integracion.voz
"""
import sys
import time

from app import voice

sys.stdout.reconfigure(encoding="utf-8")
FRASES = {
    "es": "¿Cuántas horas de servicio social necesito para graduarme?",
    "en": "What TOEFL score do I need to graduate?",
    "fr": "Quels sont les horaires de la bibliothèque ?",
    "de": "Wie lange dauert das Studium?",
    "sv": "Hur ansöker jag om ett studieintyg?",
}

for lang, frase in FRASES.items():
    t0 = time.time()
    audio = voice.synthesize(frase, lang)
    t1 = time.time()
    result = voice.transcribe(audio)  # sin indicar idioma: también prueba la detección
    t2 = time.time()
    print(f"[{lang}] dicho:    {frase}")
    print(f"     escuchado: {result['text']}  (idioma detectado: {result['language']})")
    print(f"     síntesis {t1 - t0:.1f}s, reconocimiento {t2 - t1:.1f}s\n")
