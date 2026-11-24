"""Consola de administración.  Uso:  streamlit run app/consola.py   (requiere la API corriendo)

Permite gestionar documentos, preguntas frecuentes y asistentes, probar respuestas y
revisar el historial, todo a través de la API. No tiene usuarios ni contraseñas.
"""
import os

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")  # no "localhost": en Windows agrega ~2 s
AVATAR_URL = os.getenv("AVATAR_URL", "http://localhost:8000/avatar/")
LANGUAGES = {"es": "Español", "en": "English", "fr": "Français", "sv": "Svenska", "de": "Deutsch"}
ENGINES = {"piper": "Piper (rápida)", "chatterbox": "Chatterbox (natural, más lenta)"}
MOODS = ["neutral", "happy", "love", "sad", "angry", "fear", "disgust", "sleep"]
FILE_TYPES = ["pdf", "docx", "xlsx", "txt", "md"]
NEW = "➕ Nuevo…"


class ApiError(Exception):
    pass


def api(method: str, path: str, timeout: int = 120, **kwargs):
    """Llama a la API y devuelve el JSON; convierte los fallos en un mensaje legible."""
    try:
        resp = requests.request(method, f"{API_URL}{path}", timeout=timeout, **kwargs)
    except requests.RequestException as error:
        raise ApiError(f"No se pudo contactar la API en {API_URL}. ¿Está encendida? ({error})") from error
    if not resp.ok:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise ApiError(f"{detail} (error {resp.status_code})")
    return resp.json()


def notify(message: str) -> None:
    """Muestra un aviso que sobrevive al st.rerun() que sigue a cada cambio."""
    st.session_state["notice"] = message
    st.rerun()


def category_input(categories: list[str], key: str, current: str = "general") -> str:
    """Selector de categoría con opción de escribir una nueva."""
    options = sorted(set(categories) | {current}) + [NEW]
    choice = st.selectbox("Categoría", options, index=options.index(current), key=f"{key}_select")
    if choice != NEW:
        return choice
    return st.text_input("Nombre de la nueva categoría", key=f"{key}_new").strip()


# ---------- Documentos ----------

def page_documents():
    st.title("Documentos")
    st.caption("Archivos que forman la base de conocimiento. Al subir o borrar uno, el asistente lo sabe de inmediato.")
    categories = api("GET", "/categories")

    with st.expander("Subir documentos", expanded=True):
        files = st.file_uploader("Archivos (PDF, Word, Excel o texto)", type=FILE_TYPES, accept_multiple_files=True)
        category = category_input(categories, "upload")
        if st.button("Subir e indexar", type="primary", disabled=not files or not category):
            results = []
            with st.spinner("Procesando documentos…"):
                for file in files:
                    saved = api("POST", "/documents", files={"file": (file.name, file.getvalue())},
                                data={"category": category}, timeout=600)
                    results.append(f"{file.name}: {saved['chunks']} fragmentos")
            notify("Documentos indexados. " + "; ".join(results))

    docs = api("GET", "/documents")
    if not docs:
        st.info("Todavía no hay documentos.")
        return
    st.subheader(f"Documentos cargados: {len(docs)}")
    table = pd.DataFrame(docs)[["name", "category", "kilobytes", "chunks"]]
    table.columns = ["Documento", "Categoría", "Tamaño (KB)", "Fragmentos"]
    event = st.dataframe(table, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row")
    st.caption("Selecciona una fila para ver su contenido indexado o eliminar el documento.")

    if event.selection.rows:
        doc = docs[event.selection.rows[0]]
        st.subheader(doc["name"])
        left, right = st.columns([3, 1])
        if right.button("Eliminar documento", type="primary"):
            api("DELETE", "/documents", params={"source": doc["source"]})
            notify(f"Se eliminó {doc['name']}.")
        chunks = api("GET", "/documents/chunks", params={"source": doc["source"]})
        left.write(f"Categoría **{doc['category']}** · {len(chunks)} fragmentos indexados")
        for i, text in enumerate(chunks, 1):
            with st.expander(f"Fragmento {i}"):
                st.text(text)

    st.divider()
    if st.button("Reindexar todo", help="Vuelve a procesar todos los documentos y preguntas frecuentes"):
        with st.spinner("Reindexando…"):
            result = api("POST", "/reindex", timeout=1800)
        notify(f"Se reindexaron {len(result)} documentos.")


# ---------- Preguntas frecuentes ----------

def page_faqs():
    st.title("Preguntas frecuentes")
    st.caption("Respuestas cortas que no vienen en ningún documento. El asistente las usa igual que los documentos.")
    categories = api("GET", "/categories")
    faqs = api("GET", "/faqs")

    with st.expander("Agregar pregunta", expanded=not faqs):
        question = st.text_input("Pregunta", key="faq_new_question")
        answer = st.text_area("Respuesta", key="faq_new_answer")
        category = category_input(categories, "faq_new")
        if st.button("Agregar", type="primary", disabled=not (question.strip() and answer.strip() and category)):
            api("POST", "/faqs", json={"question": question.strip(), "answer": answer.strip(), "category": category})
            for key in ("faq_new_question", "faq_new_answer"):
                del st.session_state[key]
            notify("Pregunta agregada.")

    st.subheader(f"Preguntas guardadas: {len(faqs)}")
    for faq_id, faq in faqs.items():
        with st.expander(f"{faq['question']}  ·  {faq['category']}"):
            question = st.text_input("Pregunta", faq["question"], key=f"q_{faq_id}")
            answer = st.text_area("Respuesta", faq["answer"], key=f"a_{faq_id}")
            category = category_input(categories, f"c_{faq_id}", faq["category"])
            save, delete, _ = st.columns([1, 1, 4])
            if save.button("Guardar", key=f"s_{faq_id}", disabled=not (question.strip() and answer.strip() and category)):
                api("PUT", f"/faqs/{faq_id}",
                    json={"question": question.strip(), "answer": answer.strip(), "category": category})
                notify("Pregunta actualizada.")
            if delete.button("Eliminar", key=f"d_{faq_id}"):
                api("DELETE", f"/faqs/{faq_id}")
                notify("Pregunta eliminada.")


# ---------- Asistentes ----------

def page_profiles():
    st.title("Asistentes")
    st.caption("Cada asistente tiene su nombre, personalidad, voz, personaje y las categorías que consulta.")
    profiles = api("GET", "/profiles")
    avatars = {a["id"]: a["name"] for a in api("GET", "/avatar/avatars.json")}
    categories = api("GET", "/categories")

    choice = st.selectbox("Asistente", list(profiles) + [NEW],
                          format_func=lambda key: profiles[key]["name"] if key in profiles else key)
    is_new = choice == NEW
    p = {} if is_new else profiles[choice]
    key = "new" if is_new else choice  # las claves de los campos cambian con el asistente elegido

    profile_id = choice
    if is_new:
        profile_id = st.text_input("Identificador (sin espacios, por ejemplo asesor-imt)", key="new_id").strip().lower()

    left, right = st.columns(2)
    name = left.text_input("Nombre", p.get("name", ""), key=f"{key}_name")
    description = right.text_input("Descripción", p.get("description", ""), key=f"{key}_description")
    personality = st.text_area(
        "Personalidad y forma de hablar", p.get("personality", ""), key=f"{key}_personality",
        help="Solo cambia el tono. El asistente sigue contestando únicamente con la base de conocimiento.")
    greeting = st.text_input("Saludo inicial", p.get("greeting", ""), key=f"{key}_greeting")

    left, middle, right = st.columns(3)
    language = left.selectbox("Idioma predeterminado", list(LANGUAGES), format_func=LANGUAGES.get,
                              index=list(LANGUAGES).index(p.get("language", "es")), key=f"{key}_language")
    avatar_ids = list(avatars)
    avatar = middle.selectbox("Personaje", avatar_ids, format_func=avatars.get, key=f"{key}_avatar",
                              index=avatar_ids.index(p["avatar"]) if p.get("avatar") in avatars else 0)
    mood = right.selectbox("Expresión base", MOODS, index=MOODS.index(p.get("mood", "neutral")), key=f"{key}_mood")

    engine = st.selectbox("Motor de voz", list(ENGINES), format_func=ENGINES.get,
                          index=list(ENGINES).index(p.get("engine", "piper")), key=f"{key}_engine")
    voices = {}
    with st.expander("Voz en cada idioma", expanded=True):
        columns = st.columns(len(LANGUAGES))
        for column, (code, label) in zip(columns, LANGUAGES.items()):
            options = api("GET", "/voices", params={"language": code, "engine": engine})
            saved = p.get("voices", {}).get(code) if engine == p.get("engine") else None
            voice = column.selectbox(label, options, index=options.index(saved) if saved in options else 0,
                                     key=f"{key}_{engine}_voice_{code}")
            if voice:
                voices[code] = voice

    selected = st.multiselect(
        "Categorías que consulta (vacío = todas)", sorted(set(categories) | set(p.get("categories", []))),
        default=p.get("categories", []), key=f"{key}_categories")

    valid_id = bool(profile_id) and profile_id.replace("-", "").replace("_", "").isalnum()
    if is_new and profile_id in profiles:
        st.warning("Ya existe un asistente con ese identificador.")
        valid_id = False
    save, delete, link = st.columns([1, 1, 3])
    if save.button("Guardar", type="primary", disabled=not (valid_id and name.strip())):
        api("PUT", f"/profiles/{profile_id}", json={
            "name": name.strip(), "description": description.strip(), "personality": personality.strip(),
            "greeting": greeting.strip(), "language": language, "engine": engine, "voices": voices,
            "avatar": avatar, "mood": mood, "categories": selected,
        })
        notify(f"Asistente «{name.strip()}» guardado.")
    if not is_new:
        if delete.button("Eliminar", disabled=len(profiles) <= 1):
            api("DELETE", f"/profiles/{profile_id}")
            notify(f"Asistente «{p['name']}» eliminado.")
        link.link_button("Abrir en la página del avatar", f"{AVATAR_URL}?perfil={profile_id}")


# ---------- Probar ----------

def page_test():
    st.title("Probar")
    st.caption("Haz una pregunta y revisa la respuesta y los fragmentos que usó. Estas pruebas no se guardan en el historial.")
    profiles = api("GET", "/profiles")

    with st.form("test"):
        left, right = st.columns(2)
        profile = left.selectbox("Asistente", list(profiles), format_func=lambda k: profiles[k]["name"])
        language = right.selectbox("Idioma", list(LANGUAGES), format_func=LANGUAGES.get)
        message = st.text_input("Pregunta")
        submitted = st.form_submit_button("Preguntar", type="primary")
    if submitted and message.strip():
        with st.spinner("Pensando…"):
            st.session_state["test_result"] = api(
                "POST", "/test", json={"message": message.strip(), "language": language, "profile": profile})

    result = st.session_state.get("test_result")
    if result:
        if result["answered"]:
            st.success(result["answer"])
        else:
            st.warning(f"Sin información en la base de conocimiento.\n\n{result['answer']}")
        st.caption(f"Consulta de búsqueda: {result['search_query']}")
        st.subheader(f"Fragmentos consultados ({len(result['chunks'])})")
        for chunk in result["chunks"]:
            similarity = max(0.0, 1 - chunk["distance"])
            with st.expander(f"{chunk['source']}  ·  {chunk['category']}  ·  parecido {similarity:.0%}"):
                st.text(chunk["text"])

    st.divider()
    st.subheader("Evaluación")
    st.caption("Corre las preguntas de control de tests/preguntas.jsonl. Úsala después de cambiar documentos o asistentes.")
    if st.button("Correr evaluación"):
        with st.spinner("Evaluando; tarda alrededor de un minuto…"):
            st.session_state["eval_result"] = api("POST", "/eval", timeout=1800)
    evaluation = st.session_state.get("eval_result")
    if evaluation:
        passed = sum(case["passed"] for case in evaluation)
        st.metric("Preguntas correctas", f"{passed} de {len(evaluation)}")
        table = pd.DataFrame({
            "Resultado": ["✅" if case["passed"] else "❌" for case in evaluation],
            "Pregunta": [case["question"] for case in evaluation],
            "Debía contestar": ["Sí" if case["expected_answer"] else "No" for case in evaluation],
            "Respuesta": [case["answer"] for case in evaluation],
        })
        st.dataframe(table, hide_index=True, width="stretch")


# ---------- Historial ----------

RATINGS = {None: "—", "good": "👍 Buena", "bad": "👎 Mala"}


def page_history():
    st.title("Historial y estadísticas")
    stats = api("GET", "/stats")
    if not stats["total"]:
        st.info("Todavía no hay preguntas registradas.")
        return

    cells = st.columns(5)
    cells[0].metric("Preguntas", stats["total"])
    cells[1].metric("Contestadas", f"{stats['answered'] / stats['total']:.0%}")
    cells[2].metric("Sin respuesta", stats["unanswered"])
    cells[3].metric("Conversaciones", stats["sessions"])
    cells[4].metric("Valoraciones", f"👍 {stats['good']}  👎 {stats['bad']}")

    left, middle, right = st.columns([2, 1, 1])
    left.caption("Preguntas por día")
    left.bar_chart(pd.Series(stats["by_day"], name="Preguntas"))
    middle.caption("Por idioma")
    middle.bar_chart(pd.Series({LANGUAGES.get(k, k): v for k, v in stats["by_language"].items()}, name="Preguntas"))
    right.caption("Por asistente")
    right.bar_chart(pd.Series(stats["by_profile"], name="Preguntas"))

    if stats["top_unanswered"]:
        st.subheader("Preguntas sin respuesta más repetidas")
        st.caption("Son la guía para saber qué documentos o preguntas frecuentes faltan.")
        st.dataframe(pd.DataFrame(stats["top_unanswered"], columns=["Pregunta", "Veces"]),
                     hide_index=True, width="stretch")

    st.subheader("Preguntas recientes")
    only_unanswered = st.toggle("Solo sin respuesta")
    entries = api("GET", "/history", params={"limit": 300, "unanswered": only_unanswered})
    if not entries:
        st.info("No hay preguntas con ese filtro.")
        return
    table = pd.DataFrame({
        "Fecha": [e["time"].replace("T", " ") for e in entries],
        "Asistente": [e["profile"] for e in entries],
        "Idioma": [e["language"] for e in entries],
        "Pregunta": [e["question"] for e in entries],
        "Respuesta": [e["answer"] for e in entries],
        "Contestada": [e["answered"] for e in entries],
        "Valoración": [RATINGS[e["feedback"]] for e in entries],
    })
    edited = st.data_editor(
        table, hide_index=True, width="stretch", key=f"history_{only_unanswered}",
        disabled=[c for c in table.columns if c != "Valoración"],
        column_config={"Valoración": st.column_config.SelectboxColumn(options=list(RATINGS.values()), required=True)},
    )
    st.caption("Cambia la columna Valoración para marcar una respuesta como buena o mala.")
    by_label = {label: rating for rating, label in RATINGS.items()}
    changed = [i for i in range(len(entries)) if edited["Valoración"][i] != table["Valoración"][i]]
    for i in changed:
        api("PUT", f"/history/{entries[i]['id']}/feedback", json={"rating": by_label[edited["Valoración"][i]]})
    if changed:
        notify("Valoración guardada.")


# ---------- Navegación ----------

st.set_page_config(page_title="Consola · Asistente Tec", page_icon="🎓", layout="wide")
pages = [
    st.Page(page_documents, title="Documentos", icon="📄", url_path="documentos", default=True),
    st.Page(page_faqs, title="Preguntas frecuentes", icon="❓", url_path="preguntas"),
    st.Page(page_profiles, title="Asistentes", icon="🧑‍🏫", url_path="asistentes"),
    st.Page(page_test, title="Probar", icon="🧪", url_path="probar"),
    st.Page(page_history, title="Historial", icon="📊", url_path="historial"),
    st.Page("ui.py", title="Chat de voz", icon="💬", url_path="chat"),
]
page = st.navigation(pages)

with st.sidebar:
    st.link_button("Abrir página del avatar", AVATAR_URL)
    try:
        health = api("GET", "/health", timeout=10)
        st.caption(f"API conectada · {health['chunks']} fragmentos · {health['llm']}")
    except ApiError as error:
        st.error(str(error))

if notice := st.session_state.pop("notice", None):
    st.toast(notice, icon="✅")
try:
    page.run()
except ApiError as error:
    st.error(str(error))
