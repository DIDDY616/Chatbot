"""Configuración central.

Cada valor se puede cambiar con una variable de entorno o, más cómodo, en el archivo `.env`
de la raíz del proyecto (ver `.env.example`). Una variable de entorno ya definida gana sobre
`.env`, así que un valor puesto en la terminal siempre manda.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


def load_env_file(path: Path) -> dict[str, str]:
    """Lee un archivo KEY=valor (comentarios con #, comillas opcionales) sin pisar el entorno."""
    loaded: dict[str, str] = {}
    if not path.is_file():
        return loaded
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if value[:1] in "\"'" and value[-1:] == value[:1] and len(value) >= 2:
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if key and key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded


load_env_file(ENV_FILE)


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


# ---------- Datos ----------
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = DATA_DIR / "docs"                       # documentos fuente (subcarpeta = categoría)
VECTORS_DIR = DATA_DIR / "vectores"                # almacén de vectores propio (se regenera con la ingesta)
CHROMA_DIR = DATA_DIR / "chroma"                   # solo con VECTOR_STORE=chroma
LOG_FILE = DATA_DIR / "historial.jsonl"
PROFILES_FILE = DATA_DIR / "perfiles.json"
FAQS_FILE = DATA_DIR / "faqs.json"
FEEDBACK_FILE = DATA_DIR / "valoraciones.json"
PUBLICATION_FILE = DATA_DIR / "publicacion.json"   # qué documentos están publicados y cuáles en borrador
CUSTOM_AVATARS_FILE = DATA_DIR / "personajes.json"  # personajes subidos desde la consola
EVAL_FILE = BASE_DIR / "tests" / "preguntas.jsonl"
WEB_DIR = BASE_DIR / "web"
AVATARS_DIR = WEB_DIR / "avatars"                  # archivos .glb (descargados o subidos)

# ---------- Institución ----------
# Aparece en las instrucciones al modelo. Cambiarla basta para reutilizar el asistente en otra escuela.
INSTITUTION = os.getenv(
    "INSTITUTION", "Tecnológico de Monterrey (Escuela de Ingeniería y Ciencias)")
ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "TecBot")

# ---------- Modelos ----------
# LLM: cualquier servidor compatible con la API de OpenAI (Ollama por defecto).
# Se usa 127.0.0.1 y no "localhost": en Windows localhost agrega ~2 s por conexión.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "gemma3:12b")

# Embeddings: se quedan en Ollama aunque el LLM se cambie a otro proveedor.
EMBED_BASE_URL = os.getenv("EMBED_BASE_URL", "http://127.0.0.1:11434/v1")
EMBED_API_KEY = os.getenv("EMBED_API_KEY", "ollama")
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")
EMBED_BATCH = _int("EMBED_BATCH", 32)  # fragmentos por llamada: un PDF grande no va en una sola

# ---------- Voz ----------
# Sin GPU: WHISPER_DEVICE=cpu, WHISPER_COMPUTE=int8 y WHISPER_MODEL=small.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "large-v3-turbo")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "int8_float16")  # comprimido: menos VRAM que float16
VOICES_DIR = DATA_DIR / "voices"  # voces de Piper (.onnx + .onnx.json)
DEFAULT_VOICES = {"es": "es_MX-claude-high", "en": "en_US-lessac-medium"}
# Chatterbox clona la voz de cualquier audio de referencia (.wav de 10 a 20 s) puesto aquí.
CLONE_DIR = DATA_DIR / "voces_clonadas"
CHATTERBOX_DEVICE = os.getenv("CHATTERBOX_DEVICE", "cuda")
# Con detección automática, Whisper solo cambia el idioma si está así de seguro.
LANGUAGE_DETECT_CONFIDENCE = float(os.getenv("LANGUAGE_DETECT_CONFIDENCE", "0.8"))

# ---------- RAG ----------
# "local": almacén propio en data/vectores (por omisión; Chroma se cae en algunas computadoras con
# Windows). "chroma": Chroma en data/chroma, para bases de conocimiento muy grandes.
VECTOR_STORE = os.getenv("VECTOR_STORE", "local").lower()
CHUNK_SIZE = 1000    # caracteres por fragmento
CHUNK_OVERLAP = 150
TOP_K = 5            # fragmentos recuperados por pregunta
# Búsqueda híbrida: vectores + palabras exactas (app/keyword.py). "false" vuelve a solo vectores.
HYBRID_SEARCH = os.getenv("HYBRID_SEARCH", "true").lower() not in ("0", "false", "no")
HYBRID_CANDIDATES = _int("HYBRID_CANDIDATES", 20)  # candidatos de cada búsqueda antes de combinarlas
MAX_TURNS = 4        # turnos previos que se envían al LLM (cuidar la ventana de contexto)

# ---------- Sesiones ----------
SESSION_TTL_MINUTES = _int("SESSION_TTL_MINUTES", 60)  # una conversación inactiva se olvida
MAX_SESSIONS = _int("MAX_SESSIONS", 500)               # tope de conversaciones en memoria

# ---------- Administración ----------
# Con ADMIN_TOKEN definido, la consola pide esa clave y la API la exige en las rutas de
# administración. Vacío = sin clave (solo para usarlo en una computadora propia).
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 50)
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
TEAMS_CAPTURAS = os.getenv("TEAMS_CAPTURAS", "")  # carpeta para capturas de diagnóstico de Teams; vacío = no
AVATAR_URL = os.getenv("AVATAR_URL", "http://localhost:8000/avatar/")

LANGUAGES = {"es": "español", "en": "English", "fr": "français", "sv": "svenska", "de": "Deutsch"}
