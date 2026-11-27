"""Historial de preguntas, valoraciones y estadísticas de uso (para la consola)."""
import csv
import io
import json
import threading
from collections import Counter

from . import config

_lock = threading.Lock()
RATINGS = ("good", "bad")


def _feedback() -> dict[str, str]:
    if not config.FEEDBACK_FILE.exists():
        return {}
    return json.loads(config.FEEDBACK_FILE.read_text(encoding="utf-8") or "{}")


def entries() -> list[dict]:
    """Preguntas registradas, de la más reciente a la más antigua, con su valoración si tiene."""
    if not config.LOG_FILE.exists():
        return []
    feedback = _feedback()
    result = []
    for line in config.LOG_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue  # una línea cortada (p. ej. un apagón a media escritura) no tumba la consola
        entry.setdefault("id", f"{entry['time']}-{entry['session'][:8]}")  # registros anteriores al id
        entry.setdefault("profile", "")
        entry.setdefault("intent", "consulta")
        entry["feedback"] = feedback.get(entry["id"])
        result.append(entry)
    return result[::-1]


def exists(entry_id: str) -> bool:
    return any(e["id"] == entry_id for e in entries())


def set_feedback(entry_id: str, rating: str | None) -> None:
    """Marca una respuesta como "good" o "bad"; None quita la marca."""
    if rating is not None and rating not in RATINGS:
        raise ValueError(f"Valoración no válida: {rating}")
    with _lock:
        feedback = _feedback()
        if rating is None:
            feedback.pop(entry_id, None)
        else:
            feedback[entry_id] = rating
        config.FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        config.FEEDBACK_FILE.write_text(json.dumps(feedback, ensure_ascii=False, indent=2), encoding="utf-8")


def stats() -> dict:
    items = entries()
    unanswered = [e for e in items if not e["answered"]]
    return {
        "total": len(items),
        "answered": len(items) - len(unanswered),
        "unanswered": len(unanswered),
        "sessions": len({e["session"] for e in items}),
        "good": sum(e["feedback"] == "good" for e in items),
        "bad": sum(e["feedback"] == "bad" for e in items),
        "by_day": dict(sorted(Counter(e["time"][:10] for e in items).items())),
        "by_language": dict(Counter(e["language"] for e in items).most_common()),
        "by_profile": dict(Counter(e["profile"] or "(sin perfil)" for e in items).most_common()),
        "by_intent": dict(Counter(e["intent"] for e in items).most_common()),
        "top_unanswered": Counter(e["question"].strip() for e in unanswered).most_common(10),
    }


def to_csv(items: list[dict] | None = None) -> str:
    """Historial como CSV (con BOM para que Excel respete los acentos)."""
    columns = ["time", "profile", "language", "intent", "question", "answer", "answered", "sources", "feedback"]
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(columns)
    for e in entries() if items is None else items:
        writer.writerow([", ".join(e.get(c) or []) if c == "sources" else e.get(c, "") for c in columns])
    return "﻿" + out.getvalue()
