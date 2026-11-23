"""Descarga los personajes 3D de ejemplo del proyecto TalkingHead a web/avatars/.

Uso:  python -m scripts.descargar_avatares
Licencias: mpfb.glb es CC0; los demás son solo para uso no comercial (ver web/avatars.json).
"""
import requests

from app import config

BASE = "https://raw.githubusercontent.com/met4citizen/TalkingHead/v1.8.2/avatars"
FILES = ["mpfb.glb", "avaturn.glb", "avatarsdk.glb", "brunette.glb", "vroid.glb"]

out = config.WEB_DIR / "avatars"
out.mkdir(parents=True, exist_ok=True)
for name in FILES:
    resp = requests.get(f"{BASE}/{name}", timeout=300)
    resp.raise_for_status()
    if resp.content[:4] != b"glTF":
        raise SystemExit(f"{name}: la descarga no es un archivo GLB válido")
    (out / name).write_bytes(resp.content)
    print(f"{name}  {len(resp.content) / 2**20:.1f} MB")
