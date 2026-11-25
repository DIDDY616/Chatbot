"""Prueba que cada asistente solo consulta la información que tiene asignada.

Crea tres asistentes temporales con distinto acceso, les hace las mismas dos preguntas y
comprueba de qué documentos salen los fragmentos que usan. Al final los borra.

Uso:  python -m tests.integracion.acceso     (con la API encendida)
"""
import sys

import requests

from app import config

API_URL = config.API_URL
HEADERS = {"X-Admin-Token": config.ADMIN_TOKEN} if config.ADMIN_TOKEN else {}
SERVICES = "general/EJEMPLO_faq_servicios.md"
STUDY_PLAN = "ITC/EJEMPLO_plan_estudios.md"
QUESTIONS = {
    "biblioteca": "¿Qué horario tiene la biblioteca?",
    "carrera": "¿Cuántos semestres dura la carrera de ITC?",
}
# identificador: (acceso, documentos de los que puede salir su contexto)
CASES = {
    "prueba-solo-documento": ({"documents": [SERVICES]}, {SERVICES}),
    "prueba-solo-categoria": ({"categories": ["ITC"]}, {STUDY_PLAN}),
    "prueba-mixto": ({"categories": ["ITC"], "documents": [SERVICES]}, {SERVICES, STUDY_PLAN}),
}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    failures = 0
    try:
        for profile_id, (access, allowed) in CASES.items():
            requests.put(f"{API_URL}/profiles/{profile_id}", json={"name": "Prueba", **access},
                         headers=HEADERS, timeout=30).raise_for_status()
            for topic, question in QUESTIONS.items():
                resp = requests.post(f"{API_URL}/test", json={"message": question, "profile": profile_id},
                                     headers=HEADERS, timeout=120)
                resp.raise_for_status()
                result = resp.json()
                used = {chunk["source"] for chunk in result["chunks"]}
                expected_answer = (SERVICES if topic == "biblioteca" else STUDY_PLAN) in allowed
                ok = used <= allowed and result["answered"] == expected_answer
                failures += not ok
                print(f"{'OK   ' if ok else 'FALLA'} {profile_id:22s} {topic:10s} "
                      f"contesta={result['answered']} usa={sorted(used)}")
    finally:
        for profile_id in CASES:
            requests.delete(f"{API_URL}/profiles/{profile_id}", headers=HEADERS, timeout=30)
    print(f"\n{failures} fallas")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
