"""Núcleo del asistente: recupera contexto y genera la respuesta.

La voz, el avatar y Teams son capas alrededor de answer().
"""
import json
import uuid
from collections.abc import Iterator
from datetime import datetime

from openai import OpenAI

from . import config, profiles
from .store import collection, embed

NO_ANSWER = "[SIN_RESPUESTA]"
LANGUAGES = {"es": "español", "en": "English", "fr": "français", "sv": "svenska", "de": "Deutsch"}

SYSTEM_PROMPT = """Eres {name}, asistente virtual para estudiantes del Tecnológico de Monterrey \
(Escuela de Ingeniería y Ciencias).

Reglas:
- Responde ÚNICAMENTE con la información del CONTEXTO. No inventes datos, fechas, nombres ni requisitos.
- Si el CONTEXTO responde la pregunta, aunque sea en parte, contesta con lo que sí dice.
- Solo si el CONTEXTO no dice nada sobre lo que se pregunta, empieza tu respuesta exactamente con {marker}, di que no \
cuentas con esa información y sugiere validarla con una fuente institucional (por ejemplo, la \
dirección del programa o los canales oficiales del Tec).
- Si el usuario nombra una carrera o programa con siglas, un nombre aproximado o un nombre coloquial \
que no aparece tal cual en el CONTEXTO (por ejemplo, pregunta por "ISC" o por "la carrera de sistemas" \
y el CONTEXTO solo habla de "ITC"), no lo des por hecho en silencio: \
si solo hay una opción parecida, empieza con la frase "Supongo que te refieres a <nombre correcto>" \
(o "Supongo que se refiere a <nombre correcto>" si hablas de usted) y luego responde, sin afirmar \
que ambos nombres sean equivalentes; si hay varias opciones parecidas, pregunta a cuál se refiere antes de responder. Las \
faltas de ortografía comunes no necesitan esta aclaración.
- Los saludos y la conversación casual los respondes con naturalidad, sin el marcador. No saludes \
en cada respuesta: saluda solo cuando el usuario te salude.
- Responde siempre en {language}, con la ortografía y puntuación propias de ese idioma, aunque el \
contexto esté en otro idioma.
- Sé claro y breve (2 a 5 frases), en texto plano sin markdown.

Tu función: {role}
Tu personalidad y forma de hablar: {personality}
Mantén ese estilo en todas tus respuestas, incluido el trato de tú o de usted, aunque el CONTEXTO \
o los ejemplos de las reglas usen otro. El estilo solo cambia el tono, nunca los datos ni las reglas.

CONTEXTO:
{context}

PREGUNTA A RESPONDER (el último mensaje del usuario, completado con la conversación previa):
{question}"""

CONDENSE_PROMPT = """Reescribe la última pregunta del usuario como una pregunta independiente, \
que se entienda sin la conversación previa. Nombra explícitamente el tema del que se viene \
hablando (el trámite, servicio, materia o programa) en lugar de usar "eso", "esa fecha" o \
similares. Devuelve solo la pregunta, sin explicaciones.

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


def retrieve(query: str, k: int = config.TOP_K, where: dict | None = None) -> list[dict]:
    """Fragmentos más parecidos a la consulta; `where` limita la búsqueda (ver Profile.access_filter)."""
    col = collection()
    if col.count() == 0:
        return []
    res = col.query(
        query_embeddings=embed([query]),
        n_results=min(k, col.count()),
        where=where,
    )
    return [
        {"text": doc, "source": meta["source"], "category": meta["category"], "distance": dist}
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]


def answer(session_id: str, message: str, language: str = "es",
           profile_id: str = profiles.DEFAULT_PROFILE, log: bool = True) -> dict:
    """Respuesta completa: {"answer", "answered", "sources", "search_query", "chunks"}."""
    event = {}
    for event in answer_stream(session_id, message, language, profile_id, log):
        pass
    return {key: value for key, value in event.items() if key != "type"}


def answer_stream(session_id: str, message: str, language: str = "es",
                  profile_id: str = profiles.DEFAULT_PROFILE, log: bool = True) -> Iterator[dict]:
    """Respuesta por partes, para empezar a hablar antes de que el modelo termine.

    Produce eventos {"type": "delta", "text"} y al final {"type": "done", ...} con la respuesta
    completa, si se pudo contestar, las fuentes, la consulta de búsqueda y los fragmentos usados.
    `log=False` evita registrar la pregunta en el historial (pruebas y evaluación).
    """
    profile = profiles.get(profile_id)
    history = _sessions.setdefault(session_id, [])[-2 * config.MAX_TURNS:]
    query = _condense(history, message) if history else message
    hits = retrieve(query, where=profile.access_filter())
    context = "\n\n".join(f"[Fuente: {h['source']}]\n{h['text']}" for h in hits) or "(sin documentos)"

    system = SYSTEM_PROMPT.format(
        name=profile.name,
        role=profile.role or "Resolver dudas generales de los estudiantes.",
        personality=profile.personality or "Amable y clara.",
        marker=NO_ANSWER,
        language=LANGUAGES.get(language, language),
        context=context,
        question=query,
    )
    stream = _llm.chat.completions.create(
        model=config.LLM_MODEL, temperature=0.2, stream=True,
        messages=[{"role": "system", "content": system}, *history, {"role": "user", "content": message}],
    )
    raw, sent = "", 0
    try:
        for chunk in stream:
            raw += (chunk.choices[0].delta.content or "") if chunk.choices else ""
            if NO_ANSWER.startswith(raw.strip()):
                continue  # todavía puede ser el marcador: no se envía hasta saberlo
            clean = raw.replace(NO_ANSWER, "").lstrip()
            if len(clean) > sent:
                yield {"type": "delta", "text": clean[sent:]}
                sent = len(clean)
    finally:
        stream.close()
    answered = NO_ANSWER not in raw
    text = raw.replace(NO_ANSWER, "").strip()

    _sessions[session_id] += [
        {"role": "user", "content": message},
        {"role": "assistant", "content": text},
    ]
    result = {
        "answer": text,
        "answered": answered,
        "sources": sorted({h["source"] for h in hits}) if answered else [],
    }
    if log:
        _log(session_id, profile_id, message, query, language, result)
    yield {"type": "done", **result, "search_query": query, "chunks": hits}


def warmup() -> None:
    """Hace que Ollama cargue el LLM y el modelo de embeddings."""
    embed(["hola"])
    _chat([{"role": "user", "content": "Responde solo: ok"}])


def reset(session_id: str) -> None:
    _sessions.pop(session_id, None)


def _log(session_id: str, profile_id: str, message: str, query: str, language: str, result: dict) -> None:
    """Historial en JSONL: base para estadísticas y preguntas sin respuesta en la consola."""
    config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": uuid.uuid4().hex[:12],
        "time": datetime.now().isoformat(timespec="seconds"),
        "session": session_id,
        "profile": profile_id,
        "language": language,
        "question": message,
        "search_query": query,
        **result,
    }
    with config.LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
