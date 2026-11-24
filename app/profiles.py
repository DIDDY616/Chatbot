"""Perfiles de asistente: identidad, personalidad, voz, avatar y categorías que consulta.

Se guardan en data/perfiles.json y se leen en cada petición, así que los cambios
aplican sin reiniciar el servidor.
"""
import json

from pydantic import BaseModel

from . import config

DEFAULT_PROFILE = "tecbot"


class Profile(BaseModel):
    name: str
    description: str = ""
    personality: str = ""            # tono y forma de hablar; no cambia las reglas del RAG
    greeting: str = ""               # saludo inicial, en el idioma predeterminado
    language: str = "es"
    engine: str = "piper"            # motor de voz: "piper" o "chatterbox"
    voices: dict[str, str] = {}      # voz por idioma, p. ej. {"es": "es_MX-claude-high"}
    avatar: str = ""                 # id de web/avatars.json
    mood: str = "neutral"            # expresión base del avatar
    categories: list[str] = []       # categorías de documentos que consulta; vacío = todas


def load() -> dict[str, Profile]:
    if not config.PROFILES_FILE.exists():
        return {DEFAULT_PROFILE: Profile(name=config.ASSISTANT_NAME)}
    raw = json.loads(config.PROFILES_FILE.read_text(encoding="utf-8"))
    return {key: Profile(**value) for key, value in raw.items()}


def get(profile_id: str) -> Profile:
    profiles = load()
    if profile_id not in profiles and profile_id == DEFAULT_PROFILE:
        return next(iter(profiles.values()))  # si se borró el predeterminado, vale el primero
    if profile_id not in profiles:
        raise KeyError(f"Perfil desconocido: '{profile_id}'")
    return profiles[profile_id]


def save(profile_id: str, profile: Profile) -> None:
    profiles = load()
    profiles[profile_id] = profile
    _write(profiles)


def delete(profile_id: str) -> None:
    profiles = load()
    profiles.pop(profile_id, None)
    _write(profiles)


def _write(profiles: dict[str, Profile]) -> None:
    data = {key: value.model_dump() for key, value in profiles.items()}
    config.PROFILES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
