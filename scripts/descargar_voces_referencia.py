"""Descarga los audios de referencia de la demo oficial de Chatterbox (uno por idioma).

Uso:  python -m scripts.descargar_voces_referencia
Los guarda como .wav en data/voces_clonadas/ con el idioma como prefijo (es_..., en_...).
"""
import io

import requests
import soundfile as sf

from app import config

BASE = "https://storage.googleapis.com/chatterbox-demo-samples/mtl_prompts"
CLIPS = ["es_f1", "es_m1", "en_f1", "en_m1", "fr_f1", "fr_m1", "de_f1", "de_m1", "sv_f", "sv_m"]

config.CLONE_DIR.mkdir(parents=True, exist_ok=True)
for clip in CLIPS:
    resp = requests.get(f"{BASE}/{clip}.flac", timeout=60)
    if resp.status_code != 200:
        print(f"no existe  {clip}")
        continue
    audio, rate = sf.read(io.BytesIO(resp.content))
    lang, kind = clip.split("_")
    name = f"{lang}_demo-{'femenina' if kind.startswith('f') else 'masculina'}"
    sf.write(config.CLONE_DIR / f"{name}.wav", audio, rate)
    print(f"descargada {name}.wav  ({len(audio) / rate:.0f} s)")
