"""La API completa con TestClient: rutas, clave de administración y el flujo borrador -> publicado."""
import io
import json

import pytest
from fastapi.testclient import TestClient

from app import config
from app.api import create_app
from app.api.meetings import is_teams_link

LIBRARY = "La biblioteca abre de lunes a viernes de 7:00 a 22:00 horas."


@pytest.fixture
def client(env):
    with TestClient(create_app()) as test_client:
        yield test_client


def upload(client, name, text, category="general", publish=False, headers=None):
    return client.post("/documents", files={"file": (name, io.BytesIO(text.encode()))},
                       data={"category": category, "publish": str(publish).lower()}, headers=headers or {})


def ask(client, message, session="s1"):
    return client.post("/chat", json={"session_id": session, "message": message}).json()


def test_salud_y_pagina(client):
    assert client.get("/health").json()["chunks"] == 0
    assert client.get("/", follow_redirects=False).status_code in (302, 307)


def test_flujo_borrador_probar_publicar(client):
    assert upload(client, "servicios.md", LIBRARY).json()["published"] is False
    assert ask(client, "¿Qué horario tiene la biblioteca?")["sources"] == []

    test = client.post("/test", json={"message": "¿Qué horario tiene la biblioteca?"}).json()
    assert [c["source"] for c in test["chunks"]] == ["general/servicios.md"]

    resp = client.put("/documents/publish", params={"source": "general/servicios.md"}, json={"published": True})
    assert resp.status_code == 200
    assert ask(client, "¿Qué horario tiene la biblioteca?", "s2")["sources"] == ["general/servicios.md"]


def test_publicar_todo(client):
    upload(client, "a.md", "Dato a.")
    client.post("/faqs", json={"question": "¿Hay café?", "answer": "Sí.", "published": False})
    assert client.post("/publish-all").json() == {"published": 2}
    assert all(d["published"] for d in client.get("/documents").json())


def test_stream_no_manda_fragmentos(client):
    upload(client, "servicios.md", LIBRARY, publish=True)
    resp = client.post("/chat/stream", json={"session_id": "s", "message": "¿Horario de la biblioteca?"})
    events = [json.loads(line) for line in resp.text.splitlines() if line.strip()]
    assert events[-1]["type"] == "done" and "chunks" not in events[-1]
    assert "".join(e["text"] for e in events if e["type"] == "delta") == events[-1]["answer"]


def test_valoracion_del_estudiante(client):
    answer = ask(client, "¿Qué horario tiene la biblioteca?")
    assert client.put(f"/feedback/{answer['id']}", json={"rating": "good"}).status_code == 200
    assert client.get("/stats").json()["good"] == 1
    assert client.put("/feedback/no-existe", json={"rating": "good"}).status_code == 404
    assert client.put(f"/feedback/{answer['id']}", json={"rating": "excelente"}).status_code == 422


def test_clave_de_administracion(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_TOKEN", "secreta")
    assert client.get("/documents").status_code == 401
    assert client.get("/documents", headers={"X-Admin-Token": "mala"}).status_code == 401
    assert client.get("/documents", headers={"X-Admin-Token": "secreta"}).status_code == 200
    assert client.put("/profiles/x", json={"name": "X"}).status_code == 401
    assert client.post("/meeting/join", json={"url": "https://teams.live.com/meet/1"}).status_code == 401
    # Lo que usa la página del avatar sigue abierto.
    assert client.get("/profiles").status_code == 200
    assert client.get("/avatar/avatars.json").status_code == 200
    assert client.post("/chat", json={"session_id": "s", "message": "Hola"}).status_code == 200


def test_perfiles_validos(client):
    assert client.put("/profiles/asesor-imt", json={"name": "Asesor IMT", "language": "en"}).status_code == 200
    assert client.put("/profiles/Con Espacio", json={"name": "X"}).status_code == 400
    assert client.put("/profiles/otro", json={"name": "X", "language": "pt"}).status_code == 422
    assert client.post("/chat", json={"session_id": "s", "message": "Hola", "profile": "nadie"}).status_code == 404


def test_personajes_propios(client):
    bad = client.post("/avatars", files={"file": ("x.glb", io.BytesIO(b"no es glb"))}, data={"name": "Ana"})
    assert bad.status_code == 400
    glb = b"glTF" + b"\x02\x00\x00\x00" + b"\x00" * 16
    saved = client.post("/avatars", files={"file": ("ana.glb", io.BytesIO(glb))},
                        data={"name": "Ana Pérez", "body": "F", "license": "propio"}).json()
    assert saved["id"] == "propio-ana-perez" and (config.AVATARS_DIR / saved["file"]).exists()
    listed = client.get("/avatar/avatars.json").json()
    assert listed[-1]["id"] == saved["id"] and listed[-1]["custom"] is True
    assert len(listed) == 6  # los cinco de ejemplo más el propio
    assert client.delete(f"/avatars/{saved['id']}").status_code == 200
    assert client.delete("/avatars/brunette").status_code == 404  # los de ejemplo no se borran


def test_historial_csv(client):
    ask(client, "Hola")
    resp = client.get("/history.csv")
    assert resp.status_code == 200 and "attachment" in resp.headers["content-disposition"]


def test_eval_con_casos(client):
    upload(client, "servicios.md", LIBRARY, publish=True)
    config.EVAL_FILE.write_text(json.dumps({"pregunta": "¿Horario de la biblioteca?", "idioma": "es",
                                            "debe_responder": True, "esperado": ["7:00"]}) + "\n",
                                encoding="utf-8")
    [case] = client.post("/eval").json()
    assert case["passed"] is True


@pytest.mark.parametrize("url, ok", [
    ("https://teams.live.com/meet/123", True),
    ("https://teams.microsoft.com/l/meetup-join/abc", True),
    ("https://evilteams.live.com/meet/123", False),
    ("http://teams.live.com/meet/123", False),
    ("https://teams.live.com.evil.com/meet", False),
])
def test_enlaces_de_teams(url, ok):
    assert is_teams_link(url) is ok
