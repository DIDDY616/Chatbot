# Asistente Tec

MVP de un asistente virtual con avatar en video para estudiantes. Contesta por voz o por texto con información de una base de conocimiento propia, en cinco idiomas, y puede entrar a una reunión de Microsoft Teams con su avatar y su voz.

Todo corre en una sola computadora, con modelos de código o pesos abiertos, sin servicios de pago ni cuentas externas. La página del avatar funciona sin internet.

![El asistente contestando una pregunta](docs/img/avatar_respuesta.png)

## Qué hace

- Responde preguntas con una base de conocimiento propia (RAG) y cita de qué documentos sale la respuesta. Busca por significado y por palabras exactas (siglas, claves de materias, números).
- Identifica la intención: los saludos y agradecimientos se contestan sin buscar en los documentos.
- Dice cuando no tiene la información y sugiere validarla con una fuente institucional.
- Conversa por voz o por texto y recuerda el contexto de la sesión.
- Habla español, inglés, francés, sueco y alemán, y al hablar detecta el idioma del estudiante.
- Tiene un avatar 3D con labios sincronizados con la voz; se pueden subir personajes propios.
- Permite varios asistentes, cada uno con su función, personalidad, voz, personaje y acceso a documentos.
- Entra a reuniones de Teams como invitado y contesta cuando dicen su nombre.
- Incluye una consola de administración: documentos (también importados de páginas web oficiales) en borrador o publicados, preguntas frecuentes, asistentes, personajes, pruebas, historial con valoraciones y reuniones.

## Instalación rápida

Requisitos: Windows 10 u 11 (o una Mac con Apple Silicon, ver abajo), Python 3.10 a 3.13 de python.org (de preferencia 3.12), una GPU NVIDIA (6 GB como mínimo, 12 GB o más para el modelo grande) y unos 25 GB de disco. El porqué de la GPU está en [docs/arquitectura.md](docs/arquitectura.md#por-qué-gpu-y-por-qué-local).

```powershell
powershell -ExecutionPolicy Bypass -File instalar.ps1
```

El instalador detecta la memoria de la GPU y crea `.env` con los modelos adecuados. Para encenderlo:

```powershell
.\iniciar.bat
```

En Mac con Apple Silicon se instala a mano y se enciende con `./iniciar.sh` (ver [docs/instalacion.md](docs/instalacion.md#mac-con-apple-silicon-m1-a-m4)).

Se abre la consola en `http://localhost:8501`. La página del avatar queda en `http://localhost:8000/avatar/`.

El paso a paso, la instalación manual, la configuración (`.env`) y la solución de problemas están en [docs/instalacion.md](docs/instalacion.md).

## Pruebas

```powershell
pip install -r requirements-dev.txt
pytest                      # 140 pruebas unitarias, sin GPU ni modelos (simulados)
ruff check app scripts tests
```

Las que usan los modelos reales (evaluación de respuestas, voz, reunión simulada) están en `tests/integracion/` y se corren con `python -m tests.integracion.<nombre>`. GitHub corre las unitarias en cada push (`.github/workflows/pruebas.yml`).

## Documentación

| Documento | Contenido |
|---|---|
| [Instalación y configuración](docs/instalacion.md) | Requisitos, instalador, `.env`, instalación manual, problemas comunes |
| [Arquitectura y tecnologías](docs/arquitectura.md) | Diagrama, componentes, flujo de una pregunta, tecnologías y licencias, por qué GPU y por qué local |
| [Manual de la consola](docs/manual_consola.md) | Uso de cada sección, borradores y publicación, cómo agregar o actualizar información |
| [Integración con Teams](docs/teams.md) | Cómo entra a una reunión, qué se probó y qué límites tiene |
| [Demostración](docs/demostracion.md) | Guion para mostrar cada requisito del encargo y pruebas que lo respaldan |
| [Evolución del MVP](docs/evolucion.md) | Recomendaciones para llevarlo a una solución institucional |
| [Cambios](docs/cambios.md) | Qué se cambió en la limpieza del código y por qué |
| [Herramientas evaluadas](docs/herramientas.md) | Herramientas externas revisadas: cuáles se integraron y cuáles quedan como recomendación |

## Estado

Es un prototipo. Lo más importante que falta:

- La base de conocimiento inicial son dos documentos de ejemplo con datos ficticios. Hay que cargar los documentos reales desde la consola.
- La entrada a Teams funciona en reuniones de cuentas personales. En las de la cuenta institucional del Tec el asistente no entra, porque exigen iniciar sesión y el asistente solo entra como invitado.
- Cuatro de los cinco personajes 3D de ejemplo tienen licencia solo para uso no comercial.
- La clave de administración (`ADMIN_TOKEN`) es una sola para todos; no hay usuarios ni roles.

## Estructura

```
app/            Núcleo: RAG, intención, sesiones, voz, perfiles, publicación, Teams y consola
app/api/        API dividida por tema (conversación, voz, asistentes, conocimiento, calidad, reuniones)
web/            Página del avatar (three.js, TalkingHead y HeadAudio incluidos en web/vendor/)
data/           Documentos, perfiles, preguntas frecuentes, voces e índice
scripts/        Descargas y revisión de la instalación
tests/unit/     Pruebas unitarias (pytest, sin modelos)
tests/integracion/  Pruebas con los modelos reales
docs/           Documentación
```
