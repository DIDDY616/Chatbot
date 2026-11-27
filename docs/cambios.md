# Cambios de la versión 0.2

Qué cambió respecto a la primera versión del MVP y por qué. Cada punto dice qué requisito del encargo cubre o qué problema resuelve.

## Requisitos del encargo que faltaban o estaban a medias

| Cambio | Por qué |
|---|---|
| **Borradores y publicación** (`app/publication.py`) | El encargo pide "probar preguntas y respuestas antes de publicar cambios". Antes todo lo que se subía quedaba a la vista de los estudiantes al instante. Ahora lo nuevo queda en borrador, se prueba en la consola y se publica. El filtro va en la búsqueda, así que un borrador nunca llega al modelo |
| **Identificación de la intención** (`app/intent.py`) | El flujo del encargo tiene ese paso y no existía. Los saludos, despedidas y agradecimientos se contestan sin buscar en los documentos; la intención queda en el historial y en las estadísticas |
| **Personajes propios** (`app/avatars.py`, sección Personajes) | El encargo pide personalizar "rostro o apariencia". Antes solo había cinco personajes fijos; ahora se sube un `.glb` propio desde la consola |
| **Detección del idioma al hablar** | Para estudiantes de intercambio: si alguien habla en inglés con la página en español, contesta en inglés. Solo cambia si Whisper está seguro y es uno de los cinco idiomas |
| **Valoración 👍 / 👎 de los estudiantes** | La retroalimentación sobre las respuestas solo la daba el administrador |
| **Historial en CSV** | Para reportes y para revisar las preguntas sin respuesta |
| **Más formatos**: PowerPoint, CSV y `.txt` con acentos en cualquier codificación | Muchos documentos institucionales vienen en presentaciones o tablas exportadas |
| **Importar páginas web oficiales** (`app/web_import.py`, con trafilatura) | Lo que más le falta al MVP es información real, y mucha ya está en tec.mx. Se pega el enlace y queda como documento en borrador, con la fuente y la fecha. Si la página se arma con JavaScript, se abre con un navegador sin ventana. Solo acepta páginas públicas |

## Calidad de las respuestas

| Cambio | Por qué |
|---|---|
| **Búsqueda híbrida** (`app/keyword.py`): por significado y por palabras exactas, combinadas con Reciprocal Rank Fusion | Los vectores confunden siglas, claves de materias y números ("ITC", "TC1001", "480 horas"), que es justo lo que preguntan los estudiantes. Respeta los mismos filtros de acceso y publicación. Se apaga con `HYBRID_SEARCH=false` |
| **Almacén de vectores propio** (`app/vectorstore.py`) | Chroma se cae en algunas computadoras con Windows al guardar el primer fragmento (fallo conocido sin solución: [#5392](https://github.com/chroma-core/chroma/issues/5392), [#6052](https://github.com/chroma-core/chroma/issues/6052)). El almacén propio guarda en `data/vectores` y busca con numpy, en milisegundos para miles de fragmentos y con las mismas reglas de filtros que Chroma. Chroma sigue disponible con `VECTOR_STORE=chroma` |
| **Institución configurable** (`INSTITUTION`) | Para reutilizar el asistente en otros servicios, como pide el encargo |
| **Herramientas evaluadas** ([herramientas.md](herramientas.md)) | Kokoro, MuseTalk, LatentSync, rerankers y bot oficial de Teams: qué se integró y qué conviene con un servidor con GPU |

## Seguridad

| Cambio | Por qué |
|---|---|
| **Clave de administración** (`ADMIN_TOKEN`) | Cualquiera en la red podía subir o borrar documentos y sacar al asistente de una reunión. Ahora la consola pide la clave y la API la exige en las rutas de administración; lo que usa el estudiante sigue abierto |
| **Validación de enlaces de Teams corregida** | Aceptaba dominios como `evilteams.live.com` porque solo miraba el final del nombre |
| **Límites y validación de archivos y perfiles** | Tamaño máximo de subida, personajes que de verdad sean `.glb`, perfiles con idioma, motor de voz e identificador válidos |

## Robustez

| Cambio | Por qué |
|---|---|
| **Reemplazar un documento ya no lo borra si algo falla** | Antes, si Ollama fallaba a la mitad, el documento desaparecía del asistente; si el archivo nuevo no se podía leer, se perdía también el anterior |
| **Sesiones con límite** (`app/sessions.py`) | La memoria de conversaciones crecía sin parar. Ahora guarda solo los turnos que usa y olvida tras una hora sin uso |
| **Embeddings en tandas**, **historial tolerante a líneas cortadas**, **migración automática de índices viejos** | Documentos grandes, apagones a media escritura e índices de la versión anterior ya no rompen nada |
| **La API arranca sin Playwright** | Antes no arrancaba nada si faltaba, aunque no se usara Teams |

## Instalación

| Cambio | Por qué |
|---|---|
| **Archivo `.env`** (`.env.example`) | Toda la configuración en un archivo, sin variables de entorno de Windows |
| **El instalador elige los modelos según la GPU** | Tenía fijo `gemma3:12b`, que no cabe con menos de 12 GB. Ahora usa `gemma3:4b` y Whisper `small` en GPU chicas |
| **El instalador elige el Python correcto** | Descarta el Python de MSYS2 o Git Bash y el 3.14, con los que no se instalan las librerías de voz |
| **Revisa el Visual C++ Redistributable** | Sin él la voz falla con "DLL load failed"; muchas computadoras con Windows no lo traen |
| **Descargas con límite de tiempo y reintentos** (`scripts/descargar_voces.py`, `scripts/descargar_whisper.py`) | Las descargas de Hugging Face a veces se quedan colgadas sin mandar datos. El descargador de Piper esperaba para siempre, y el modelo de Whisper se bajaba en la primera pregunta: si se colgaba, el avatar contestaba por escrito pero nunca hablaba |
| **Encuentra Ollama recién instalado** | En una terminal abierta antes de instalarlo, el instalador creía que faltaba y se detenía |
| **three.js dentro del proyecto** | La página del avatar dependía de internet; en una red que bloquee el CDN, el avatar no aparecía |
| **Soporte para Mac con Apple Silicon** (`iniciar.sh`, guía en [instalacion.md](instalacion.md)) | Los paquetes de CUDA hacían fallar la instalación en Mac |

## Orden del código

| Cambio | Por qué |
|---|---|
| **API dividida por tema** (`app/api/`) | Un solo archivo de 336 líneas con todo mezclado. Separado se ve qué es público y qué es de administración |
| **Instrucciones al modelo aparte** (`app/prompts.py`) | Se revisan y ajustan sin leer la lógica del RAG |
| **Valores en un solo lugar** (`app/config.py`) | Idiomas, direcciones y rutas estaban repetidos en varios archivos |
| **Se quitaron** la ruta de OBS (4 scripts), el chat de voz duplicado de la consola y un script de un solo uso | La conexión directa a Teams sustituye a OBS (cuyo audio nunca se probó); lo demás duplicaba funciones o dependía de librerías que no están en el proyecto |

## Pruebas

| Cambio | Por qué |
|---|---|
| **148 pruebas unitarias con pytest** (`tests/unit/`) | Antes solo había scripts que necesitaban GPU, Ollama y la API encendida, así que casi nunca se corrían. Las nuevas simulan el modelo y los embeddings, y corren en segundos en cualquier computadora |
| **Pruebas con modelos reales** en `tests/integracion/` | Separadas para que `pytest` no dependa de la GPU |
| **ruff y GitHub Actions** | Revisión de estilo y pruebas automáticas en cada push, con los dos almacenes de vectores |

## Estado de la verificación

- **Verificado:** las pruebas unitarias pasan en Windows y en GitHub (Linux), y ruff no marca errores. El asistente se instaló desde cero en Windows con una GPU de 6 GB (`gemma3:4b`, Whisper `small`) y funciona de punta a punta: avatar, voz, labios y consola.
- **Pendiente:** volver a correr las pruebas con modelos reales (`tests/integracion/`) y la entrada a una reunión real de Teams después de estos cambios.
