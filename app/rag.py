"""Núcleo del asistente: recupera contexto y genera la respuesta.

Voz, avatar y Teams se construirán después alrededor de answer().
"""
import json
from datetime import datetime

from openai import OpenAI

from . import config
from .store import collection, embed

NO_ANSWER = "[SIN_RESPUESTA]"
LANGUAGES = {"es": "español", "en": "English", "fr": "français", "sv": "svenska", "de": "Deutsch"}

SYSTEM_PROMPT = """Eres {name}, asistente virtual para estudiantes del Tecnológico de Monterrey \
(Escuela de Ingeniería y Ciencias).

Reglas:
- Responde ÚNICAMENTE con la información del CONTEXTO. No inventes datos, fechas, nombres ni requisitos.
- Si el CONTEXTO no contiene la respuesta, empieza tu respuesta exactamente con {marker}, di que no \
cuentas con esa información y sugiere validarla con una fuente institucional (por ejemplo, la \
dirección del programa o los canales oficiales del Tec).
- Los saludos y la conversación casual los respondes con naturalidad, sin el marcador.
- Responde siempre en {language}, aunque el contexto esté en otro idioma.
- Sé claro y breve (2 a 5 frases), en texto plano sin markdown.

CONTEXTO:
{context}"""

CONDENSE_PROMPT = """Reescribe la última pregunta del usuario como una pregunta independiente, \
que se entienda sin la conversación previa. Devuelve solo la pregunta, sin explicaciones.

Conversación:
{history}

Última pregunta: {question}"""

_llm = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)
_sessions: dict[str, list[dict]] = {}  # memoria por sesión (se pierde al reiniciar)


def _chat(messages: list[dict]) -> str:
    resp = _llm.chat.completions.create(model=config.LLM_MODEL, messages=messages, temperature=0.2)
    return (resp.choices[0].message.content or "").strip()


def _condense(history: list[dict], question: str) -> str:
    """Convierte una pregunta de seguimiento ("¿y cuánto dura?") en una pregunta completa."""
    text = "\n".join(f"{m['role']}: {m['content']}" for m in history)
    return _chat([{"role": "user", "content": CONDENSE_PROMPT.format(history=text, question=question)}])


def retrieve(query: str, k: int = config.TOP_K) -> list[dict]:
    col = collection()
    if col.count() == 0:
        return []
    res = col.query(query_embeddings=embed([query]), n_results=min(k, col.count()))
    return [
        {"text": doc, "source": meta["source"], "category": meta["category"], "distance": dist}
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]


def answer(session_id: str, message: str, language: str = "es") -> dict:
    history = _sessions.setdefault(session_id, [])[-2 * config.MAX_TURNS:]
    query = _condense(history, message) if history else message
    hits = retrieve(query)
    context = "\n\n".join(f"[Fuente: {h['source']}]\n{h['text']}" for h in hits) or "(sin documentos)"

    system = SYSTEM_PROMPT.format(
        name=config.ASSISTANT_NAME,
        marker=NO_ANSWER,
        language=LANGUAGES.get(language, language),
        context=context,
    )
    text = _chat([{"role": "system", "content": system}, *history, {"role": "user", "content": message}])
    answered = NO_ANSWER not in text
    text = text.replace(NO_ANSWER, "").strip()

    _sessions[session_id] += [
        {"role": "user", "content": message},
        {"role": "assistant", "content": text},
    ]
    result = {
        "answer": text,
        "answered": answered,
        "sources": sorted({h["source"] for h in hits}) if answered else [],
    }
    _log(session_id, message, query, language, result)
    return result


def reset(session_id: str) -> None:
    _sessions.pop(session_id, None)


def _log(session_id: str, message: str, query: str, language: str, result: dict) -> None:
    """Historial en JSONL: base para estadísticas y preguntas sin respuesta en la consola."""
    config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "session": session_id,
        "language": language,
        "question": message,
        "search_query": query,
        **result,
    }
    with config.LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
