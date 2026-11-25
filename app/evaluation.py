"""Evaluación del asistente con las preguntas de tests/preguntas.jsonl.

Cada línea: pregunta, idioma, debe_responder y palabras esperadas en la respuesta.
Opcional: "previas" (preguntas anteriores en la misma conversación, para probar seguimientos),
"no_esperado" (palabras que no deben aparecer) y "perfil" (asistente con el que se pregunta).
"""
import json
import uuid

from . import config, profiles, rag


def cases() -> list[dict]:
    lines = config.EVAL_FILE.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def check(case: dict, result: dict) -> bool:
    """¿La respuesta cumple lo que espera el caso?"""
    text = result["answer"].lower()
    return (
        result["answered"] == case["debe_responder"]
        and all(word.lower() in text for word in case.get("esperado", []))
        and not any(word.lower() in text for word in case.get("no_esperado", []))
    )


def run_case(case: dict, include_drafts: bool = False) -> dict:
    session = f"eval-{uuid.uuid4().hex}"
    profile = case.get("perfil", profiles.DEFAULT_PROFILE)
    try:
        for previous in case.get("previas", []):
            rag.answer(session, previous, case["idioma"], profile, log=False, include_drafts=include_drafts)
        result = rag.answer(session, case["pregunta"], case["idioma"], profile, log=False,
                            include_drafts=include_drafts)
    finally:
        rag.reset(session)
    return {"question": case["pregunta"], "passed": check(case, result), "answer": result["answer"],
            "expected_answer": case["debe_responder"], "answered": result["answered"]}


def run(include_drafts: bool = False) -> list[dict]:
    return [run_case(case, include_drafts) for case in cases()]
