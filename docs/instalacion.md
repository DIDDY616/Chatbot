# Instalación y configuración

## Requisitos

### Equipo

| Componente | Mínimo | Probado |
|---|---|---|
| Sistema | Windows 10 u 11 de 64 bits | Windows 11 |
| GPU | NVIDIA con 12 GB de memoria | RTX 4090 de laptop, 16 GB |
| Memoria RAM | 16 GB | |
| Disco | 25 GB libres | |
| Micrófono y bocinas | Para conversar por voz | |
| Internet | Para instalar y para cargar la página del avatar | |

La instalación ocupa unos 15 GB: 9.4 GB de modelos de lenguaje, 2.9 GB de librerías de Python, 1.6 GB del modelo de reconocimiento de voz y 0.7 GB de voces. Con la voz natural son unos 5 GB más.

La GPU es necesaria para conversar por voz con fluidez. La configuración por omisión ocupa unos 11.7 GB de memoria de video. La explicación completa está en [arquitectura.md](arquitectura.md#por-qué-gpu-y-por-qué-local).

Con menos de 12 GB hay que usar un modelo de lenguaje más chico, por ejemplo `gemma3:4b` (ver [Configuración](#configuración)). Esa combinación no se ha probado en este proyecto.

### Programas

| Programa | Para qué | Lo instala el script |
|---|---|---|
| Python 3.10 o posterior | Ejecutar el asistente | No |
| Controladores de NVIDIA | Usar la GPU | No |
| Ollama | Ejecutar el modelo de lenguaje | Sí, si aceptas |
| Chrome o Edge | Página del avatar y entrada a Teams | No (Edge viene con Windows) |

Al instalar Python, marca la casilla "Add python.exe to PATH".

## Instalación rápida

1. Descarga o clona el proyecto.
2. Abre PowerShell en la carpeta del proyecto.
3. Ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File instalar.ps1
```

El script hace siete pasos y avisa en cuál va:

1. Comprueba la versión de Python.
2. Detecta la GPU y avisa si tiene poca memoria.
3. Crea el entorno de Python en `.venv` e instala las librerías.
4. Instala Ollama si falta (pregunta antes) y descarga los modelos `gemma3:12b` y `bge-m3`.
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
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Instala Ollama desde `https://ollama.com/download` y descarga los modelos:

```powershell
ollama pull gemma3:12b
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

Se configura con variables de entorno antes de encender la API. Sin ellas se usan los valores por omisión.

| Variable | Por omisión | Qué controla |
|---|---|---|
| `LLM_MODEL` | `gemma3:12b` | Modelo de lenguaje |
| `LLM_BASE_URL` | `http://127.0.0.1:11434/v1` | Servidor del modelo de lenguaje |
| `EMBED_MODEL` | `bge-m3` | Modelo para buscar en los documentos |
| `EMBED_BASE_URL` | `http://127.0.0.1:11434/v1` | Servidor de ese modelo |
| `WHISPER_MODEL` | `large-v3-turbo` | Modelo de reconocimiento de voz |
| `WHISPER_DEVICE` | `cuda` | `cuda` para GPU, `cpu` para procesador |
| `WHISPER_COMPUTE` | `int8_float16` | Precisión del reconocimiento; en CPU usar `int8` |
| `CHATTERBOX_DEVICE` | `cuda` | Dispositivo de la voz natural |
| `ASSISTANT_NAME` | `TecBot` | Nombre del asistente si no hay perfiles |
| `TEAMS_BROWSER` | (Chrome, luego Edge) | Navegador para entrar a reuniones: `chrome`, `msedge` o `chromium` |

Ejemplo, para usar un modelo más chico:

```powershell
$env:LLM_MODEL = "gemma3:4b"
```

Las variables `LLM_BASE_URL` y `EMBED_BASE_URL` permiten apuntar a un servidor con GPU en lugar de a la misma computadora. Cualquier servidor compatible con la API de OpenAI sirve.

Los asistentes, sus voces, sus personajes y su acceso a documentos no se configuran aquí, sino en la consola. Ver [manual_consola.md](manual_consola.md).

## Problemas comunes

| Síntoma | Causa | Solución |
|---|---|---|
| "No se pudo conectar con Ollama" | Ollama está cerrado | Ábrelo o ejecuta `iniciar.bat` |
| Error de puerto en uso al encender | Ya hay una API o consola encendida | Cierra la ventana anterior |
| Las respuestas tardan unos 10 segundos | Se usa `localhost` en lugar de `127.0.0.1` en la configuración | Deja las direcciones por omisión; en Windows `localhost` agrega unos 2 segundos por conexión |
| La API se cierra con "Could not load symbol cudnnGetLibConfig" | Dos versiones de cuDNN cargadas | Ya está resuelto en `app/voice.py`; si reaparece, reinstala con `instalar.ps1` |
| Error `av.open() got unexpected keyword` | Versión nueva de PyAV | `requirements.txt` ya fija `av<16`; reinstala las librerías |
| El avatar no aparece | Sin internet, o falta descargar los personajes | La página carga three.js desde internet; ejecuta `python -m scripts.descargar_avatares` |
| No se puede borrar un Excel desde la consola | El archivo está abierto en otro programa | Ciérralo e inténtalo de nuevo |
| El micrófono no funciona en la página | Permiso denegado en el navegador | Permite el micrófono para `localhost:8000` |

## Qué se probó de la instalación

- El instalador se ejecutó con `-Minimo` en una copia limpia del proyecto, sin entorno, voces, personajes ni índice, en la misma computadora de desarrollo. Terminó en 1.9 minutos, con las librerías ya en la caché de pip.
- La copia recién instalada se encendió y contestó una pregunta por texto, sintetizó voz y la reconoció en GPU.
- Ollama y sus modelos ya estaban instalados, así que la descarga de modelos (9.4 GB) y la instalación de Ollama con winget no se ejercitaron.
- Las opciones sin `-Minimo` y `-VozNatural` no se probaron en la copia limpia; la instalación de desarrollo usa esas mismas librerías y voces.
- No se ha probado en otra computadora, ni en Linux o macOS.
- No se ha probado sin GPU ni con una GPU de menos de 16 GB.
