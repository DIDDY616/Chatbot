"""Evaluación rápida del RAG.  Uso:  python -m tests.eval

Cada línea de preguntas.jsonl: pregunta, idioma, debe_responder y palabras esperadas en la respuesta.
Opcional: "previas", preguntas que se hacen antes en la misma conversación (para probar seguimientos),
y "no_esperado", palabras que no deben aparecer en la respuesta.
"""
import json
import sys
import uuid
from pathlib import Path

from app import rag

sys.stdout.reconfigure(encoding="utf-8")
cases = [json.loads(line) for line in Path(__file__).with_name("preguntas.jsonl").read_text("utf-8").splitlines() if line.strip()]

passed = 0
for case in cases:
    session = uuid.uuid4().hex
    for previa in case.get("previas", []):
        rag.answer(session, previa, case["idioma"])
    res = rag.answer(session, case["pregunta"], case["idioma"])
    text = res["answer"].lower()
    ok = (
        res["answered"] == case["debe_responder"]
        and all(word.lower() in text for word in case["esperado"])
        and not any(word.lower() in text for word in case.get("no_esperado", []))
    )
    passed += ok
    print(f"{'OK   ' if ok else 'FALLA'} {case['pregunta']}\n      -> {res['answer']}\n")

print(f"{passed}/{len(cases)} correctas")
sys.exit(0 if passed == len(cases) else 1)
