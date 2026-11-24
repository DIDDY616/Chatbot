"""Evaluación del asistente con las preguntas de tests/preguntas.jsonl.

Cada línea: pregunta, idioma, debe_responder y palabras esperadas en la respuesta.
Opcional: "previas" (preguntas anteriores en la misma conversación, para probar seguimientos)
y "no_esperado" (palabras que no deben aparecer).
"""
import json
import uuid

from . import config, rag


def cases() -> list[dict]:
    lines = config.EVAL_FILE.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def run_case(case: dict) -> dict:
    session = f"eval-{uuid.uuid4().hex}"
    for previous in case.get("previas", []):
        rag.answer(session, previous, case["idioma"], log=False)
    result = rag.answer(session, case["pregunta"], case["idioma"], log=False)
    rag.reset(session)
    text = result["answer"].lower()
    passed = (
        result["answered"] == case["debe_responder"]
        and all(word.lower() in text for word in case["esperado"])
        and not any(word.lower() in text for word in case.get("no_esperado", []))
    )
    return {"question": case["pregunta"], "passed": passed, "answer": result["answer"],
            "expected_answer": case["debe_responder"], "answered": result["answered"]}


def run() -> list[dict]:
    return [run_case(case) for case in cases()]
