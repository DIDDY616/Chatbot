"""Historial de preguntas, valoraciones y estadísticas de uso (para la consola)."""
import json
from collections import Counter

from . import config


def _feedback() -> dict[str, str]:
    if not config.FEEDBACK_FILE.exists():
        return {}
    return json.loads(config.FEEDBACK_FILE.read_text(encoding="utf-8"))


def entries() -> list[dict]:
    """Preguntas registradas, de la más reciente a la más antigua, con su valoración si tiene."""
    if not config.LOG_FILE.exists():
        return []
    feedback = _feedback()
    result = []
    for line in config.LOG_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        entry.setdefault("id", f"{entry['time']}-{entry['session'][:8]}")  # registros anteriores al id
        entry.setdefault("profile", "")
        entry["feedback"] = feedback.get(entry["id"])
        result.append(entry)
    return result[::-1]


def set_feedback(entry_id: str, rating: str | None) -> None:
    """Marca una respuesta como "good" o "bad"; None quita la marca."""
    feedback = _feedback()
    if rating is None:
        feedback.pop(entry_id, None)
    else:
        feedback[entry_id] = rating
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
        "top_unanswered": Counter(e["question"].strip() for e in unanswered).most_common(10),
    }
