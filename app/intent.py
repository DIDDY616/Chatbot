"""Identificación de la intención: el paso del flujo entre "reconocimiento de voz" y "consulta".

Distingue la conversación casual (saludos, despedidas, agradecimientos) de una consulta. Lo
casual se contesta sin buscar en la base de conocimiento: es más rápido y no cita fuentes que
no vienen al caso. Todo lo demás es una consulta y sigue el camino del RAG.

Es deliberadamente conservador: una frase solo es casual si TODAS sus palabras son de
cortesía. "Hola, ¿qué horario tiene la biblioteca?" es una consulta.
"""
import re
import unicodedata

QUERY = "consulta"
GREETING = "saludo"
FAREWELL = "despedida"
THANKS = "agradecimiento"
SMALL_TALK = (GREETING, FAREWELL, THANKS)

# Sin acentos y en minúsculas, como las deja _plain. Una frase se clasifica por la primera
# categoría que tenga alguna de sus palabras; las de RELLENO solo acompañan.
WORDS = {
    THANKS: "gracias muchas mil thanks thank merci danke tack tusen vielen",
    FAREWELL: "adios bye goodbye chao chau hasta luego pronto manana vemos nos au revoir tschuss hej "
              "da wiedersehen auf adieu salut later see",
    GREETING: "hola buenas buenos dias tardes noches hello hi hey bonjour bonsoir hallo guten tag morgen "
              "abend hej hejsan god morgon good morning afternoon evening que tal saludos",
}
FILLER = ("a ti te tu usted senor senora asistente bot muy mucho todo bien ok okey vale perfecto genial "
          "excelente you so much very for all your help ayuda por la el de y e oh ah oye cool "
          "great nice super schon gut bra tres bien beaucoup votre aide pour fur deine ihre hilfe "
          "for hjalpen dig er sa mycket")
MAX_WORDS = 8
WORD = re.compile(r"[^\W_]+")
_CATEGORY = {word: name for name, words in WORDS.items() for word in words.split()}
_FILLER = set(FILLER.split())


def _plain(word: str) -> str:
    word = unicodedata.normalize("NFD", word.lower())
    return "".join(c for c in word if not unicodedata.combining(c))


def classify(message: str) -> str:
    """Devuelve "saludo", "despedida", "agradecimiento" o "consulta"."""
    words = [_plain(m.group()) for m in WORD.finditer(message)]
    if not words or len(words) > MAX_WORDS or "?" in message or "¿" in message:
        return QUERY
    if not all(w in _CATEGORY or w in _FILLER for w in words):
        return QUERY
    found = {_CATEGORY[w] for w in words if w in _CATEGORY}
    for name in (THANKS, FAREWELL, GREETING):
        if name in found:
            return name
    return QUERY
