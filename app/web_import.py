"""Importar páginas web oficiales a la base de conocimiento.

La mayor parte de la información institucional (programas, planes de estudio, servicios,
becas) ya está publicada en páginas web. En vez de copiarla a mano, el administrador pega el
enlace: se descarga la página, trafilatura extrae solo el texto principal (sin menús, pies de
página ni anuncios) y se guarda como un documento Markdown en borrador, con la fuente y la
fecha de consulta al inicio. Así se revisa en la consola antes de publicarlo.

Si la página trae muy poco texto (se arma con JavaScript), se abre con Chrome o Edge sin
ventana, mediante Playwright (el mismo que usa la conexión a Teams), y se extrae de nuevo.
Para PDF y Word conviene descargarlos y subirlos como documento.

Por seguridad solo se aceptan direcciones http(s) públicas: nada de localhost ni de redes
internas, para que nadie use el servidor para leer páginas privadas de la red.
"""
import ipaddress
import re
import socket
from datetime import date
from urllib.parse import urlparse

from . import documents

MAX_BYTES = 5 * 1024 * 1024
MIN_STATIC_CHARS = 400  # con menos texto que esto se intenta armar la página con un navegador
USER_AGENT = "AsistenteTec/0.2 (importador de paginas para una base de conocimiento)"


def _resolve(host: str) -> list[str]:
    return [info[4][0] for info in socket.getaddrinfo(host, None)]


def check_url(url: str) -> None:
    """Rechaza lo que no sea una dirección http(s) pública."""
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("El enlace debe empezar con http:// o https://")
    try:
        ipaddress.ip_address(parts.hostname)
        addresses = [parts.hostname]  # una IP escrita en el enlace se revisa tal cual
    except ValueError:
        addresses = None
    try:
        addresses = addresses or _resolve(parts.hostname)
    except OSError as error:
        raise ValueError(f"No se encontró el sitio {parts.hostname}") from error
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("Solo se pueden importar páginas públicas de internet")


def _download(url: str) -> tuple[str, str]:
    """(HTML, dirección final tras redirecciones)."""
    import requests

    with requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT}, stream=True) as resp:
        resp.raise_for_status()
        if "html" not in resp.headers.get("Content-Type", "text/html"):
            raise ValueError("El enlace no es una página web (para PDF o Word, descárgalo y súbelo como documento)")
        content = b""
        for block in resp.iter_content(65536):
            content += block
            if len(content) > MAX_BYTES:
                raise ValueError("La página es demasiado grande")
        return content.decode(resp.encoding or "utf-8", errors="replace"), resp.url


def _render(url: str) -> str:
    """HTML de la página ya armada por su JavaScript, con Chrome o Edge sin ventana."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        last = None
        for channel in ("msedge", "chrome", None):
            try:
                browser = pw.chromium.launch(channel=channel, headless=True)
                break
            except Exception as error:  # noqa: BLE001
                last = error
        else:
            raise ValueError(f"No se pudo abrir un navegador para armar la página: {last}")
        try:
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, wait_until="load", timeout=60_000)
            page.wait_for_timeout(3000)  # deja que el JavaScript termine de pintar el contenido
            return page.content()
        finally:
            browser.close()


# Nombres de íconos de Material ("keyboard_arrow_down", "pin_drop") que quedan como texto suelto.
ICON = re.compile(r"\*[a-z]+(?:\\?_[a-z]+)+\*|^[a-z]+(?:\\?_[a-z]+)+$", re.MULTILINE)


def clean(text: str) -> str:
    text = ICON.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract(html: str, url: str) -> tuple[str, str]:
    """(título, texto principal en Markdown)."""
    import trafilatura

    text = trafilatura.extract(html, url=url, output_format="markdown", include_tables=True,
                               include_links=False, include_comments=False) or ""
    text = clean(text)
    if len(text) < 40:
        raise ValueError("No se encontró texto útil en la página")
    meta = trafilatura.extract_metadata(html, default_url=url)
    title = (meta.title if meta and meta.title else "") or urlparse(url).path.strip("/") or urlparse(url).hostname
    return title.strip(), text


def _filename(title: str) -> str:
    return f"web-{documents.slugify(title, 'pagina')}.md"


def import_url(url: str, category: str, publish: bool = False) -> dict:
    """Descarga la página, la guarda como documento y lo indexa (en borrador si no se publica)."""
    url = url.strip()
    check_url(url)
    html, final_url = _download(url)
    check_url(final_url)  # una redirección no puede llevar a una dirección interna
    try:
        title, text = extract(html, final_url)
    except ValueError:
        title, text = "", ""
    if len(text) < MIN_STATIC_CHARS:
        # Poco texto: la página probablemente se arma con JavaScript. Se intenta con un navegador.
        try:
            rendered = extract(_render(final_url), final_url)
            if len(rendered[1]) > len(text):
                title, text = rendered
        except Exception as error:  # noqa: BLE001
            if not text:
                raise ValueError(f"No se encontró texto útil en la página ({error})") from error
    heading = "" if text.lstrip().startswith("# ") else f"# {title}\n\n"  # trafilatura a veces ya lo trae
    body = f"Fuente: {final_url}\nConsultado: {date.today().isoformat()}\n\n{heading}{text}\n"
    saved = documents.save(_filename(title), category, body.encode("utf-8"), publish)
    return {**saved, "title": title, "url": final_url}
