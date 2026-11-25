"""Entorno de pruebas sin modelos: datos en una carpeta temporal, embeddings y LLM simulados.

Los embeddings simulados son una bolsa de palabras con hash: dos textos que comparten palabras
quedan cerca, así que la búsqueda de Chroma (real) se comporta de forma creíble.

Con PRUEBAS_CHROMA=simulado se usa un Chroma en memoria (tests/unit/fake_chroma.py), para
computadoras donde el Chroma real no puede correr (por ejemplo, con muy poca memoria libre).
"""
import hashlib
import math
import os
import re
from types import SimpleNamespace

import pytest

from app import config, rag, sessions, store

DIM = 256
WORD = re.compile(r"[^\W_]+")


def fake_vector(text: str) -> list[float]:
    vector = [0.0] * DIM
    for word in WORD.findall(text.lower()):
        vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class FakeEmbeddings:
    def __init__(self):
        self.calls = 0

    def create(self, model, input):
        self.calls += 1
        return SimpleNamespace(data=[SimpleNamespace(embedding=fake_vector(t), index=i) for i, t in enumerate(input)])


class FakeLLM:
    """Imita chat.completions de OpenAI. `reply(messages)` decide el texto de la respuesta."""

    def __init__(self):
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.reply = self.default_reply

    @staticmethod
    def default_reply(messages: list[dict]) -> str:
        system = messages[0]["content"]
        if "Reescribe la última pregunta" in system:
            return "pregunta reescrita sobre la biblioteca"
        if "(sin documentos)" in system:
            return "[SIN_RESPUESTA] No cuento con esa información."
        if "solo conversa" in system:
            return "¡Hola! ¿En qué te ayudo?"
        return "La biblioteca abre a las 7:00."

    def _create(self, model, messages, temperature=0.2, stream=False):
        self.calls.append({"messages": messages, "stream": stream})
        text = self.reply(messages)
        if not stream:
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
        pieces = [text[i:i + 4] for i in range(0, len(text), 4)]
        return iter([SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=p))]) for p in pieces])


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Carpeta de datos vacía, Chroma propio y modelos simulados. Devuelve los dobles."""
    data = tmp_path / "data"
    paths = {
        "DATA_DIR": data,
        "DOCS_DIR": data / "docs",
        "CHROMA_DIR": data / "chroma",
        "LOG_FILE": data / "historial.jsonl",
        "PROFILES_FILE": data / "perfiles.json",
        "FAQS_FILE": data / "faqs.json",
        "FEEDBACK_FILE": data / "valoraciones.json",
        "PUBLICATION_FILE": data / "publicacion.json",
        "CUSTOM_AVATARS_FILE": data / "personajes.json",
        "AVATARS_DIR": tmp_path / "avatars",
        "EVAL_FILE": tmp_path / "preguntas.jsonl",
    }
    for name, value in paths.items():
        monkeypatch.setattr(config, name, value)
    monkeypatch.setattr(config, "ADMIN_TOKEN", "")
    data.mkdir()

    store.reset()
    if os.getenv("PRUEBAS_CHROMA") == "simulado":
        from tests.unit.fake_chroma import FakeClient

        monkeypatch.setattr(store, "_chroma", FakeClient())
    embeddings = FakeEmbeddings()
    llm = FakeLLM()
    monkeypatch.setattr(store, "_client", lambda: SimpleNamespace(embeddings=embeddings))
    monkeypatch.setattr(rag, "_client", lambda: llm)
    monkeypatch.setattr(rag, "sessions", sessions.SessionStore(config.MAX_TURNS, 3600, 100))
    yield SimpleNamespace(data=data, llm=llm, embeddings=embeddings)
    store.reset()


def write_doc(category: str, name: str, text: str):
    path = config.DOCS_DIR / category / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
