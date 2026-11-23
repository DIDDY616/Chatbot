"""Configuración central. Todo se puede cambiar con variables de entorno."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "data" / "docs"      # documentos fuente (subcarpeta = categoría)
CHROMA_DIR = BASE_DIR / "data" / "chroma"  # base vectorial (se regenera con la ingesta)
LOG_FILE = BASE_DIR / "data" / "historial.jsonl"
PROFILES_FILE = BASE_DIR / "data" / "perfiles.json"  # perfiles de asistente (editable)
WEB_DIR = BASE_DIR / "web"                 # página del avatar

# LLM: cualquier servidor compatible con la API de OpenAI (Ollama por defecto).
# Se usa 127.0.0.1 y no "localhost": en Windows localhost agrega ~2 s por conexión.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "gemma3:12b")

# Embeddings: se quedan en Ollama aunque el LLM se cambie a otro proveedor.
EMBED_BASE_URL = os.getenv("EMBED_BASE_URL", "http://127.0.0.1:11434/v1")
EMBED_API_KEY = os.getenv("EMBED_API_KEY", "ollama")
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")

# Voz. Sin GPU: WHISPER_DEVICE=cpu, WHISPER_COMPUTE=int8 y WHISPER_MODEL=small.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "large-v3-turbo")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "int8_float16")  # comprimido: menos VRAM que float16
VOICES_DIR = BASE_DIR / "data" / "voices"  # voces de Piper (.onnx + .onnx.json)
DEFAULT_VOICES = {"es": "es_MX-claude-high", "en": "en_US-lessac-medium"}
# Chatterbox clona la voz de cualquier audio de referencia (.wav de 10 a 20 s) puesto aquí.
CLONE_DIR = BASE_DIR / "data" / "voces_clonadas"
CHATTERBOX_DEVICE = os.getenv("CHATTERBOX_DEVICE", "cuda")

ASSISTANT_NAME =os.getenv("ASSISTANT_NAME", "TecBot")

CHUNK_SIZE = 1000    # caracteres por fragmento
CHUNK_OVERLAP = 150
TOP_K = 5            # fragmentos recuperados por pregunta
MAX_TURNS = 4        # turnos previos que se envían al LLM (cuidar la ventana de contexto)
