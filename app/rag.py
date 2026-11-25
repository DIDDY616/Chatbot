"""Núcleo del asistente: identifica la intención, recupera contexto y genera la respuesta.

Flujo de una pregunta (el mismo que pide el encargo):
    intención -> (si es consulta) pregunta completa -> búsqueda -> modelo -> respuesta

La voz, el avatar y Teams son capas alrededor de answer_stream().
"""
import json
import threading
import uuid
from collections.abc import Iterator
from datetime import datetime

from . import config, intent, keyword, profiles, prompts, publication
from .prompts import NO_ANSWER
from .sessions import store as sessions
from .store import collection, embed

LANGUAGES = config.LANGUAGES

_llm = None
_log_lock = threading.Lock()


def _client():
    global _llm
    if _llm is None:
        from openai import OpenAI

        _llm = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)
    return _llm


def _chat(messages: list[dict]) -> str:
    resp = _client().chat.completions.create(model=config.LLM_MODEL, messages=messages, temperature=0.2)
    return (resp.choices[0].message.content or "").strip()


def _condense(history: list[dict], question: str) -> str:
    """Convierte una pregunta de seguimiento ("¿y cuánto dura?") en una pregunta completa."""
    text = "\n".join(f"{m['role']}: {m['content']}" for m in history)
    rewritten = _chat([{"role": "user", "content": prompts.CONDENSE_PROMPT.format(history=text, question=question)}])
    return rewritten or question


def retrieve(query: str, k: int = config.TOP_K, where: dict | None = None,
             include_drafts: bool = False) -> list[dict]:
    """Fragmentos más parecidos a la consulta.

    `where` limita la búsqueda (ver Profile.access_filter). Sin `include_drafts` solo se
    buscan los fragmentos publicados, que es lo que ven los estudiantes.
    """
    col = collection()
    total = col.count()
    if total == 0:
        return []
    if not include_drafts:
        where = publication.visible_to_students(where)
    wanted = max(k, config.HYBRID_CANDIDATES) if config.HYBRID_SEARCH else k
    res = col.query(query_embeddings=embed([query]), n_results=min(wanted, total), where=where)
    found = {
        chunk_id: {"text": doc, "source": meta["source"], "category": meta["category"],
                   "published": meta.get("published", True), "distance": dist, "match": "significado"}
        for chunk_id, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0],
                                             res["distances"][0])
    }
    vector_ids = list(found)
    if not config.HYBRID_SEARCH:
        return list(found.values())[:k]

    # Búsqueda por palabras sobre los mismos fragmentos permitidos (mismo filtro de acceso y publicación).
    pool = col.get(where=where, include=["documents", "metadatas"])
    order = keyword.bm25_rank(query, pool["documents"])[:config.HYBRID_CANDIDATES]
    keyword_ids = [pool["ids"][i] for i in order]
    for i in order:
        chunk_id, meta = pool["ids"][i], pool["metadatas"][i]
        if chunk_id in found:
            found[chunk_id]["match"] = "ambas"
        else:
            found[chunk_id] = {"text": pool["documents"][i], "source": meta["source"], "category": meta["category"],
                               "published": meta.get("published", True), "distance": None, "match": "palabras"}
    return [found[chunk_id] for chunk_id in keyword.rrf([vector_ids, keyword_ids])[:k]]


class MarkerFilter:
    """Quita el marcador de "sin respuesta" del texto que llega por partes.

    El modelo empieza con [SIN_RESPUESTA] cuando no sabe. Mientras lo que llegó todavía puede
    ser el principio del marcador, no se envía nada; después se envía todo menos el marcador.
    """

    def __init__(self, marker: str = NO_ANSWER):
        self.marker = marker
        self.raw = ""
        self._sent = 0

    def feed(self, delta: str) -> str:
        self.raw += delta
        if self.marker.startswith(self.raw.strip()):
            return ""
        clean = self.raw.replace(self.marker, "").lstrip()
        new, self._sent = clean[self._sent:], max(self._sent, len(clean))
        return new

    @property
    def answered(self) -> bool:
        return self.marker not in self.raw

    @property
    def text(self) -> str:
        return self.raw.replace(self.marker, "").strip()


def answer(session_id: str, message: str, language: str = "es",
           profile_id: str = profiles.DEFAULT_PROFILE, log: bool = True, include_drafts: bool = False) -> dict:
    """Respuesta completa: {"id", "answer", "answered", "sources", "intent", "search_query", "chunks"}."""
    *_, done = answer_stream(session_id, message, language, profile_id, log, include_drafts)
    return {key: value for key, value in done.items() if key != "type"}


def answer_stream(session_id: str, message: str, language: str = "es",
                  profile_id: str = profiles.DEFAULT_PROFILE, log: bool = True,
                  include_drafts: bool = False) -> Iterator[dict]:
    """Respuesta por partes, para empezar a hablar antes de que el modelo termine.

    Produce eventos {"type": "delta", "text"} y al final {"type": "done", ...} con la respuesta
    completa, si se pudo contestar, las fuentes, la intención, la consulta de búsqueda y los
    fragmentos usados. `log=False` evita registrar la pregunta en el historial (pruebas y
    evaluación). `include_drafts` también busca en documentos en borrador (consola).
    """
    profile = profiles.get(profile_id)
    history = sessions.history(session_id)
    kind = intent.classify(message)
    fields = {
        "name": profile.name,
        "institution": config.INSTITUTION,
        "role": profile.role or prompts.DEFAULT_ROLE,
        "personality": profile.personality or prompts.DEFAULT_PERSONALITY,
        "language": LANGUAGES.get(language, language),
    }

    if kind in intent.SMALL_TALK:
        query, hits = message, []
        system = prompts.SMALL_TALK_PROMPT.format(intent=kind, **fields)
    else:
        query = _condense(history, message) if history else message
        hits = retrieve(query, where=profile.access_filter(), include_drafts=include_drafts)
        context = "\n\n".join(f"[Fuente: {h['source']}]\n{h['text']}" for h in hits) or "(sin documentos)"
        system = prompts.SYSTEM_PROMPT.format(marker=NO_ANSWER, context=context, question=query, **fields)

    stream = _client().chat.completions.create(
        model=config.LLM_MODEL, temperature=0.2, stream=True,
        messages=[{"role": "system", "content": system}, *history, {"role": "user", "content": message}],
    )
    marker = MarkerFilter()
    try:
        for chunk in stream:
            delta = (chunk.choices[0].delta.content or "") if chunk.choices else ""
            if text := marker.feed(delta):
                yield {"type": "delta", "text": text}
    finally:
        close = getattr(stream, "close", None)
        if close:
            close()

    sessions.add(session_id, message, marker.text)
    answered = marker.answered or kind in intent.SMALL_TALK
    result = {
        "id": uuid.uuid4().hex[:12] if log else None,
        "answer": marker.text,
        "answered": answered,
        "sources": sorted({h["source"] for h in hits}) if marker.answered else [],
        "intent": kind,
    }
    if log:
        _log(session_id, profile_id, message, query, language, result)
    yield {"type": "done", **result, "search_query": query, "chunks": hits}


def warmup() -> None:
    """Hace que Ollama cargue el LLM y el modelo de embeddings."""
    embed(["hola"])
    _chat([{"role": "user", "content": "Responde solo: ok"}])


def reset(session_id: str) -> None:
    sessions.reset(session_id)


def _log(session_id: str, profile_id: str, message: str, query: str, language: str, result: dict) -> None:
    """Historial en JSONL: base para estadísticas y preguntas sin respuesta en la consola."""
    config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "session": session_id,
        "profile": profile_id,
        "language": language,
        "question": message,
        "search_query": query,
        **result,
    }
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with _log_lock, config.LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line)
