# Recomendaciones para evolucionar el MVP

El prototipo demuestra que el recorrido completo funciona en una computadora. Para que sea un servicio institucional faltan cosas de cuatro tipos, ordenadas aquí por prioridad.

## 1. Lo indispensable antes de usarlo con estudiantes

**Base de conocimiento real.** Hoy solo hay dos documentos de ejemplo. Cargar planes de estudio, reglamentos y preguntas frecuentes vigentes, y nombrar a un responsable de mantenerlos al día por área. Un asistente con datos viejos es peor que no tener asistente.

**Evaluación con preguntas reales.** Ampliar `tests/preguntas.jsonl` con preguntas que los estudiantes hacen de verdad y sus respuestas correctas, y correrla en cada cambio de documentos o de modelo. La lista de preguntas sin respuesta del historial (que ahora se descarga en CSV) es la mejor fuente.

**Acceso a la consola.** Ya hay una clave de administración (`ADMIN_TOKEN`) que protege la consola y las rutas de administración de la API. Falta el inicio de sesión institucional y los roles (quién sube documentos, quién publica, quién crea asistentes).

**Aviso de privacidad.** El historial guarda las preguntas, y en reuniones se transcribe lo que dicen los participantes. Definir qué se guarda, cuánto tiempo y cómo se avisa. En reuniones, que el asistente se presente como programa al entrar.

**Licencias.** Cuatro de los cinco personajes son solo para uso no comercial; conviene encargar o generar personajes propios. Revisar la licencia de cada voz y los términos de uso de Gemma, o cambiar a un modelo con licencia abierta sin condiciones.

## 2. Infraestructura

**Servidor con GPU.** Pasar los modelos a un servidor institucional. El código ya lo permite: basta apuntar `LLM_BASE_URL` y `EMBED_BASE_URL` a ese servidor. La página del avatar y la consola pueden quedar en un servidor web común.

**Varias personas a la vez.** Ollama está pensado para uso personal y no se probó con usuarios simultáneos. Para muchos a la vez conviene un servidor de inferencia pensado para eso, como vLLM, que también ofrece la API de OpenAI.

**Memoria de las conversaciones.** Las sesiones viven en la memoria del proceso, ya con límite de turnos, caducidad y tope (`app/sessions.py`), pero se pierden al reiniciar y no se comparten entre varios servidores. Guardarlas en una base de datos (Redis o SQL), igual que el historial, que hoy es un archivo.

**Dependencias de la página.** Resuelto: three.js se sirve desde `web/vendor/three/` (se actualiza con `python -m scripts.vendorizar_three`).

**Despliegue.** Empaquetar en contenedores con los modelos ya descargados, para instalar igual en cualquier servidor.

## 3. Integración con Teams

La conexión actual entra por la versión web de Teams como invitado. Es suficiente para demostrar, pero frágil para producción: depende de los botones de la página y no entra a reuniones que exigen iniciar sesión.

El camino institucional es un **bot oficial de Teams**: una aplicación registrada en Microsoft Entra que entra a las reuniones por la API de Microsoft Graph, con acceso al audio y video. Requiere:

- registro de la aplicación y permisos aprobados por el área de TI;
- un servicio en Windows con el SDK de medios de Microsoft, alojado en Azure;
- adaptar la salida de imagen y voz del avatar a ese servicio.

A cambio se obtiene entrada sin sala de espera, identidad propia del asistente, saber quién habla y estabilidad ante cambios de la interfaz.

Mientras tanto, lo más barato es pedir a TI que permita invitados anónimos en las reuniones donde se quiera usar.

## 4. Calidad de la experiencia

**Turnos de conversación.** Hoy el asistente decide que alguien terminó de hablar tras 0.9 segundos de silencio, lo que corta preguntas con pausas. Un detector de fin de turno que use el contenido de la frase lo haría más natural.

**Saber quién habla** en una reunión, para que solo quien preguntó pueda interrumpir. El bot oficial lo da directamente.

**Voz.** La voz rápida suena sintética. La voz natural ya está integrada pero deja la GPU al límite; con un servidor de más memoria puede ser la voz por omisión.

**Avatar.** Los personajes de ejemplo son de estilo caricatura. Ya se pueden subir personajes propios (`.glb`) desde la consola. Si se busca un rostro realista, hay que evaluar generación de video, que es mucho más costosa en GPU.

**Respuestas con formato.** Mostrar en pantalla enlaces, tablas o pasos numerados además de decirlos.

**Canales de respaldo.** Cuando el asistente no sabe, ofrecer el contacto del área responsable según la categoría de la pregunta, en vez de una sugerencia genérica.

## 5. Reutilizarlo para otros servicios

El diseño ya separa lo que cambia de un servicio a otro:

| Para adaptar a otro servicio | Dónde se cambia |
|---|---|
| Información | Documentos y preguntas frecuentes en la consola |
| Función y personalidad | Perfil del asistente en la consola |
| Nombre, voz y personaje | Perfil del asistente en la consola |
| A qué información accede | Acceso del perfil, por categoría o por documento |
| Idioma | Perfil y selector de la página |

La institución que aparece en las instrucciones del modelo ya es configurable (`INSTITUTION` en `.env`). Las instrucciones completas están en `app/prompts.py`; después de cambiarlas hay que correr la evaluación.

## Orden sugerido

1. Base de conocimiento real, evaluación con preguntas reales y aviso de privacidad.
2. Acceso a la consola y personajes con licencia propia.
3. Servidor con GPU y memoria de conversaciones.
4. Piloto con un grupo pequeño y revisión semanal de las preguntas sin respuesta.
5. Bot oficial de Teams, si el piloto muestra que las reuniones son un canal útil.
