import pytest

from app import documents, web_import

HTML = """<html><head><title>Ingeniería en Tecnologías Computacionales | Tec</title></head><body>
<nav>Inicio | Admisiones | Contacto</nav>
<article><h1>Ingeniería en Tecnologías Computacionales</h1>
<p>El programa forma profesionales capaces de diseñar soluciones de software y sistemas computacionales
para resolver problemas reales en organizaciones de todo tipo.</p>
<p>La carrera se cursa en ocho semestres e incluye un Semestre Tec con estancias en la industria.</p>
</article><footer>© Aviso de privacidad</footer></body></html>"""

# Una página que se arma con JavaScript: el HTML descargado solo trae el menú.
EMPTY_SHELL = "<html><head><title>Cargando</title></head><body><nav>Inicio</nav><div id='app'></div></body></html>"


@pytest.fixture
def public(monkeypatch):
    """Cualquier sitio resuelve a una IP pública; nunca se abre un navegador de verdad."""
    monkeypatch.setattr(web_import, "_resolve", lambda host: ["127.0.0.1"] if host == "localhost" else ["200.1.2.3"])

    def no_browser(url):
        raise RuntimeError("sin navegador en las pruebas")

    monkeypatch.setattr(web_import, "_render", no_browser)


@pytest.mark.parametrize("url", [
    "ftp://tec.mx/plan", "javascript:alert(1)", "http://127.0.0.1:8000/documents", "http://10.0.0.5/intranet",
    "http://192.168.1.1/", "http://[::1]/", "http://169.254.169.254/latest/meta-data",
])
def test_rechaza_direcciones_no_publicas(url):
    with pytest.raises(ValueError):
        web_import.check_url(url)


def test_extrae_texto_principal():
    pytest.importorskip("trafilatura")
    title, text = web_import.extract(HTML, "https://tec.mx/es/ingenieria/itc")
    assert "Tecnologías Computacionales" in title
    assert "ocho semestres" in text
    assert "Aviso de privacidad" not in text


def test_limpia_nombres_de_iconos():
    text = "Plan de estudios\n\n*keyboard\\_arrow\\_down*\n\n*pin\\_drop*Singapur\n\nkeyboard_arrow_left\n\nFin"
    assert web_import.clean(text) == "Plan de estudios\n\nSingapur\n\nFin"


def test_importa_como_borrador_con_fuente(env, public, monkeypatch):
    pytest.importorskip("trafilatura")
    monkeypatch.setattr(web_import, "_download", lambda url: (HTML, url))
    saved = web_import.import_url("https://tec.mx/es/ingenieria/itc", "ITC")
    assert saved["published"] is False and saved["chunks"] >= 1
    # trafilatura quita del título el nombre del sitio (" | Tec") y el nombre pierde los acentos.
    assert saved["source"] == "ITC/web-ingenieria-en-tecnologias-computacionales.md"
    [text] = documents.chunks(saved["source"])
    assert text.startswith("Fuente: https://tec.mx/es/ingenieria/itc")


def test_pagina_con_javascript_se_arma_con_navegador(env, public, monkeypatch):
    pytest.importorskip("trafilatura")
    monkeypatch.setattr(web_import, "_download", lambda url: (EMPTY_SHELL, url))
    monkeypatch.setattr(web_import, "_render", lambda url: HTML)
    saved = web_import.import_url("https://tec.mx/es/dinamica", "general")
    assert "ocho semestres" in documents.chunks(saved["source"])[0]


def test_pagina_vacia_sin_navegador_falla_con_mensaje(env, public, monkeypatch):
    pytest.importorskip("trafilatura")
    monkeypatch.setattr(web_import, "_download", lambda url: (EMPTY_SHELL, url))
    with pytest.raises(ValueError, match="texto útil"):
        web_import.import_url("https://tec.mx/es/dinamica", "general")
    assert documents.list_documents() == []


def test_una_redireccion_a_la_red_interna_se_rechaza(env, public, monkeypatch):
    monkeypatch.setattr(web_import, "_download", lambda url: (HTML, "http://localhost/secreto"))
    with pytest.raises(ValueError):
        web_import.import_url("https://tec.mx/redirige", "general")
    assert documents.list_documents() == []


def test_ruta_de_la_api(env, public, monkeypatch):
    pytest.importorskip("trafilatura")
    from fastapi.testclient import TestClient

    from app.api import create_app

    monkeypatch.setattr(web_import, "_download", lambda url: (HTML, url))
    with TestClient(create_app()) as client:
        ok = client.post("/documents/from-url", json={"url": "https://tec.mx/es/itc", "category": "ITC"})
        assert ok.status_code == 200 and ok.json()["published"] is False
        bad = client.post("/documents/from-url", json={"url": "http://127.0.0.1/x"})
        assert bad.status_code == 400
