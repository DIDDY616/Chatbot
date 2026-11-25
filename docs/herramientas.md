# Herramientas externas evaluadas

Qué se revisó para mejorar el MVP, qué se integró y qué queda como recomendación. Revisado en noviembre de 2026; las versiones y requisitos cambian rápido, así que conviene confirmarlos en cada repositorio antes de instalar.

## Integradas

| Herramienta | Para qué | Por qué esta | Licencia |
|---|---|---|---|
| [trafilatura](https://github.com/adbar/trafilatura) 2.x | Importar páginas web oficiales a la base de conocimiento ([app/web_import.py](../app/web_import.py)) | Extrae el texto principal y descarta menús y pies de página. Es Python puro y conocida para este uso | Apache 2.0 |
| Playwright (ya estaba, para Teams) | Armar con un navegador sin ventana las páginas que se construyen con JavaScript, como varias de tec.mx | No agrega dependencias: reutiliza la que ya usa la conexión a Teams | Apache 2.0 |
| BM25 con Reciprocal Rank Fusion, programado sin librerías ([app/keyword.py](../app/keyword.py)) | Búsqueda híbrida: vectores más palabras exactas | Los vectores confunden siglas, claves de materias y números ("ITC", "TC1001", "480 horas"). La búsqueda por palabras los encuentra, y RRF combina las dos listas por posición sin ajustar puntajes ([Pinecone](https://docs.pinecone.io/guides/search/reciprocal-rank-fusion), [Elastic](https://www.elastic.co/search-labs/blog/improving-information-retrieval-elastic-stack-hybrid)). Para miles de fragmentos se calcula al vuelo; no hace falta otro índice | Propio |

**Lo que se comprobó con la página real.** La página de la carrera ([tec.mx, BS in Computer Science and Technology](https://tec.mx/en/engineering-and-sciences/bs-in-computer-science-and-technology)) se importa bien sin abrir navegador: unos 4,000 caracteres con el plan por semestre, en 6 fragmentos. La página general de la Escuela casi no tiene texto (es un buscador), así que no sirve de fuente. Para planes de estudio completos, el Tec publica PDF oficiales (por ejemplo, el [catálogo de planes de estudio](https://tec.mx/sites/default/files/repositorio/conocenos/sacscoc/catalogos/profesional/catalogo-profesional-esp.pdf) y la [hoja resumen de ITC](https://tec.mx/sites/default/files/inline-files/OnePage%20ITC_digital.pdf)), que se descargan y se suben como documento.

**Sobre la búsqueda híbrida.** Hay reportes de que RRF con pesos iguales no siempre mejora el primer resultado en todas las colecciones ([RankFuse](https://pypi.org/project/rankfuse/)). Por eso se puede apagar con `HYBRID_SEARCH=false` en `.env`, y hay que correr la evaluación con documentos reales para decidir.

## Recomendadas, no integradas

| Herramienta | Qué daría | Por qué no se integró | Cuándo conviene |
|---|---|---|---|
| [Kokoro](https://github.com/hexgrad/kokoro) (82M parámetros) | Voz más natural que Piper con muy poca GPU; tiene voces en español (`ef_dora`, `em_alex`) | Necesita PyTorch (unos 3 GB más de instalación) y no tiene sueco ni alemán, así que Piper seguiría para esos dos. No se pudo probar sin los modelos instalados | Como tercer motor de voz para español, inglés y francés. Su licencia es Apache 2.0, más permisiva que la de Piper (GPL) ([guía 2026](https://tts.ai/blog/open-source-text-to-speech-guide-2026/)) |
| [MuseTalk 1.5](https://arxiv.org/abs/2410.10122) | Avatar con rostro realista a partir de una foto o video, con labios sincronizados en tiempo real (más de 30 cuadros por segundo a 256×256 en una V100) | Corre en el servidor y genera video: necesita una GPU dedicada aparte del modelo de lenguaje (un fork no oficial pide 8 GB como mínimo). En la laptop de 6 GB no cabe junto con lo demás | En el servidor institucional con GPU, si se quiere un rostro realista en vez del personaje 3D. Habría que mandar video al navegador en lugar de animar el personaje ahí |
| LatentSync | Labios de mejor calidad que MuseTalk | No es en tiempo real ([sync.so](https://sync.so/blog/what-is-musetalk)) | Para videos pregrabados (bienvenida, tutoriales), no para conversar |
| Reordenador (reranker) multilingüe, como bge-reranker-v2-m3 | Reordena los fragmentos encontrados con un modelo que lee la pregunta y el fragmento juntos; suele mejorar el primer resultado | Ollama no los sirve y agregaría PyTorch. Con la búsqueda híbrida y una base chica la ganancia es menor | Cuando la base de conocimiento tenga cientos de documentos |
| Bot oficial de Teams (Microsoft Graph y su SDK de medios) | Entrar a reuniones institucionales, saber quién habla | Requiere registro de la aplicación, permisos de TI y un servicio en Azure (ver [evolucion.md](evolucion.md#3-integración-con-teams)) | Si el piloto muestra que las reuniones son un canal útil |
