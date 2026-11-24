"""Prueba la conexión directa contra una reunión simulada (sin Teams).

Abre los dos navegadores como en una reunión real, pero la "reunión" es
web/pruebas/reunion_falsa.html. Comprueba que:
- la página de la reunión recibe la imagen del avatar como cámara;
- recibe la voz del asistente como micrófono;
- el asistente oye a un participante y contesta cuando dicen su nombre.

Uso:  python -m tests.puente [carpeta para guardar capturas]     (con la API encendida)
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from app import teams

FAKE_MEETING = f"{teams.API_URL}/avatar/pruebas/reunion_falsa.html"


def wait_until(check, seconds: float, step: float = 0.5):
    deadline = time.time() + seconds
    while time.time() < deadline:
        value = check()
        if value:
            return value
        time.sleep(step)
    return check()


def main() -> int:
    shots = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    failures = 0

    def check(label: str, ok: bool, detail="") -> None:
        nonlocal failures
        failures += not ok
        print(f"{'OK   ' if ok else 'FALLA'} {label} {detail}")

    with sync_playwright() as pw:
        avatar_browser, avatar = teams.open_avatar(pw, "tecbot")
        context, meeting = teams.open_meeting(pw, FAKE_MEETING)
        try:
            wait_until(lambda: teams.ensure_bridge(avatar, meeting), 30)
            meeting.wait_for_function("window.prueba", timeout=40_000)

            print("dispositivos:", meeting.evaluate("window.prueba.dispositivos"))
            tracks = meeting.evaluate("window.prueba.pistas()")
            print("pistas:", [(t["kind"], t["label"], t["state"]) for t in tracks])
            check("puente conectado", meeting.evaluate("window.__tecPuente.status().connection") == "connected",
                  meeting.evaluate("window.__tecPuente.status()"))
            check("pistas de cámara y micrófono vivas", len(tracks) == 2 and all(t["state"] == "live" for t in tracks))

            video = wait_until(lambda: (v := meeting.evaluate("window.prueba.video()"))["width"] and v, 20)
            check("llega video del avatar", bool(video) and video["width"] == 1280 and video["height"] == 720, video)
            before = meeting.evaluate("window.prueba.video().time")
            time.sleep(2)
            check("el video avanza", meeting.evaluate("window.prueba.video().time") > before + 1)

            # Saludo: la voz del asistente debe llegar por el "micrófono" de la reunión.
            meeting.evaluate("window.prueba.nivel(true)")
            avatar.evaluate("window.puente.greet()")
            wait_until(lambda: avatar.evaluate("window.puente.state.status") == "speaking", 30)
            time.sleep(2.5)
            level = meeting.evaluate("window.prueba.nivel(true)")
            check("llega la voz del asistente", level > 0.01, f"nivel {level:.3f}")
            if shots:
                meeting.screenshot(path=str(shots / "reunion_hablando.png"))
            wait_until(lambda: avatar.evaluate("window.puente.state.status") == "idle", 30)

            # Un participante habla sin nombrarlo: no debe contestar.
            turn = avatar.evaluate("window.puente.state.turn")
            duration = meeting.evaluate("window.prueba.decir('Yo creo que la reunión del martes estuvo muy bien.')")
            time.sleep(duration + 4)
            check("ignora una frase sin su nombre", avatar.evaluate("window.puente.state.turn") == turn)

            # Lo nombran: debe oírlo por el puente y contestar.
            meeting.evaluate("window.prueba.nivel(true)")
            duration = meeting.evaluate("window.prueba.decir('TecBot, ¿qué horario tiene la biblioteca?')")
            started = time.time()
            answered = wait_until(lambda: avatar.evaluate("window.puente.state.status") == "speaking", duration + 20, 0.2)
            delay = time.time() - started - duration
            check("contesta cuando lo nombran", bool(answered), f"{delay:.1f} s después de la pregunta")
            time.sleep(2.5)
            level = meeting.evaluate("window.prueba.nivel(true)")
            check("su respuesta llega a la reunión", level > 0.01, f"nivel {level:.3f}")
            if shots:
                meeting.screenshot(path=str(shots / "reunion_respondiendo.png"))
        finally:
            context.close()
            avatar_browser.close()

    print(f"\n{failures} fallas")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
