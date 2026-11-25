# Cambios de la limpieza del código (rama `explect`)

Qué se cambió y por qué. Cada punto dice qué requisito del encargo cubre o qué problema resuelve.

## Requisitos del encargo que faltaban o estaban a medias

| Cambio | Por qué |
|---|---|
| **Borradores y publicación** (`app/publication.py`). Un documento o pregunta frecuente nuevos quedan en borrador; la consola los prueba y luego se publican | El encargo pide "probar preguntas y respuestas antes de publicar cambios". Antes todo lo que se subía quedaba a la vista de los estudiantes al instante. El filtro va en la búsqueda, así que un borrador nunca llega al modelo |
| **Identificación de la intención** (`app/intent.py`) | El flujo del encargo tiene un paso de "identificación de la intención" que no existía. Ahora los saludos, despedidas y agradecimientos se contestan sin buscar en los documentos (más rápido y sin citar fuentes que no vienen al caso). La intención queda en el historial y en las estadísticas |
| **Personajes propios** (`app/avatars.py`, sección Personajes de la consola) | El encargo pide personalizar "rostro o apariencia". Antes solo se podía elegir entre cinco personajes fijos; ahora se sube un `.glb` propio sin tocar archivos |
| **Detección automática del idioma al hablar** | Para estudiantes de intercambio: si alguien habla en inglés con la página en español, contesta en inglés. Solo cambia si Whisper está seguro y es uno de los cinco idiomas |
| **Valoración 👍 / 👎 en la página del avatar** | La "retroalimentación sobre la calidad de las respuestas" solo la podía dar el administrador. Ahora la dan los estudiantes y aparece en el historial |
| **Exportar el historial a CSV** | Para los reportes de avance y el análisis de preguntas sin respuesta |
| **Más formatos**: PowerPoint (`.pptx`) y CSV; los `.txt` guardados en cp1252 se leen bien | Muchos documentos institucionales vienen en presentaciones o en tablas exportadas. Antes un `.txt` del Bloc de notas viejo perdía los acentos |

## Seguridad

| Cambio | Por qué |
|---|---|
| **Clave de administración** (`ADMIN_TOKEN`, `app/api/security.py`) | Cualquiera en la red podía subir o borrar documentos y sacar al asistente de una reunión. Ahora la consola pide la clave y la API la exige en las rutas de administración. Lo que usa el estudiante sigue abierto |
| **Validación de enlaces de Teams corregida** | La comprobación anterior aceptaba dominios como `evilteams.live.com` porque solo miraba que el nombre terminara igual |
| **Límite de tamaño de archivos** y validación de que un personaje sea un `.glb` real | Evita llenar el disco o guardar archivos que no son lo que dicen |
| **Validación de perfiles**: idioma, motor de voz e identificador | Un perfil con un idioma inexistente o un identificador con espacios rompía la página del avatar |

## Robustez

| Cambio | Por qué |
|---|---|
| **Reemplazar un documento ya no lo borra si algo falla** | Antes se borraba el índice y luego se calculaban los vectores: si Ollama fallaba a la mitad, el documento desaparecía del asistente. Y si el archivo nuevo no se podía leer, se borraba también el anterior. Ahora se calcula todo primero y se restaura el archivo anterior |
| **Sesiones con límite** (`app/sessions.py`) | La memoria de conversaciones crecía sin parar: cada sesión guardaba todos sus mensajes y nunca se borraba. Con el asistente encendido días en un kiosco o en reuniones, la memoria solo subía. Ahora guarda solo los turnos que usa, olvida tras una hora sin uso y tiene un tope |
| **Embeddings en tandas** (`EMBED_BATCH`) | Un PDF grande se mandaba en una sola llamada a Ollama, que podía tardar demasiado o fallar |
| **Historial tolerante a líneas cortadas** y escritura con candado | Un apagón a media escritura dejaba una línea incompleta que tumbaba la sección Historial |
| **Índices viejos se migran solos** al encender la API | Un índice creado antes de los borradores no tenía el dato de publicación; sin migrarlo, los estudiantes no verían nada |
| **La API arranca sin Playwright** | Antes, sin Playwright instalado no arrancaba nada, aunque no se usara Teams |

## Instalación y configuración

| Cambio | Por qué |
|---|---|
| **Archivo `.env`** (`.env.example`) | Antes había que definir variables de entorno con `setx` y reiniciar la terminal. Ahora todo está en un archivo, con valores sugeridos según la GPU |
| **El instalador elige los modelos según la GPU** | Tenía fijo `gemma3:12b`, que no cabe en una GPU de 6 GB y descargaba 8 GB inútiles. Ahora crea `.env` con `gemma3:4b` y Whisper `small` si hay menos de 12 GB |
| **El instalador elige el Python correcto** | Tomaba el primer `python` del PATH. En una computadora con MSYS2 ese es un Python 3.14 con el que no se instalan las librerías de voz. Ahora busca uno de python.org entre 3.10 y 3.13 y descarta los demás |
| **three.js dentro del proyecto** (`web/vendor/three/`, `scripts/vendorizar_three.py`) | La página del avatar dependía de un CDN: sin internet, o en una red institucional que lo bloquee, el avatar no aparecía en plena demostración |
| **El revisor de la instalación** conoce `.env`, la memoria que pide cada modelo y three.js | Para que el diagnóstico corresponda a la configuración real |
| **Institución configurable** (`INSTITUTION`) | Las instrucciones al modelo tenían fijo "Tecnológico de Monterrey". El encargo pide que sea reutilizable para otros servicios |

## Orden del código

| Cambio | Por qué |
|---|---|
| **API dividida por tema** (`app/api/`: conversación, voz, asistentes, conocimiento, calidad, reuniones) | `app/api.py` tenía todo junto en 336 líneas. Separado se ve qué es público y qué es de administración, y la clave se aplica por grupo |
| **Instrucciones al modelo aparte** (`app/prompts.py`) | Se pueden revisar y ajustar sin leer la lógica del RAG |
| **Filtro del marcador "sin respuesta" como clase propia** (`MarkerFilter`) | Era lógica escondida dentro de un ciclo; ahora tiene pruebas |
| **Conexiones a modelos y base vectorial al primer uso** | Importar el código ya no se conecta a Ollama ni abre Chroma; eso permite probarlo sin modelos |
| **Se quitó la ruta de OBS** (4 scripts) | La conexión directa a Teams la sustituye; el audio por cables virtuales nunca se probó. Sigue en el historial de git |
| **Se quitó el "Chat de voz" de la consola** (`app/ui.py`) | Duplicaba la página del avatar sin perfiles ni personaje y no se mantenía |

## Pruebas

| Cambio | Por qué |
|---|---|
| **121 pruebas unitarias con pytest** (`tests/unit/`) | Antes solo había scripts que necesitaban GPU, Ollama y la API encendida, así que casi nunca se corrían. Las nuevas simulan el modelo y los embeddings, usan Chroma real en una carpeta temporal y corren en segundos en cualquier computadora |
| **Pruebas con modelos reales en `tests/integracion/`** | Separadas de las unitarias para que `pytest` no dependa de la GPU |
| **ruff** (`pyproject.toml`) y **GitHub Actions** (`.github/workflows/pruebas.yml`) | Revisión de estilo y pruebas automáticas en cada push, para que un cambio no rompa algo sin que nadie lo note |
| **Chroma simulado opcional** (`PRUEBAS_CHROMA=simulado`) | En una computadora con poca memoria libre Chroma no puede correr; así las pruebas se pueden correr igual |

## Lo que se verificó y lo que no

- **Verificado:** las 121 pruebas unitarias pasan (con Chroma simulado: en la laptop donde se hizo la limpieza, Chroma no tenía memoria para correr; ver abajo), ruff sin errores, todo el código compila, la página del avatar carga en Edge sin errores de JavaScript con three.js local, y los pasos 1 y 2 del instalador eligen bien Python y modelos en una RTX 3050 de 6 GB.
- **No verificado todavía:** las pruebas con los modelos reales (`tests/integracion/`), la voz, el avatar hablando y la entrada a Teams después de estos cambios. Hay que correrlas en una computadora con los modelos instalados antes de dar la limpieza por buena.
- **Hallazgo:** con muy poca memoria RAM libre (en esa laptop había 1 GB libre, con Android Studio y su emulador abiertos), Chroma se cierra con `access violation`. No es un error del proyecto, pero puede pasar en una demostración; está en los problemas comunes de [instalacion.md](instalacion.md#problemas-comunes).
