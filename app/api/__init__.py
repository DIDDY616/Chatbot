"""API del asistente.  Uso:  uvicorn app.api:app --port 8000

La página del avatar queda en http://localhost:8000/avatar/

Rutas por tema (cada una en su archivo de esta carpeta):
    conversation  /chat, /chat/stream, /sessions, /feedback        (abiertas)
    speech        /stt, /tts, /speak, /voices, /warmup               (abiertas)
    assistants    /profiles, /avatars                                (lectura abierta, cambios con clave)
    knowledge     /documents, /faqs, /categories, /reindex, ...      (con clave)
    quality       /test, /eval, /history, /stats                     (con clave)
    meetings      /meeting                                           (con clave)
"""
import logging
import mimetypes
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .. import avatars, config, publication
from ..store import collection
from . import assistants, conversation, knowledge, meetings, quality, speech

log = logging.getLogger("uvicorn.error")

# En Windows el registro puede asignar tipos incorrectos y el navegador rechaza los módulos JS.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("model/gltf-binary", ".glb")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        fixed = publication.sync_index()
        if fixed:
            log.info("publicación: se actualizó el estado de %d fragmentos", fixed)
    except Exception as error:  # noqa: BLE001  (un índice dañado no debe impedir arrancar)
        log.warning("publicación: no se pudo revisar el índice (%s)", error)
    if not config.ADMIN_TOKEN:
        log.warning("Sin ADMIN_TOKEN: la administración no pide clave. Defínela en .env antes de abrirla a la red.")
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Asistente Tec", lifespan=lifespan)

    try:
        import openai

        @app.exception_handler(openai.APIConnectionError)
        def llm_unreachable(request, error):
            """Ollama apagado: se responde con un mensaje claro en vez de un error interno."""
            return JSONResponse(
                {"detail": "No se pudo conectar con Ollama. Abre la aplicación de Ollama e inténtalo de nuevo."}, 503)
    except ImportError:
        pass

    for module in (conversation, speech, assistants, knowledge, quality, meetings):
        app.include_router(module.router)

    @app.get("/health", tags=["estado"])
    def health():
        return {"llm": config.LLM_MODEL, "embeddings": config.EMBED_MODEL, "chunks": collection().count(),
                "admin_token": bool(config.ADMIN_TOKEN)}

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/avatar/")

    # Antes del montaje estático: la lista incluye los personajes subidos desde la consola.
    @app.get("/avatar/avatars.json", include_in_schema=False)
    def avatar_list():
        return avatars.list_all()

    app.mount("/avatar", StaticFiles(directory=config.WEB_DIR, html=True), name="avatar")
    return app


app = create_app()
