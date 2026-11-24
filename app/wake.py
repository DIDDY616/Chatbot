"""Activación por nombre: decide si una frase oída en una reunión va dirigida al asistente.

Whisper no siempre escribe el nombre igual ("Tec Bot", "Techbot", "Tech boat"), así que se
compara por cómo suena y no por cómo se escribe.
"""
import logging
import re
import unicodedata

from . import voice

log = logging.getLogger("uvicorn.error")

MAX_WORDS = 3     # un nombre puede transcribirse partido en varias palabras
TOLERANCE = 1 / 6  # diferencia admitida por letra del nombre: una consonante cada seis letras
VOWELS = set("aeiou")
WORD = re.compile(r"[^\W_]+")

# Pista para Whisper: un diálogo corto donde alguien llama al asistente por su nombre.
# Así aprende cómo se escribe el nombre y que debe transcribirlo cuando abre la frase.
HINTS = {
    "es": "Reunión con el asistente virtual {names}. — {name}, ¿me escuchas? — Sí, dime.",
    "en": "Meeting with the virtual assistant {names}. — {name}, can you hear me? — Yes, go ahead.",
    "fr": "Réunion avec l'assistant virtuel {names}. — {name}, tu m'entends ? — Oui, je t'écoute.",
    "sv": "Möte med den virtuella assistenten {names}. — {name}, hör du mig? — Ja, jag lyssnar.",
    "de": "Besprechung mit dem virtuellen Assistenten {names}. — {name}, hörst du mich? — Ja, ich höre.",
}

# Órdenes de alto: si la frase, quitando el nombre, es corta y solo trae estas palabras
# ("TecBot, espera un momento", "gracias, TecBot"), el asistente se calla en vez de tomarla
# como pregunta. Hace falta al menos una palabra de la primera lista; las de la segunda
# solo acompañan. Van sin acentos, como las deja _plain.
STOP_WORDS = {
    "es": ("para parale espera esperame alto silencio calla callate gracias basta detente suficiente listo ya todo",
           "un momento por favor ok okey muchas perdon oye bueno esta bien es eso asi hasta ahi aqui"),
    "en": ("stop wait thanks thank quiet enough pause silence hold",
           "you please ok okay a an one moment second that s thats all on sorry very much it is"),
    "fr": ("stop arrete arretez attends attendez merci silence assez suffit pause",
           "s il te vous plait un une moment instant seconde beaucoup ok ca c est bon pardon"),
    "sv": ("stopp stop sluta vanta tack tyst paus racker",
           "ett ogonblick snalla ok okej det sa mycket lite ursakta nu"),
    "de": ("stopp stop halt warte warten danke dank ruhe pause genug reicht aufhoren",
           "bitte mal kurz einen moment ok okay das vielen schon sei entschuldigung jetzt"),
}
MAX_STOP_WORDS = 5

# Preguntas para saber si el asistente está oyendo ("TecBot, ¿me escuchas?"). No se buscan en
# la base de conocimiento: el asistente solo confirma que oye. Sin acentos, como las deja _plain.
PINGS = {
    "es": ("me escuchas", "me escucha", "me oyes", "me oye", "estas ahi", "esta ahi", "sigues ahi", "me puedes oir", "me puedes escuchar"),
    "en": ("can you hear me", "do you hear me", "are you there", "are you still there", "you hear me"),
    "fr": ("tu m entends", "vous m entendez", "tu es la", "vous etes la", "est ce que tu m entends"),
    "sv": ("hor du mig", "ar du dar", "kan du hora mig"),
    "de": ("horst du mich", "horen sie mich", "bist du da", "kannst du mich horen"),
}
MAX_PING_WORDS = 7


def hear(audio: bytes, language: str | None, names: list[str]) -> dict:
    """Transcribe una frase de la reunión y dice si nombra al asistente.

    Devuelve {"text", "language", "addressed", "question", "stop", "ping"}. Se transcribe hasta dos veces:
    con la pista Whisper escribe bien el nombre pero alguna vez se lo salta, y sin ella pasa
    lo contrario; con cualquiera de las dos que lo detecte basta.
    """
    hint = HINTS.get(language or "es", HINTS["es"]).format(names=", ".join(names), name=names[0])
    result = voice.transcribe(audio, language, prompt=hint)
    hinted = result["text"]
    # Con audio poco claro Whisper a veces repite la pista en vez de transcribir: eso no cuenta.
    # Se reconoce porque trae el principio o el final de la pista, que nadie dice en la reunión;
    # la pregunta de en medio ("TecBot, ¿me escuchas?") sí puede haberse dicho de verdad.
    found = detect(hinted, names, language)
    intro, reply = _plain(hint.split(".")[0]), _plain(hint.rsplit("—", 1)[1])
    if intro in _plain(hinted) or reply in _plain(hinted):
        found = detect("", names, language)
    if not found["addressed"]:
        result = voice.transcribe(audio, language)
        found = detect(result["text"], names, language)
    log.info("oido en reunion [%s] %s | con pista: %r | sin pista: %r", language,
             "LO NOMBRAN" if found["addressed"] else "no lo nombran", hinted,
             result["text"] if result["text"] != hinted else "(igual)")
    return {**result, **found}


def _plain(text: str) -> str:
    """Minúsculas, sin acentos y solo letras y números."""
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if c.isalnum())


def _sound(text: str) -> str:
    """Clave aproximada de cómo suena un texto, para comparar nombres mal escritos.

    "Tech boat", "Tek bot" y "TecBot" dan la misma clave: "tekbot". Cada palabra se convierte
    por separado, para que "take about" no acabe sonando igual que "take bot".
    """
    return "".join(_word_sound(match.group()) for match in WORD.finditer(text))


def _word_sound(word: str) -> str:
    s = _plain(word)
    for written, sound in (("ough", "o"), ("th", "0"), ("ph", "f"), ("ck", "k"), ("ch", "k"), ("qu", "k")):
        s = s.replace(written, sound)
    s = re.sub(r"c(?=[eiy])", "s", s)
    s = s.translate(str.maketrans("cqgdzy", "kkktsi")).replace("h", "").replace("x", "ks")
    s = re.sub(r"[aeiou]+", lambda run: run.group()[0], s)  # "oa", "ou" suenan como una vocal
    return re.sub(r"(.)\1+", r"\1", s)                    # letras dobles


def _distance(heard: str, target: str) -> float:
    """Distancia de edición entre dos claves; equivocarse en una vocal cuesta la mitad."""
    cost = lambda letter: 0.5 if letter in VOWELS else 1.0
    previous = [0.0]
    for letter in target:
        previous.append(previous[-1] + cost(letter))
    for a in heard:
        current = [previous[0] + cost(a)]
        for j, b in enumerate(target, 1):
            change = 0.0 if a == b else 0.5 if a in VOWELS and b in VOWELS else 1.0
            current.append(min(previous[j] + cost(a), current[j - 1] + cost(b), previous[j - 1] + change))
        previous = current
    return previous[-1]


def is_stop(question: str, language: str | None = None) -> bool:
    """¿Lo que queda de la frase es solo una orden de alto ("espera", "gracias")?"""
    core, filler = (set(words.split()) for words in STOP_WORDS.get(language or "es", STOP_WORDS["es"]))
    words = [_plain(match.group()) for match in WORD.finditer(question)]
    return (0 < len(words) <= MAX_STOP_WORDS
            and all(word in core or word in filler for word in words)
            and any(word in core for word in words))


def is_ping(question: str, language: str | None = None) -> bool:
    """¿Solo preguntan si el asistente está oyendo ("¿me escuchas?")?"""
    words = [_plain(match.group()) for match in WORD.finditer(question)]
    said = " ".join(words)
    return len(words) <= MAX_PING_WORDS and any(phrase in said for phrase in PINGS.get(language or "es", PINGS["es"]))


def detect(text: str, names: list[str], language: str | None = None) -> dict:
    """Busca alguno de los nombres en el texto.

    Devuelve {"addressed": bool, "question": str, "stop": bool, "ping": bool}: la pregunta es
    el texto sin el nombre, `stop` indica que no es una pregunta sino una orden de callarse, y
    `ping` que solo quieren saber si el asistente está oyendo.
    """
    words = list(WORD.finditer(text))
    targets = [sound for sound in map(_sound, names) if len(sound) >= 3]
    best = None  # (distancia, número de palabras, primera palabra, última palabra)
    for start in range(len(words)):
        for end in range(start, min(start + MAX_WORDS, len(words))):
            heard = _sound(text[words[start].start():words[end].end()])
            for target in targets:
                # Nombre pegado a la palabra de al lado ("TecBotnär", "DistecBot").
                glued = len(target) >= 5 and len(heard) > len(target) and (
                    heard.startswith(target) or heard.endswith(target))
                if not glued and abs(len(heard) - len(target)) > 2:
                    continue
                candidate = (0.25 if glued else _distance(heard, target), end - start, start, end)
                if candidate[0] <= len(target) * TOLERANCE + 1e-9 and (best is None or candidate < best):
                    best = candidate
    if best is None:
        return {"addressed": False, "question": "", "stop": False, "ping": False}
    _, _, start, end = best
    rest = f"{text[:words[start].start()]} {text[words[end].end():]}"
    rest = re.sub(r"\s+([,.;:!?])", r"\1", re.sub(r"\s+", " ", rest))  # sin espacios antes de un signo
    rest = re.sub(r"[,;:]+(?=[,.;:!?])", "", rest)                     # ni comas dobles donde iba el nombre
    rest = re.sub(r"^[\s,.;:!?—–-]+", "", rest).strip()               # ni signos sueltos al inicio
    return {"addressed": True, "question": rest, "stop": is_stop(rest, language), "ping": is_ping(rest, language)}
