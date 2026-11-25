# Instalación y configuración

## Requisitos

### Equipo

| Componente | Mínimo | Probado |
|---|---|---|
| Sistema | Windows 10 u 11 de 64 bits | Windows 11 |
| GPU | NVIDIA con 6 GB de memoria (12 GB para el modelo grande) | RTX 4090 de laptop, 16 GB |
| Memoria RAM | 16 GB, con unos 6 GB libres al encender | |
| Disco | 25 GB libres | |
| Micrófono y bocinas | Para conversar por voz | |
| Internet | Solo para instalar | |

La instalación ocupa unos 15 GB con el modelo grande: 9.4 GB de modelos de lenguaje, 2.9 GB de librerías de Python, 1.6 GB del modelo de reconocimiento de voz y 0.7 GB de voces. Con `gemma3:4b` son unos 6 GB menos. Con la voz natural son unos 5 GB más.

La GPU es necesaria para conversar por voz con fluidez. La configuración grande ocupa unos 11.7 GB de memoria de video. La explicación completa está en [arquitectura.md](arquitectura.md#por-qué-gpu-y-por-qué-local).

Con menos de 12 GB el instalador elige solo un modelo de lenguaje más chico (`gemma3:4b`) y un Whisper más chico (`small`). Esa combinación todavía no se ha medido en este proyecto: espera respuestas algo menos precisas, sobre todo con nombres aproximados de carreras.

**Memoria RAM libre.** Con poca memoria libre (por ejemplo, con Android Studio y su emulador abiertos) la base vectorial Chroma no logra reservar memoria y la API se cierra sin mensaje claro (`access violation` u `OpenBLAS error: Memory allocation still failed`). Cierra programas pesados antes de encender el asistente.

### Programas

| Programa | Para qué | Lo instala el script |
|---|---|---|
| Python 3.10 a 3.13 de python.org (de preferencia 3.12) | Ejecutar el asistente | No |
| Controladores de NVIDIA | Usar la GPU | No |
| Ollama | Ejecutar el modelo de lenguaje | Sí, si aceptas |
| Chrome o Edge | Página del avatar y entrada a Teams | No (Edge viene con Windows) |

La forma más simple de instalar Python es `winget install -e --id Python.Python.3.12`. No sirve el Python de MSYS2, Cygwin o Git Bash: para ese no existen las librerías compiladas de reconocimiento de voz ni de Piper. Tampoco Python 3.14, que todavía es demasiado nuevo para varias de ellas. El instalador busca solo un Python que sirva y descarta los demás.

## Instalación rápida

1. Descarga o clona el proyecto.
2. Abre PowerShell en la carpeta del proyecto.
3. Ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File instalar.ps1
```

El script hace siete pasos y avisa en cuál va:

1. Busca un Python que sirva (3.10 a 3.13 de python.org, de preferencia 3.12).
2. Detecta la GPU y, si no existe `.env`, lo crea con los modelos que caben: `gemma3:12b` y Whisper `large-v3-turbo` con 12 GB o más, `gemma3:4b` y Whisper `small` con menos, y Whisper en procesador si no hay GPU NVIDIA.
3. Crea el entorno de Python en `.venv` e instala las librerías.
4. Instala Ollama si falta (pregunta antes) y descarga el modelo de lenguaje de `.env` y `bge-m3`.
5. Descarga las voces.
6. Descarga los personajes 3D.
7. Indexa los documentos de `data/docs` y revisa que todo esté completo.

Se puede ejecutar varias veces: salta lo que ya está instalado. La primera vez tarda sobre todo por las descargas (unos 12 GB).

### Opciones

| Opción | Efecto |
|---|---|
| `-Minimo` | Solo las voces de español e inglés. Las otras tres lenguas quedan sin voz. |
| `-VozNatural` | Agrega la voz natural con clonación (Chatterbox). Necesita unos 3 GB más de memoria de video. |
| `-SoloRevisar` | No instala nada. Solo dice qué falta. |

Ejemplo:

```powershell
powershell -ExecutionPolicy Bypass -File instalar.ps1 -Minimo
```

## Encender y apagar

```powershell
.\iniciar.bat
```

Abre Ollama si estaba cerrado, enciende la API y la consola en dos ventanas, y abre la consola en el navegador.

| Qué | Dirección |
|---|---|
| Consola de administración | `http://localhost:8501` |
| Página del avatar | `http://localhost:8000/avatar/` |

La primera pregunta tarda más porque los modelos se cargan en memoria.

Para apagarlo, cierra las dos ventanas tituladas "Asistente Tec - API" y "Asistente Tec - Consola".

## Revisar la instalación

```powershell
.\.venv\Scripts\python.exe -m scripts.revisar
```

Lista cada requisito como `OK`, `AVISO` o `FALTA`, y dice qué comando ejecutar para lo que falte.

## Instalación manual

Para quien prefiera hacerlo paso a paso o esté en otra plataforma.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env     # y ajusta LLM_MODEL y WHISPER_MODEL a tu GPU
```

Instala Ollama desde `https://ollama.com/download` y descarga los modelos (el de lenguaje es el que pusiste en `.env`):

```powershell
ollama pull gemma3:12b     # o gemma3:4b con menos de 12 GB
ollama pull bge-m3
```

Descarga las voces y los personajes:

```powershell
.\.venv\Scripts\python.exe -m piper.download_voices es_MX-claude-high en_US-lessac-medium --download-dir data\voices
.\.venv\Scripts\python.exe -m scripts.descargar_avatares
```

Indexa los documentos:

```powershell
.\.venv\Scripts\python.exe -m app.ingest
```

Enciende la API y la consola, cada una en su terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api:app --port 8000
```

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/consola.py
```

### Voz natural (opcional)

```powershell
.\.venv\Scripts\python.exe -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
.\.venv\Scripts\python.exe -m pip install -r requirements-voz-natural.txt
.\.venv\Scripts\python.exe -m scripts.descargar_voces_referencia
```

Con la voz natural y el avatar a la vez, la GPU de 16 GB queda al límite (unos 15.5 GB) y las respuestas salen más lentas.

## Configuración

Todo se configura en el archivo `.env` de la raíz del proyecto. El instalador lo crea a partir de `.env.example`; para hacerlo a mano, copia ese archivo como `.env`. No hay que reiniciar Windows ni usar `setx`: basta con apagar y volver a encender el asistente. Una variable definida en la terminal gana sobre `.env`.

| Variable | Por omisión | Qué controla |
|---|---|---|
| `LLM_MODEL` | `gemma3:12b` | Modelo de lenguaje (`gemma3:4b` con 6 a 8 GB de GPU) |
| `LLM_BASE_URL` | `http://127.0.0.1:11434/v1` | Servidor del modelo de lenguaje |
| `EMBED_MODEL` | `bge-m3` | Modelo para buscar en los documentos |
| `EMBED_BASE_URL` | `http://127.0.0.1:11434/v1` | Servidor de ese modelo |
| `WHISPER_MODEL` | `large-v3-turbo` | Modelo de reconocimiento de voz (`small` con poca GPU) |
| `WHISPER_DEVICE` | `cuda` | `cuda` para GPU, `cpu` para procesador |
| `WHISPER_COMPUTE` | `int8_float16` | Precisión del reconocimiento; en CPU usar `int8` |
| `CHATTERBOX_DEVICE` | `cuda` | Dispositivo de la voz natural |
| `INSTITUTION` | `Tecnológico de Monterrey (Escuela de Ingeniería y Ciencias)` | Institución que aparece en las instrucciones al modelo |
| `ASSISTANT_NAME` | `TecBot` | Nombre del asistente si no hay perfiles |
| `ADMIN_TOKEN` | (vacío) | Clave de la consola y de las rutas de administración de la API |
| `SESSION_TTL_MINUTES` | `60` | Minutos sin actividad tras los que se olvida una conversación |
| `MAX_UPLOAD_MB` | `50` | Tamaño máximo de un archivo subido |
| `LANGUAGE_DETECT_CONFIDENCE` | `0.8` | Qué tan seguro debe estar Whisper para cambiar de idioma solo |
| `TEAMS_BROWSER` | (Chrome, luego Edge) | Navegador para entrar a reuniones: `chrome`, `msedge` o `chromium` |

Las variables `LLM_BASE_URL` y `EMBED_BASE_URL` permiten apuntar a un servidor con GPU en lugar de a la misma computadora. Cualquier servidor compatible con la API de OpenAI sirve.

### Clave de administración

Sin `ADMIN_TOKEN`, cualquiera que llegue a la consola o a la API puede subir y borrar documentos. Para usarlo con más gente en la red, pon una clave larga:

```
ADMIN_TOKEN=una-clave-larga-y-dificil
```

Con la clave, la consola la pide al abrirla y la API rechaza las rutas de administración sin el encabezado `X-Admin-Token`. La página del avatar sigue abierta, porque los estudiantes no tienen clave.

Los asistentes, sus voces, sus personajes y su acceso a documentos no se configuran aquí, sino en la consola. Ver [manual_consola.md](manual_consola.md).

## Pruebas

Las pruebas unitarias no necesitan GPU, Ollama ni Whisper: simulan los modelos y usan una base vectorial temporal.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app scripts tests
```

Si Chroma no puede correr en la computadora (por ejemplo, con muy poca memoria libre), `$env:PRUEBAS_CHROMA = "simulado"` usa una versión en memoria que respeta sus mismas reglas de filtros.

Las pruebas con los modelos reales están en [demostracion.md](demostracion.md#pruebas-automáticas).

## Problemas comunes

| Síntoma | Causa | Solución |
|---|---|---|
| "No se pudo conectar con Ollama" | Ollama está cerrado | Ábrelo o ejecuta `iniciar.bat` |
| Error de puerto en uso al encender | Ya hay una API o consola encendida | Cierra la ventana anterior |
| Las respuestas tardan unos 10 segundos | Se usa `localhost` en lugar de `127.0.0.1` en la configuración | Deja las direcciones por omisión; en Windows `localhost` agrega unos 2 segundos por conexión |
| La API se cierra sola al indexar, con `access violation` u `OpenBLAS error: Memory allocation` | Poca memoria RAM libre | Cierra programas pesados (emuladores, Android Studio, muchas pestañas) y vuelve a encender |
| El instalador dice que no encuentra Python | Solo hay un Python de MSYS2, Git Bash o 3.14 | `winget install -e --id Python.Python.3.12` |
| `CUDA out of memory` al hablar | La GPU no alcanza para el modelo y Whisper | En `.env` usa `LLM_MODEL=gemma3:4b` y `WHISPER_MODEL=small`, o `WHISPER_DEVICE=cpu` con `WHISPER_COMPUTE=int8` |
| La API se cierra con "Could not load symbol cudnnGetLibConfig" | Dos versiones de cuDNN cargadas | Ya está resuelto en `app/voice.py`; si reaparece, reinstala con `instalar.ps1` |
| Error `av.open() got unexpected keyword` | Versión nueva de PyAV | `requirements.txt` ya fija `av<16`; reinstala las librerías |
| El avatar no aparece | Faltan los personajes | `python -m scripts.descargar_avatares` |
| La consola dice "Falta la clave de administración" | `ADMIN_TOKEN` cambió en `.env` | Vuelve a abrir la consola y escribe la clave nueva |
| No se puede borrar un Excel desde la consola | El archivo está abierto en otro programa | Ciérralo e inténtalo de nuevo |
| El micrófono no funciona en la página | Permiso denegado en el navegador | Permite el micrófono para `localhost:8000` |

## Qué se probó de la instalación

- El instalador se ejecutó con `-Minimo` en una copia limpia del proyecto, sin entorno, voces, personajes ni índice, en la misma computadora de desarrollo. Terminó en 1.9 minutos, con las librerías ya en la caché de pip.
- La copia recién instalada se encendió y contestó una pregunta por texto, sintetizó voz y la reconoció en GPU.
- Ollama y sus modelos ya estaban instalados, así que la descarga de modelos (9.4 GB) y la instalación de Ollama con winget no se ejercitaron.
- Las opciones sin `-Minimo` y `-VozNatural` no se probaron en la copia limpia; la instalación de desarrollo usa esas mismas librerías y voces.
- En una laptop con RTX 3050 de 6 GB se comprobó la parte nueva del instalador (pasos 1 y 2): descarta el Python de MSYS2, elige el de python.org y crea `.env` con `gemma3:4b` y Whisper `small`. La instalación completa en esa máquina todavía no se ha hecho.
- No se ha probado en Linux o macOS, ni sin GPU.