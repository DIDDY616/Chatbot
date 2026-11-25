"""Evaluación rápida del RAG.  Uso:  python -m tests.integracion.eval

Los casos están en tests/preguntas.jsonl; el formato se explica en app/evaluation.py.
"""
import sys

from app import evaluation

sys.stdout.reconfigure(encoding="utf-8")
results = evaluation.run()
for r in results:
    print(f"{'OK   ' if r['passed'] else 'FALLA'} {r['question']}\n      -> {r['answer']}\n")

passed = sum(r["passed"] for r in results)
print(f"{passed}/{len(results)} correctas")
sys.exit(0 if passed == len(results) else 1)
