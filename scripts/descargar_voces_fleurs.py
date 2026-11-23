"""Más voces de referencia para Chatterbox, tomadas del conjunto abierto FLEURS (Google, CC BY 4.0).

Uso:  python -m scripts.descargar_voces_fleurs
Por cada idioma revisa los primeros clips, descarta los ruidosos y guarda dos voces
femeninas y dos masculinas con tono distinto en data/voces_clonadas/.
"""
import io
import tarfile
from pathlib import Path

import librosa
import numpy as np
import requests
import soundfile as sf

from app import config

BASE = "https://huggingface.co/datasets/google/fleurs/resolve/main/data"
CONFIGS = {"es": "es_419", "en": "en_us", "fr": "fr_fr", "de": "de_de", "sv": "sv_se"}
POOL = 80          # clips candidatos que se revisan por idioma
PER_GENDER = 2     # voces que se guardan por género
MIN_PITCH_GAP = 12  # Hz de diferencia para considerar que son personas distintas


def cleanliness_db(audio: np.ndarray, rate: int) -> float:
    """Diferencia entre las partes habladas y los silencios; mayor = grabación más limpia."""
    frame = rate // 50
    n = len(audio) // frame
    rms = np.sqrt((audio[: n * frame].reshape(n, frame) ** 2).mean(axis=1)) + 1e-9
    return float(20 * np.log10(np.percentile(rms, 90) / np.percentile(rms, 10)))


def candidates(fleurs_config: str) -> list[dict]:
    meta = {}
    for line in requests.get(f"{BASE}/{fleurs_config}/dev.tsv", timeout=60).text.splitlines():
        cols = line.split("\t")
        meta[cols[1]] = (int(cols[-2]), cols[-1].strip().upper())  # (muestras, género)

    pool = []
    with requests.get(f"{BASE}/{fleurs_config}/audio/dev.tar.gz", stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with tarfile.open(fileobj=resp.raw, mode="r|gz") as tar:  # se lee solo el inicio del archivo
            for member in tar:
                samples, gender = meta.get(Path(member.name).name, (0, ""))
                if not 8 * 16000 <= samples <= 16 * 16000 or gender not in ("FEMALE", "MALE"):
                    continue
                audio, rate = sf.read(io.BytesIO(tar.extractfile(member).read()), dtype="float32")
                pool.append({
                    "audio": audio, "rate": rate, "gender": gender,
                    "clean": cleanliness_db(audio, rate),
                    "pitch": float(np.median(librosa.yin(audio, fmin=60, fmax=350, sr=rate))),
                })
                if len(pool) >= POOL:
                    break
    return pool


config.CLONE_DIR.mkdir(parents=True, exist_ok=True)
for lang, fleurs_config in CONFIGS.items():
    pool = candidates(fleurs_config)
    for gender, label in (("FEMALE", "femenina"), ("MALE", "masculina")):
        chosen = []
        for clip in sorted((c for c in pool if c["gender"] == gender), key=lambda c: -c["clean"]):
            if all(abs(clip["pitch"] - other["pitch"]) >= MIN_PITCH_GAP for other in chosen):
                chosen.append(clip)
            if len(chosen) == PER_GENDER:
                break
        for i, clip in enumerate(chosen, 1):
            name = f"{lang}_fleurs-{label}-{i}"
            sf.write(config.CLONE_DIR / f"{name}.wav", clip["audio"], clip["rate"])
            print(f"{name}.wav  {len(clip['audio']) / clip['rate']:.0f} s, "
                  f"tono {clip['pitch']:.0f} Hz, limpieza {clip['clean']:.0f} dB")
        if len(chosen) < PER_GENDER:
            print(f"  ({lang}: solo {len(chosen)} voz {label} entre {len(pool)} clips revisados)")
