"""Búsqueda por palabras (BM25) y fusión con la búsqueda por vectores (RRF).

Los vectores encuentran preguntas dichas con otras palabras ("¿cuándo cierra la biblioteca?"
contra "horario de la biblioteca"), pero confunden siglas, claves y números: "TC1001", "ITC",
"480 horas". BM25 hace justo lo contrario. Se corren las dos y se combinan por posición con
Reciprocal Rank Fusion, que no necesita que los puntajes de las dos búsquedas se parezcan.

Sin dependencias: para una base de conocimiento de un MVP (miles de fragmentos) basta con
calcularlo al vuelo sobre los fragmentos que el asistente puede consultar.
"""
import math
import re
import unicodedata
from collections import Counter

WORD = re.compile(r"[^\W_]+")
# Palabras tan comunes que no ayudan a distinguir fragmentos (sin acentos, como las deja _plain).
STOPWORDS = set("""
a al algo como con cual cuales cuando cuanto cuantos de del donde el en es esa ese esta este hay la las
le lo los mas me mi o para pero por que quien se si sin sobre son su sus te tiene tu un una uno y ya yo
puedo debo necesito hacer saber
the a an and are can do does for how i in is it my of on or to what when where which who why with
le la les des du de et est en un une que qui pour dans sur avec
der die das und ist ein eine den dem zu mit fur wie was wann wo
och att det en ett ar som pa for med hur vad nar var
""".split())


def _plain(word: str) -> str:
    word = unicodedata.normalize("NFD", word.lower())
    return "".join(c for c in word if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    """Palabras útiles para buscar: sin acentos, minúsculas, sin palabras vacías."""
    words = (_plain(m.group()) for m in WORD.finditer(text))
    return [w for w in words if w not in STOPWORDS and (len(w) > 1 or w.isdigit())]


def bm25_rank(query: str, documents: list[str], k1: float = 1.5, b: float = 0.75) -> list[int]:
    """Índices de los documentos que comparten palabras con la consulta, del más al menos relevante."""
    terms = set(tokens(query))
    if not terms or not documents:
        return []
    docs = [Counter(tokens(d)) for d in documents]
    lengths = [sum(d.values()) for d in docs]
    average = (sum(lengths) / len(docs)) or 1.0
    frequency = {t: sum(1 for d in docs if t in d) for t in terms}
    scores = []
    for i, doc in enumerate(docs):
        score = 0.0
        for term in terms:
            tf = doc.get(term, 0)
            if not tf:
                continue
            idf = math.log(1 + (len(docs) - frequency[term] + 0.5) / (frequency[term] + 0.5))
            score += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * lengths[i] / average))
        if score > 0:
            scores.append((score, i))
    return [i for _, i in sorted(scores, key=lambda pair: (-pair[0], pair[1]))]


def rrf(rankings: list[list[str]], k: int = 60) -> list[str]:
    """Reciprocal Rank Fusion: suma 1/(k + posición) de cada lista. k=60 es el valor del artículo original."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for position, item in enumerate(ranking, 1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + position)
    return sorted(scores, key=lambda item: -scores[item])
