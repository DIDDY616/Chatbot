"""Prepara OBS para usar el avatar como cámara en Teams.

Crea en OBS una colección de escenas y un perfil llamados "Asistente Tec" (1280x720, 30 fps)
con una captura de la ventana del avatar en modo reunión. No toca las escenas ni los perfiles
que ya existan. Después, scripts/camara_obs.bat abre OBS con ellos y enciende la cámara virtual.

Uso:  python scripts/preparar_obs.py            (no hace nada si ya estaban creados)
      python scripts/preparar_obs.py --rehacer  (vuelve a crear los de "Asistente Tec")
"""
import json
import os
import sys
import uuid
from pathlib import Path

NAME = "Asistente Tec"
FILE = "Asistente_Tec"
WINDOW_TITLE = "Asistente Tec - Reunion"  # título fijo de la ventana del avatar (web/app.js)
WIDTH, HEIGHT, FPS = 1280, 720, 30
MAIN_CANVAS = "6c69626f-6273-4c00-9d88-c5136d61696e"  # identificador fijo del lienzo principal de OBS

BROWSERS = [  # mismo orden que scripts/avatar_reunion.bat
    (r"%ProgramFiles%\Google\Chrome\Application\chrome.exe", "chrome.exe"),
    (r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe", "chrome.exe"),
    (r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe", "chrome.exe"),
    (r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe", "msedge.exe"),
    (r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe", "msedge.exe"),
]


def browser_exe() -> str:
    for path, exe in BROWSERS:
        if Path(os.path.expandvars(path)).exists():
            return exe
    return "msedge.exe"


def source_base(name: str, kind: str, settings: dict) -> dict:
    return {
        "name": name, "uuid": str(uuid.uuid4()), "id": kind, "versioned_id": kind, "settings": settings,
        "mixers": 0, "sync": 0, "flags": 0, "volume": 1.0, "balance": 0.5, "enabled": True, "muted": False,
        "push-to-mute": False, "push-to-mute-delay": 0, "push-to-talk": False, "push-to-talk-delay": 0,
        "hotkeys": {}, "deinterlace_mode": 0, "deinterlace_field_order": 0, "monitoring_type": 0,
        "private_settings": {},
    }


def scene_collection() -> dict:
    capture = source_base("Avatar", "window_capture", {
        "window": f"{WINDOW_TITLE}:Chrome_WidgetWin_1:{browser_exe()}",
        "priority": 1,        # busca la ventana por su título
        "method": 2,          # Windows Graphics Capture: sirve para ventanas con aceleración gráfica
        "cursor": False,
        "client_area": True,  # sin la barra de título
    })
    item = {
        "name": "Avatar", "source_uuid": capture["uuid"], "visible": True, "locked": True, "rot": 0.0,
        "align": 5, "id": 1, "group_item_backup": False,
        "pos": {"x": 0.0, "y": 0.0}, "scale": {"x": 1.0, "y": 1.0},
        "bounds_type": 3,     # escala hasta llenar el lienzo; lo que sobre queda fuera
        "bounds_align": 8,    # pegado abajo: lo que sobra es la barra de título del navegador
        "bounds_crop": False, "bounds": {"x": float(WIDTH), "y": float(HEIGHT)},
        "crop_left": 0, "crop_top": 0, "crop_right": 0, "crop_bottom": 0,
        "scale_filter": "bicubic", "blend_method": "default", "blend_type": "normal",
        "show_transition": {"duration": 0}, "hide_transition": {"duration": 0}, "private_settings": {},
    }
    scene = source_base("Reunion", "scene", {"id_counter": 1, "custom_size": False, "items": [item]})
    scene["canvas_uuid"] = MAIN_CANVAS
    return {
        "name": NAME, "sources": [capture, scene], "groups": [], "scene_order": [{"name": "Reunion"}],
        "current_scene": "Reunion", "current_program_scene": "Reunion", "canvases": [],
        "current_transition": "Corte", "transition_duration": 300, "transitions": [],
        "saved_projectors": [], "preview_locked": False, "scaling_enabled": False,
        "virtual-camera": {"type2": 3}, "modules": {},
        "resolution": {"x": WIDTH, "y": HEIGHT}, "version": 2,
    }


PROFILE = f"""[General]
Name={NAME}

[Video]
BaseCX={WIDTH}
BaseCY={HEIGHT}
OutputCX={WIDTH}
OutputCY={HEIGHT}
FPSType=0
FPSCommon={FPS}
"""


def main() -> int:
    obs = Path(os.environ["APPDATA"]) / "obs-studio" / "basic"
    if not obs.is_dir():
        print("No encontré la configuración de OBS. Instala OBS Studio y ábrelo una vez.")
        return 1
    redo = "--rehacer" in sys.argv
    scenes = obs / "scenes" / f"{FILE}.json"
    profile = obs / "profiles" / FILE / "basic.ini"
    for path, write in ((scenes, lambda: json.dumps(scene_collection(), ensure_ascii=False, indent=4)), (profile, lambda: PROFILE)):
        if path.exists() and not redo:
            print(f"Ya existía, no lo toqué: {path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(write(), encoding="utf-8")
        print(f"Creado: {path}")
    print(f'Listo. En OBS aparecen como colección de escenas y perfil "{NAME}".')
    return 0


if __name__ == "__main__":
    sys.exit(main())
