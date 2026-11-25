"""Descarga three.js a web/vendor/three/ para que la página del avatar funcione sin internet.

Uso:  python -m scripts.vendorizar_three

Baja los archivos que importa TalkingHead y, de forma recursiva, los que importan ellos
(imports relativos), con la misma estructura que el paquete de npm. Ya se dejó hecho en el
repositorio; solo hace falta repetirlo para cambiar de versión de three.js (VERSION abajo y
en web/vendor/three/VERSION.txt).
"""
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests

VERSION = "0.186.0"
BASE = f"https://cdn.jsdelivr.net/npm/three@{VERSION}/"
TARGET = Path(__file__).resolve().parent.parent / "web" / "vendor" / "three"
ENTRIES = [
    "build/three.module.js",
    "examples/jsm/controls/OrbitControls.js",
    "examples/jsm/loaders/GLTFLoader.js",
    "examples/jsm/loaders/DRACOLoader.js",
    "examples/jsm/libs/meshopt_decoder.module.js",
    "examples/jsm/loaders/FBXLoader.js",
    "examples/jsm/environments/RoomEnvironment.js",
    "examples/jsm/libs/stats.module.js",
]
IMPORT = re.compile(r"""(?:import|export)\s[^'"]*?from\s*['"](\.{1,2}/[^'"]+)['"]|import\s*['"](\.{1,2}/[^'"]+)['"]""")


def main() -> int:
    pending, done = list(ENTRIES), set()
    while pending:
        rel = pending.pop()
        if rel in done:
            continue
        done.add(rel)
        resp = requests.get(BASE + rel, timeout=60)
        resp.raise_for_status()
        path = TARGET / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(resp.content)
        for match in IMPORT.finditer(resp.text):
            relative = match.group(1) or match.group(2)
            pending.append(urljoin(rel, relative))
        print(f"{len(resp.content) / 1024:8.1f} KB  {rel}")
    license_resp = requests.get(BASE + "LICENSE", timeout=60)
    license_resp.raise_for_status()
    (TARGET / "LICENSE").write_bytes(license_resp.content)
    (TARGET / "VERSION.txt").write_text(f"three.js {VERSION} (MIT), descargado de {BASE}\n", encoding="utf-8")
    print(f"Listo: {len(done)} archivos en {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
