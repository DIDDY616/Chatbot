"""Evaluación rápida del RAG.  Uso:  python -m tests.eval

Cada línea de preguntas.jsonl: pregunta, idioma, debe_responder y palabras esperadas en la respuesta.
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
    res = rag.answer(uuid.uuid4().hex, case["pregunta"], case["idioma"])
    ok = res["answered"] == case["debe_responder"] and all(
        word.lower() in res["answer"].lower() for word in case["esperado"]
    )
    passed += ok
    print(f"{'OK   ' if ok else 'FALLA'} {case['pregunta']}\n      -> {res['answer']}\n")

print(f"{passed}/{len(cases)} correctas")
sys.exit(0 if passed == len(cases) else 1)
