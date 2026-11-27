"""Conexión directa a una reunión de Teams, sin OBS ni cables de audio: Playwright abre un
navegador con el avatar y otro con Teams web, y app/teams_puente.js entrega a Teams la imagen
y la voz del asistente como cámara y micrófono.

El asistente entra siempre como invitado: nunca abre la aplicación de Teams instalada ni usa
una cuenta de esta computadora (si el navegador inicia sesión solo o la reunión lo exige, se
cancela), y no se oculta la automatización ni se intenta pasar verificaciones.

Uso desde la API:  join(url, perfil, nombre) / leave() / status()
"""
import logging
import os
import re
import threading
import time
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

from . import config

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:  # sin Playwright la API funciona igual; solo no puede entrar a reuniones
    sync_playwright = None

    class PlaywrightError(Exception):
        pass

log = logging.getLogger("uvicorn.error")

API_URL = config.API_URL
INJECT = Path(__file__).with_name("teams_puente.js")
# Navegadores a probar, en orden. Con TEAMS_BROWSER=chromium se usa el Chromium propio de
# Playwright (hay que instalarlo con "playwright install chromium"), que no conoce las cuentas
# de Windows; Chrome y Edge sí pueden intentar iniciar sesión solos, y por eso se vigila abajo.
CHANNELS = [c for c in (os.getenv("TEAMS_BROWSER"), "chrome", "msedge") if c]
GUEST_ONLY = ("El asistente solo entra como invitado y nunca con una cuenta de esta computadora, "
              "así que canceló la entrada.")
# Diagnóstico (TEAMS_CAPTURAS en .env): carpeta donde cada pocos segundos se guarda una captura de
# Teams y el estado del puente. Sirve para ver en qué pantalla se atoró si Microsoft cambia la página.
DEBUG_DIR = Path(config.TEAMS_CAPTURAS) if config.TEAMS_CAPTURAS else None

# Comunes a los dos navegadores: siguen dibujando aunque otra ventana los tape, permiten audio
# sin que nadie pulse nada, y no sacan sonido por las bocinas de esta máquina.
COMMON_ARGS = [
    "--autoplay-policy=no-user-gesture-required",
    "--disable-features=CalculateNativeWinOcclusion,WebRtcHideLocalIpsWithMdns",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-background-timer-throttling",
    "--mute-audio",
]
# El de la reunión arranca con cámara y micrófono falsos y sin preguntar por el permiso:
# Teams ve dispositivos normales y teams_puente.js cambia lo que capturan. Va en inglés para
# que los textos de los botones sean siempre los mismos.
MEETING_ARGS = COMMON_ARGS + ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--lang=en-US"]

# Selectores de Teams web, reunidos de bots de código abierto (Attendee, Vexa, Recall,
# ScreenApp). Se prueban en orden; Microsoft los cambia de vez en cuando.
CONTINUE_IN_BROWSER = [
    'button[data-tid="joinOnWeb"]',
    'button[aria-label="Join meeting from this browser"]',
    'button[aria-label="Continue on this browser"]',
    'button[aria-label="Join on this browser"]',
    'button:has-text("Continue on this browser")',
    'button:has-text("Join from browser")',
]
NAME_INPUT = ['input[data-tid="prejoin-display-name-input"]', 'input[placeholder="Type your name"]']
JOIN_BUTTON = ['[data-tid="prejoin-join-button"]', 'button:has-text("Join now")']
PREJOIN_CAMERA = ['[data-tid="toggle-video"]']
PREJOIN_MIC = ['[data-tid="toggle-mute"]']
NO_DEVICES_MODAL = ['button:has-text("Continue without audio or video")']
NOT_STARTED = ['text=/let you in when the meeting starts/i']
LOBBY = ['text=/Someone will let you in (shortly|soon)/i', 'text=/let you in/i']
IN_MEETING = ['button#hangup-button', 'button[data-tid="hangup-main-btn"]', '#callingButtons-showMoreBtn']
HANGUP = ['button#hangup-button', '[data-inp="hangup-button"]', 'button[data-tid="hangup-main-btn"]']
CAMERA_OFF = ['button#video-button[aria-label*="Turn camera on" i]']
MIC_OFF = ['button#microphone-button[aria-label*="Unmute" i]', 'button#mic-button[aria-label*="Unmute" i]']
DENIED = ['text=/denied access to the meeting/i', 'text=/request to join was declined/i']
REMOVED = ['#calling-retry-screen-title', 'text=/removed from (this|the) meeting/i']
TEAMS_HOSTS = ("teams.microsoft.com", "teams.live.com", "teams.cloud.microsoft", "teams.microsoft.us")
# Fuera de estos sitios (y de la reunión simulada de las pruebas) la página es un inicio de sesión.
MEETING_HOSTS = TEAMS_HOSTS + (urlparse(API_URL).hostname or "127.0.0.1",)
SIGN_IN = ['input[name="loginfmt"]', 'text=/To join, sign in/i', 'text=/verify your info before you can join/i']
HUMAN_CHECK = ['text=/Verify you.re a real person/i']


def meeting_url(url: str) -> str:
    """Agrega los parámetros que piden la versión web directamente, sin la pantalla de 'abrir la app'."""
    parts = urlparse(url)
    if "/l/meetup-join/" not in parts.path and "/meet/" not in parts.path:
        return url
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({"msLaunch": "false", "type": "meetup-join", "directDl": "true",
                  "enableMobilePage": "true", "suppressPrompt": "true"})
    return urlunparse(parts._replace(query=urlencode(query)))


def safe_name(name: str) -> str:
    """Teams solo acepta letras, números, espacios y - ' . _ @ en el nombre; con otro signo no deja entrar."""
    cleaned = re.sub(r"[^\w\s\-'.@]", " ", name, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip() or "Asistente"


def launch(pw, args, **options):
    """Abre Chrome o Edge (el que haya) con ventana visible."""
    last = None
    for channel in CHANNELS:
        try:
            return pw.chromium.launch(channel=None if channel == "chromium" else channel,
                                      headless=False, args=args, **options)
        except PlaywrightError as error:
            last = error
    raise RuntimeError(f"No se pudo abrir Chrome ni Edge: {last}")


def open_avatar(pw, profile: str):
    """Abre la página del avatar en modo puente y espera a que esté lista."""
    browser = launch(pw, COMMON_ARGS + ["--window-size=1296,820", "--window-position=40,40"])
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    page.goto(f"{API_URL}/avatar/?puente=1&perfil={quote(profile)}")
    page.wait_for_function("window.puente", timeout=120_000)
    return browser, page


def open_meeting(pw, url: str):
    """Abre la pestaña de la reunión con el puente inyectado. Devuelve (lo que hay que cerrar, la página).

    La ventana no tiene perfil (como una de incógnito) y no guarda nada al cerrarse.
    """
    browser = launch(pw, MEETING_ARGS + ["--window-size=1300,860", "--window-position=120,80"])
    context = browser.new_context(
        viewport={"width": 1280, "height": 760}, permissions=["camera", "microphone"], locale="en-US")
    context.add_init_script(path=str(INJECT))
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded")
    return browser, page


def ensure_bridge(avatar, meeting) -> bool:
    """Conecta (o reconecta) el puente si la pestaña de la reunión no lo tiene.

    Teams recarga la página varias veces antes de entrar, y cada recarga lo pierde.
    """
    try:
        state = meeting.evaluate("window.__tecPuente ? window.__tecPuente.status().connection : null")
        if state is None or state in ("connecting", "connected", "new"):
            return state == "connected"
        offer = avatar.evaluate("window.puente.offer()")
        answer = meeting.evaluate("offer => window.__tecPuente.accept(offer)", offer)
        avatar.evaluate("answer => window.puente.finish(answer)", answer)
        return True
    except PlaywrightError as error:  # la página estaba navegando: se reintenta en la siguiente vuelta
        log.info("puente: reintento (%s)", str(error).splitlines()[0])
        return False


def first_visible(page, selectors):
    """Primer elemento visible de una lista de selectores, en la página o en sus marcos."""
    for frame in page.frames:
        for selector in selectors:
            try:
                locator = frame.locator(selector).first
                if locator.is_visible():
                    return locator
            except PlaywrightError:
                continue
    return None


def click_if_visible(page, selectors) -> bool:
    target = first_visible(page, selectors)
    if not target:
        return False
    try:
        target.click(timeout=3000)
        return True
    except PlaywrightError:
        return False


def turn_on(page, selectors) -> None:
    """Enciende un interruptor de la pantalla previa (cámara o micrófono) si está apagado."""
    toggle = first_visible(page, selectors)
    if not toggle:
        return
    try:
        state = toggle.get_attribute("aria-checked") or toggle.get_attribute("aria-pressed")
        on = state == "true" if state in ("true", "false") else toggle.is_checked()
        if not on:
            toggle.click(timeout=3000)
    except PlaywrightError:
        pass


class Session(threading.Thread):
    """Una reunión en curso. Todo Playwright corre en este hilo, que es el que lo creó."""

    def __init__(self, url: str, profile: str, name: str):
        super().__init__(daemon=True, name="reunion-teams")
        self.url, self.profile, self.name_shown = url, profile, safe_name(name)
        self.stop_requested = threading.Event()
        self.state = "starting"   # starting, joining, needs_user, lobby, in_meeting, ended, error
        self.detail = "Abriendo los navegadores…"
        self.started = time.time()
        self.finished = None

    def set(self, state: str, detail: str) -> None:
        if (state, detail) != (self.state, self.detail):
            log.info("reunion: %s - %s", state, detail)
        self.state, self.detail = state, detail

    def info(self) -> dict:
        return {"state": self.state, "detail": self.detail, "url": self.url, "profile": self.profile,
                "name": self.name_shown, "seconds": int((self.finished or time.time()) - self.started),
                "active": self.is_alive()}

    def run(self) -> None:
        try:
            with sync_playwright() as pw:
                self._run(pw)
            if self.state not in ("error", "ended"):
                self.set("ended", "El asistente salió de la reunión.")
        except Exception as error:  # noqa: BLE001  (cualquier fallo debe verse en la consola)
            log.exception("reunion: error")
            self.set("error", str(error).splitlines()[0])
        finally:
            self.finished = time.time()

    def _run(self, pw) -> None:
        avatar_browser, avatar = open_avatar(pw, self.profile)
        context, meeting = open_meeting(pw, meeting_url(self.url))
        self.set("joining", "Entrando a la reunión…")
        typed_name = clicked_join = greeted = False
        inside_since = signed_in_since = 0.0
        try:
            while not self.stop_requested.is_set():
                if meeting.is_closed() or avatar.is_closed():
                    self.set("ended", "Se cerró una de las ventanas del asistente (la de Teams o la del avatar).")
                    return
                ensure_bridge(avatar, meeting)
                self._debug(avatar, meeting)

                host = urlparse(meeting.url).hostname or ""
                if (host and not host.endswith(MEETING_HOSTS)) or first_visible(meeting, SIGN_IN):
                    self.set("ended", f"Esta reunión exige iniciar sesión ({host}). {GUEST_ONLY}")
                    return
                # Sin haber escrito un nombre de invitado, un botón de unirse o estar ya dentro significa
                # que el navegador inició sesión solo con una cuenta de esta computadora.
                if not typed_name and not first_visible(meeting, NAME_INPUT) and (
                        first_visible(meeting, JOIN_BUTTON) or first_visible(meeting, IN_MEETING)):
                    signed_in_since = signed_in_since or time.time()
                    if time.time() - signed_in_since > 4:
                        click_if_visible(meeting, HANGUP)
                        self.set("ended", f"El navegador inició sesión solo con una cuenta de esta computadora. {GUEST_ONLY}")
                        return
                    self.stop_requested.wait(1.0)
                    continue
                signed_in_since = 0.0
                if first_visible(meeting, HUMAN_CHECK):
                    self.set("needs_user", "Teams pide comprobar que hay una persona. Resuélvelo en la ventana de Teams.")
                elif first_visible(meeting, DENIED):
                    self.set("ended", "No admitieron al asistente en la reunión.")
                    return
                elif first_visible(meeting, REMOVED):
                    self.set("ended", "Sacaron al asistente de la reunión o la reunión terminó.")
                    return
                elif first_visible(meeting, NOT_STARTED):
                    self.set("lobby", "La reunión todavía no empieza: entra tú primero y luego admite al asistente.")
                elif first_visible(meeting, LOBBY):
                    self.set("lobby", "En la sala de espera: alguien debe admitir al asistente.")
                elif first_visible(meeting, IN_MEETING) and not first_visible(meeting, JOIN_BUTTON):
                    if not inside_since:
                        inside_since = time.time()
                        self.set("in_meeting", "El asistente está en la reunión.")
                    # Durante los primeros segundos enciende cámara y micrófono si entró con ellos apagados.
                    if time.time() - inside_since < 20:
                        click_if_visible(meeting, CAMERA_OFF)
                        click_if_visible(meeting, MIC_OFF)
                    if not greeted and time.time() - inside_since > 3:
                        avatar.evaluate("window.puente.greet()")
                        greeted = True
                elif inside_since:
                    self.set("ended", "La reunión terminó.")
                    return
                elif clicked_join:
                    if first_visible(meeting, NO_DEVICES_MODAL):
                        self.set("needs_user", "Teams no encontró cámara ni micrófono. Revisa la ventana de Teams.")
                elif not click_if_visible(meeting, CONTINUE_IN_BROWSER):
                    name = first_visible(meeting, NAME_INPUT)
                    if name and not typed_name:
                        name.fill(self.name_shown)
                        typed_name = True
                    join = first_visible(meeting, JOIN_BUTTON)
                    if join and typed_name and join.is_enabled():
                        turn_on(meeting, PREJOIN_CAMERA)
                        turn_on(meeting, PREJOIN_MIC)
                        join.click()
                        clicked_join = True
                        self.set("joining", "Pidiendo entrar a la reunión…")
                self.stop_requested.wait(1.0)

            if click_if_visible(meeting, HANGUP):
                meeting.wait_for_timeout(1500)
        finally:
            for closeable in (context, avatar_browser):
                try:
                    closeable.close()
                except PlaywrightError:
                    pass


    def _debug(self, avatar, meeting) -> None:
        if not DEBUG_DIR or time.time() - getattr(self, "_last_debug", 0) < 4:
            return
        self._last_debug = time.time()
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            meeting.screenshot(path=str(DEBUG_DIR / "teams.png"), timeout=5000)
            bridge = meeting.evaluate("window.__tecPuente ? window.__tecPuente.status() : null")
            buttons = meeting.evaluate("""() => [...document.querySelectorAll('#video-button, #microphone-button, #mic-button, [data-tid="toggle-video"], [data-tid="toggle-mute"]')]
                .map(b => `${b.id || b.dataset.tid}: label=${b.getAttribute('aria-label')} disabled=${b.disabled ?? ''}/${b.getAttribute('aria-disabled')} checked=${b.getAttribute('aria-checked') ?? b.checked}`)""")
            frames = [frame.url[:120] for frame in meeting.frames]
            (DEBUG_DIR / "teams.txt").write_text(
                f"{self.state} | {self.detail}\nurl: {meeting.url}\npuente: {bridge}\n"
                f"avatar: {avatar.evaluate('({...window.puente.info, status: window.puente.state.status})')}\n"
                f"marcos: {frames}\nbotones: {buttons}\n", encoding="utf-8")
        except PlaywrightError as error:
            log.info("captura: %s", str(error).splitlines()[0])


_current: Session | None = None
_lock = threading.Lock()


def join(url: str, profile: str, name: str) -> dict:
    global _current
    if sync_playwright is None:
        raise ValueError("Falta Playwright: ejecuta pip install -r requirements.txt")
    with _lock:
        if _current and _current.is_alive():
            raise ValueError("El asistente ya está en una reunión. Sácalo antes de entrar a otra.")
        _current = Session(url, profile, name)
        _current.start()
        return _current.info()


def leave() -> dict:
    with _lock:
        if _current and _current.is_alive():
            _current.stop_requested.set()
            _current.set(_current.state, "Saliendo de la reunión…")
        return status()


def status() -> dict:
    return _current.info() if _current else {"state": "idle", "detail": "Sin reunión.", "active": False}
