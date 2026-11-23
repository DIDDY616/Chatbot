"""Sincronía de labios: convierte el audio de una frase en visemas con tiempos.

Whisper da el inicio y fin de cada palabra, espeak (incluido en Piper) da sus fonemas,
y cada fonema se traduce a uno de los 15 visemas de Oculus que anima el avatar.
Funciona igual con cualquier motor de voz porque parte del audio ya generado.
"""
import io
import wave
from functools import lru_cache

import numpy as np

from . import voice

ESPEAK_VOICES = {"es": "es-419", "en": "en-us", "fr": "fr-fr", "de": "de", "sv": "sv"}
VOWELS = {"aa", "E", "I", "O", "U"}
MAX_PHONEME_SECONDS = 0.16  # si la palabra trae una pausa, los fonemas no se estiran de más

_GROUPS = {
    "aa": "aɑɐæä",
    "E": "eɛœɜʌəɚɘɝ",
    "I": "iɪɨyʏ",
    "O": "oɔɒø",
    "U": "uʊɯɤʉ",
    "PP": "pbmβ",
    "SS": "szʃʒɕʑçʝxɣhɦχ",
    "TH": "θð",
    "DD": "tdʈɖ",
    "FF": "fvʋ",
    "kk": "kgɡqɢ",
    "nn": "nŋɲɳ",
    "RR": "ɹrɾɽlɫjwʎʁɻʀɭ",
}
PHONEME_TO_VISEME = {phoneme: viseme for viseme, phonemes in _GROUPS.items() for phoneme in phonemes}


@lru_cache(maxsize=1)
def _phonemizer():
    from piper.phonemize_espeak import EspeakPhonemizer

    return EspeakPhonemizer()


def word_visemes(word: str, language: str) -> list[tuple[str, float]]:
    """Visemas de una palabra con su peso relativo de duración (las vocales duran más)."""
    result: list[tuple[str, float]] = []
    for sentence in _phonemizer().phonemize(ESPEAK_VOICES.get(language, language), word):
        for phoneme in sentence:
            if phoneme == "ː" and result:
                result[-1] = (result[-1][0], result[-1][1] * 1.5)
                continue
            viseme = PHONEME_TO_VISEME.get(phoneme)
            if viseme is None:
                continue
            weight = 1.0 if viseme in VOWELS else 0.6
            if result and result[-1][0] == viseme:
                result[-1] = (viseme, result[-1][1] + weight)
            else:
                result.append((viseme, weight))
    return result


def _loudness(audio: bytes) -> tuple[np.ndarray, float]:
    """Volumen por tramos de 10 ms y el umbral bajo el cual se considera silencio."""
    with wave.open(io.BytesIO(audio)) as wav:
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16).astype(np.float32)
        samples = samples.reshape(-1, wav.getnchannels()).mean(axis=1)
        frame = wav.getframerate() // 100
    count = len(samples) // frame
    rms = np.sqrt((samples[: count * frame].reshape(count, frame) ** 2).mean(axis=1))
    return rms, (0.1 * float(np.percentile(rms, 95)) if count else 0.0)


def visemes(audio: bytes, language: str) -> dict:
    """Devuelve {visemes, vtimes, vdurations} (tiempos en ms) para un audio WAV."""
    rms, threshold = _loudness(audio)
    names, times, durations = [], [], []
    for word, start, end in voice.word_times(audio, language):
        # Recorta los silencios que Whisper deja dentro del intervalo de la palabra.
        first, last = int(start * 100), min(int(end * 100), len(rms))
        loud = np.nonzero(rms[first:last] > threshold)[0]
        if len(loud):
            start, end = (first + loud[0]) / 100, (first + loud[-1] + 1) / 100
        shapes = word_visemes(word, language)
        total = sum(weight for _, weight in shapes)
        if not shapes or end <= start:
            continue
        unit = min((end - start) / total, MAX_PHONEME_SECONDS)
        clock = start
        for viseme, weight in shapes:
            names.append(viseme)
            times.append(round(clock * 1000))
            durations.append(round(unit * weight * 1000))
            clock += unit * weight
    return {"visemes": names, "vtimes": times, "vdurations": durations}
