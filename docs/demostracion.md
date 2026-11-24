# Demostración funcional

Guion para mostrar, en unos 15 minutos, cada punto que el encargo pide demostrar. Usa los documentos de ejemplo que trae el proyecto.

## Antes de empezar

1. Ejecuta `iniciar.bat` y espera a que se abra la consola.
2. Abre la página del avatar en `http://localhost:8000/avatar/` y pulsa **Comenzar**.
3. Haz una pregunta de calentamiento para que los modelos queden cargados.

## Guion

| Paso | Qué hacer | Qué demuestra |
|---|---|---|
| 1 | Escribe "¿Qué horario tiene la biblioteca?" | Interacción por texto, respuesta con IA, RAG y fuente citada |
| 2 | Pulsa **Hablar** y pregunta "¿Cómo solicito una constancia de estudios?" | Interacción por voz y respuesta del avatar con voz y labios |
| 3 | Pregunta "¿Y cuánto tarda en llegar?" | Conversación de varios turnos con contexto |
| 4 | Pregunta "¿Quién ganó el mundial de 2010?" | Dice que no tiene esa información y sugiere una fuente institucional |
| 5 | Pregunta "¿Cuántos semestres dura la carrera de sistemas?" | Aclara que supone que se refiere a ITC antes de contestar |
| 6 | En Configuración cambia el idioma a English y pregunta "What time does the library open?" | Operación en inglés |
| 7 | En Configuración cambia el personaje y la voz | Personalización de avatar y voz |
| 8 | En Configuración elige el asistente "Asesor ITC" y repite la pregunta 1 | Otro perfil: trato de usted y otro personaje |
| 9 | En la consola, **Documentos**: sube un archivo de texto con un dato nuevo y pregunta por él | Actualización de la base de conocimiento sin tocar código |
| 10 | En la consola, **Preguntas frecuentes**: agrega una y pregunta por ella | Gestión de preguntas frecuentes |
| 11 | En la consola, **Asistentes**: limita un asistente a una categoría y pregunta algo de otra | Acceso a la información según el rol |
| 12 | En la consola, **Probar**: haz una pregunta y abre los fragmentos | Prueba antes de publicar |
| 13 | En la consola, **Historial** | Preguntas sin respuesta, estadísticas y valoraciones |
| 14 | En la consola, **Reuniones**: pega el enlace de una reunión y admítelo | Integración con Teams |
| 15 | En la reunión: "TecBot, ¿qué horario tiene la biblioteca?" | Escucha, contesta y se ve en la reunión |

Para el paso 14 usa una reunión de Teams personal y entra tú primero. Detalles en [teams.md](teams.md).

## Requisitos del encargo y dónde se ven

| Requisito mínimo | Estado | Dónde |
|---|---|---|
| Interacción por voz y texto | Cumplido | Pasos 1 y 2 |
| Respuestas generadas mediante IA | Cumplido | Paso 1 |
| Base de conocimiento con RAG | Cumplido | Pasos 1, 9 y 12 |
| Respuesta mediante avatar con voz | Cumplido | Paso 2 |
| Operación en español e inglés | Cumplido, más francés, sueco y alemán | Paso 6 |
| Personalización de avatar y voz | Cumplido | Pasos 7 y 8 |
| Consola de administración | Cumplido | Pasos 9 a 13 |
| Evidencia de integración con Teams | Cumplido en reuniones personales | Pasos 14 y 15 |
| Varios turnos con contexto | Cumplido | Paso 3 |
| Indicar cuando no sabe | Cumplido | Paso 4 |

Funciones deseables de la consola: historial, preguntas sin respuesta, estadísticas, valoraciones y varios asistentes están incluidas.

## Pruebas automáticas

Respaldan la demostración y se pueden repetir en cualquier momento. Todas necesitan el asistente encendido, salvo la del nombre.

| Comando | Qué comprueba | Último resultado |
|---|---|---|
| `python -m tests.eval` | 17 preguntas con respuesta esperada: datos correctos, seguimiento, negativas, nombres aproximados | 17 de 17 |
| `python -m tests.acceso` | Cada asistente solo usa los documentos que tiene asignados | 6 de 6 |
| `python -m tests.nombre` | Detección del nombre, órdenes de alto y preguntas de presencia | Sin fallas |
| `python -m tests.nombre --voz` | Lo mismo con frases sintetizadas y transcritas | 58 a 59 de 60, según la corrida |
| `python -m tests.puente` | Reunión simulada: el avatar llega como cámara, la voz como micrófono, oye y contesta | 8 de 8 |
| `python -m scripts.revisar` | Que la instalación esté completa | Todo listo |

Ejecuta los comandos con el Python del entorno: `.\.venv\Scripts\python.exe -m tests.eval`.

## Qué no cubre la demostración

- La calidad con documentos reales: los de ejemplo son cortos y ficticios.
- Varias personas usando el asistente a la vez.
- Reuniones de la cuenta institucional del Tec.
- La calidad de la voz y del movimiento del avatar se juzga viéndolo; las pruebas automáticas solo comprueban que haya imagen y sonido.
