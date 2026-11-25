"""Personajes 3D: los cinco de ejemplo (web/avatars.json) más los que se suben desde la consola.

Los subidos se guardan en web/avatars/ (el archivo) y data/personajes.json (sus datos), así
web/avatars.json queda intacto y una actualización del proyecto no borra los propios.

TalkingHead necesita un .glb con esqueleto tipo Mixamo, las 52 formas de ARKit y los 15
visemas de Oculus. Ready Player Me, Avaturn y Avatar SDK los exportan así.
"""
import json
import threading

from . import config

BUILTIN_FILE = config.WEB_DIR / "avatars.json"
GLB_MAGIC = b"glTF"
BODIES = ("F", "M")
_lock = threading.Lock()


def _custom() -> list[dict]:
    if not config.CUSTOM_AVATARS_FILE.exists():
        return []
    return json.loads(config.CUSTOM_AVATARS_FILE.read_text(encoding="utf-8") or "[]")


def _write_custom(items: list[dict]) -> None:
    config.CUSTOM_AVATARS_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.CUSTOM_AVATARS_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def list_all() -> list[dict]:
    builtin = json.loads(BUILTIN_FILE.read_text(encoding="utf-8"))
    return builtin + [{**a, "custom": True} for a in _custom()]


def _slug(name: str) -> str:
    from .documents import slugify

    return slugify(name, "personaje", 40)


def add(name: str, content: bytes, body: str = "F", license_text: str = "") -> dict:
    """Agrega un personaje subido. Comprueba que sea un .glb (glTF binario)."""
    name = name.strip()
    if not name:
        raise ValueError("Falta el nombre del personaje")
    if body not in BODIES:
        raise ValueError("El cuerpo debe ser F o M")
    if content[:4] != GLB_MAGIC:
        raise ValueError("El archivo no es un .glb válido (glTF binario)")
    if len(content) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(f"El archivo pasa de {config.MAX_UPLOAD_MB} MB")
    with _lock:
        taken = {a["id"] for a in list_all()}
        base = f"propio-{_slug(name)}"
        avatar_id, n = base, 2
        while avatar_id in taken:
            avatar_id, n = f"{base}-{n}", n + 1
        config.AVATARS_DIR.mkdir(parents=True, exist_ok=True)
        (config.AVATARS_DIR / f"{avatar_id}.glb").write_bytes(content)
        entry = {"id": avatar_id, "name": name, "file": f"{avatar_id}.glb",
                 "license": license_text.strip() or "Personaje propio", "options": {"body": body}}
        _write_custom(_custom() + [entry])
    return entry


def delete(avatar_id: str) -> None:
    """Borra un personaje propio. Los de ejemplo no se pueden borrar desde aquí."""
    with _lock:
        items = _custom()
        match = next((a for a in items if a["id"] == avatar_id), None)
        if match is None:
            raise KeyError(f"No hay un personaje propio con el identificador '{avatar_id}'")
        _write_custom([a for a in items if a["id"] != avatar_id])
        (config.AVATARS_DIR / match["file"]).unlink(missing_ok=True)
