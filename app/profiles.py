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
    role: str = ""                   # su función: para qué sirve y a quién atiende
    personality: str = ""            # tono y forma de hablar; no cambia las reglas del RAG
    greeting: str = ""               # saludo inicial, en el idioma predeterminado
    language: str = "es"
    engine: str = "piper"            # motor de voz: "piper" o "chatterbox"
    voices: dict[str, str] = {}      # voz por idioma, p. ej. {"es": "es_MX-claude-high"}
    avatar: str = ""                 # id de web/avatars.json
    mood: str = "neutral"            # expresión base del avatar
    categories: list[str] = []       # categorías completas que puede consultar
    documents: list[str] = []        # documentos sueltos que puede consultar, además de las categorías
    wake_words: list[str] = []       # nombres a los que responde en una reunión; vacío = su nombre

    def wake_names(self) -> list[str]:
        return self.wake_words or [self.name]

    def access_filter(self) -> dict | None:
        """Filtro de búsqueda con lo que este asistente puede consultar; None = todo.

        Se aplica antes de que el modelo vea nada: lo que queda fuera no llega a la respuesta.
        """
        rules = []
        if self.categories:
            rules.append({"category": {"$in": self.categories}})
        if self.documents:
            rules.append({"source": {"$in": self.documents}})
        if not rules:
            return None
        return rules[0] if len(rules) == 1 else {"$or": rules}


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
