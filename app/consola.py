"""Consola de administración.  Uso:  streamlit run app/consola.py   (requiere la API corriendo)

Permite gestionar documentos, preguntas frecuentes, asistentes y personajes, probar
respuestas antes de publicarlas y revisar el historial, todo a través de la API.

Si en .env hay un ADMIN_TOKEN, la consola pide esa clave antes de mostrar nada.
"""
import hmac
import sys
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

# Streamlit ejecuta este archivo como script suelto: se agrega la raíz del proyecto para poder
# leer la misma configuración (.env) que la API.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config  # noqa: E402

API_URL = config.API_URL
AVATAR_URL = config.AVATAR_URL
LANGUAGES = {"es": "Español", "en": "English", "fr": "Français", "sv": "Svenska", "de": "Deutsch"}
ENGINES = {"piper": "Piper (rápida)", "chatterbox": "Chatterbox (natural, más lenta)"}
MOODS = ["neutral", "happy", "love", "sad", "angry", "fear", "disgust", "sleep"]
FILE_TYPES = ["pdf", "docx", "xlsx", "pptx", "csv", "txt", "md"]
STATE_LABEL = {True: "Publicado", False: "Borrador"}
INTENTS = {"consulta": "Consulta", "saludo": "Saludo", "despedida": "Despedida", "agradecimiento": "Agradecimiento"}
CUSTOM_STYLE = "Personalizado"
PERSONALITY_STYLES = {
    "Cercano": "Amigable y cercano. Tutea, usa un tono positivo y frases sencillas.",
    "Formal": "Formal, preciso y respetuoso. Habla de usted, va directo al dato y evita expresiones coloquiales.",
    "Breve y directo": "Muy breve. Contesta en una o dos frases, sin rodeos ni cortesías de más.",
    "Paciente y didáctico": "Paciente y claro. Explica paso a paso, con ejemplos sencillos, y confirma que se entendió.",
    CUSTOM_STYLE: None,
}
NEW = "Nuevo…"


class ApiError(Exception):
    pass


def api(method: str, path: str, timeout: int = 120, raw: bool = False, **kwargs):
    """Llama a la API con la clave de administración y devuelve el JSON (o la respuesta con `raw`)."""
    headers = kwargs.pop("headers", {})
    if token := st.session_state.get("admin_token") or config.ADMIN_TOKEN:
        headers["X-Admin-Token"] = token
    try:
        resp = requests.request(method, f"{API_URL}{path}", timeout=timeout, headers=headers, **kwargs)
    except requests.RequestException as error:
        raise ApiError(f"No se pudo contactar la API en {API_URL}. ¿Está encendida? ({error})") from error
    if not resp.ok:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise ApiError(f"{detail} (error {resp.status_code})")
    return resp if raw else resp.json()


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


# ---------- Acceso ----------

def require_login() -> bool:
    """Con ADMIN_TOKEN definido, pide la clave una vez por sesión del navegador."""
    if not config.ADMIN_TOKEN or st.session_state.get("logged_in"):
        return True
    st.title("Consola del Asistente Tec")
    with st.form("login"):
        key = st.text_input("Clave de administración", type="password")
        if st.form_submit_button("Entrar", type="primary"):
            if hmac.compare_digest(key.encode(), config.ADMIN_TOKEN.encode()):
                st.session_state["logged_in"] = True
                st.session_state["admin_token"] = key
                st.rerun()
            st.error("La clave no es correcta.")
    st.caption("La clave es el valor de ADMIN_TOKEN en el archivo .env del servidor.")
    return False


# ---------- Documentos ----------

def page_documents():
    st.title("Documentos")
    st.caption("Archivos que forman la base de conocimiento. Un documento nuevo queda en borrador: "
               "pruébalo en **Probar** y publícalo cuando esté bien. Los estudiantes solo ven lo publicado.")
    categories = api("GET", "/categories")

    with st.expander("Subir documentos", expanded=True):
        files = st.file_uploader("Archivos (PDF, Word, Excel, PowerPoint, CSV o texto)", type=FILE_TYPES,
                                 accept_multiple_files=True)
        category = category_input(categories, "upload")
        publish_now = st.checkbox("Publicar de inmediato", value=False,
                                  help="Sin marcar, quedan en borrador hasta que los publiques.")
        if st.button("Subir e indexar", type="primary", disabled=not files or not category):
            results = []
            with st.spinner("Procesando documentos…"):
                for file in files:
                    saved = api("POST", "/documents", files={"file": (file.name, file.getvalue())},
                                data={"category": category, "publish": str(publish_now).lower()}, timeout=600)
                    results.append(f"{file.name}: {saved['chunks']} fragmentos")
            state = "publicados" if publish_now else "en borrador"
            notify(f"Documentos indexados y {state}. " + "; ".join(results))

    docs = api("GET", "/documents")
    if not docs:
        st.info("Todavía no hay documentos.")
        return
    drafts = sum(not d["published"] for d in docs)
    head, action = st.columns([3, 1])
    head.subheader(f"Documentos cargados: {len(docs)}" + (f" · {drafts} en borrador" if drafts else ""))
    if drafts and action.button("Publicar todos los borradores"):
        result = api("POST", "/publish-all")
        notify(f"Se publicaron {result['published']} elementos.")

    table = pd.DataFrame(docs)
    table["estado"] = table["published"].map(STATE_LABEL)
    table = table[["name", "category", "estado", "kilobytes", "chunks"]]
    table.columns = ["Documento", "Categoría", "Estado", "Tamaño (KB)", "Fragmentos"]
    event = st.dataframe(table, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row")
    st.caption("Selecciona una fila para ver su contenido indexado, publicarlo o eliminarlo.")

    if event.selection.rows:
        doc = docs[event.selection.rows[0]]
        st.subheader(doc["name"])
        left, publish_col, delete_col = st.columns([3, 1, 1])
        label = "Pasar a borrador" if doc["published"] else "Publicar"
        if publish_col.button(label, type="secondary" if doc["published"] else "primary"):
            api("PUT", "/documents/publish", params={"source": doc["source"]},
                json={"published": not doc["published"]})
            notify(f"{doc['name']}: {'en borrador' if doc['published'] else 'publicado'}.")
        if delete_col.button("Eliminar"):
            api("DELETE", "/documents", params={"source": doc["source"]})
            notify(f"Se eliminó {doc['name']}.")
        chunks = api("GET", "/documents/chunks", params={"source": doc["source"]})
        left.write(f"Categoría **{doc['category']}** · {STATE_LABEL[doc['published']]} · "
                   f"{len(chunks)} fragmentos indexados")
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
    st.caption("Respuestas cortas que no vienen en ningún documento. El asistente las usa igual que los "
               "documentos. Las nuevas quedan en borrador hasta que las publiques.")
    categories = api("GET", "/categories")
    faqs = api("GET", "/faqs")

    with st.expander("Agregar pregunta", expanded=not faqs):
        question = st.text_input("Pregunta", key="faq_new_question")
        answer = st.text_area("Respuesta", key="faq_new_answer")
        category = category_input(categories, "faq_new")
        publish_now = st.checkbox("Publicar de inmediato", value=False, key="faq_new_publish")
        if st.button("Agregar", type="primary", disabled=not (question.strip() and answer.strip() and category)):
            api("POST", "/faqs", json={"question": question.strip(), "answer": answer.strip(),
                                       "category": category, "published": publish_now})
            for key in ("faq_new_question", "faq_new_answer"):
                del st.session_state[key]
            notify("Pregunta agregada.")

    drafts = sum(not f["published"] for f in faqs.values())
    st.subheader(f"Preguntas guardadas: {len(faqs)}" + (f" · {drafts} en borrador" if drafts else ""))
    for faq_id, faq in faqs.items():
        with st.expander(f"{faq['question']}  ·  {faq['category']}  ·  {STATE_LABEL[faq['published']]}"):
            question = st.text_input("Pregunta", faq["question"], key=f"q_{faq_id}")
            answer = st.text_area("Respuesta", faq["answer"], key=f"a_{faq_id}")
            category = category_input(categories, f"c_{faq_id}", faq["category"])
            save, publish, delete, _ = st.columns([1, 1, 1, 3])
            valid = bool(question.strip() and answer.strip() and category)
            if save.button("Guardar", key=f"s_{faq_id}", disabled=not valid):
                api("PUT", f"/faqs/{faq_id}", json={"question": question.strip(), "answer": answer.strip(),
                                                    "category": category, "published": faq["published"]})
                notify("Pregunta actualizada.")
            if publish.button("A borrador" if faq["published"] else "Publicar", key=f"p_{faq_id}"):
                api("PUT", f"/faqs/{faq_id}/publish", json={"published": not faq["published"]})
                notify("Estado actualizado.")
            if delete.button("Eliminar", key=f"d_{faq_id}"):
                api("DELETE", f"/faqs/{faq_id}")
                notify("Pregunta eliminada.")


# ---------- Asistentes ----------

def page_profiles():
    st.title("Asistentes")
    st.caption("Cada asistente tiene su función, su personalidad, su voz y su personaje, y solo consulta "
               "la información que le asignes.")
    profiles = api("GET", "/profiles")
    avatars = {a["id"]: a["name"] for a in api("GET", "/avatars")}
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
    description = right.text_input("Descripción corta (se ve bajo el nombre)", p.get("description", ""),
                                   key=f"{key}_description")
    role = st.text_input(
        "Función: para qué sirve y a quién atiende", p.get("role", ""), key=f"{key}_role",
        placeholder="Por ejemplo: orientar a alumnos de nuevo ingreso sobre inscripciones y becas")

    st.subheader("Personalidad")
    personality_key = f"{key}_personality"
    if personality_key not in st.session_state:
        st.session_state[personality_key] = p.get("personality", "")
    styles = list(PERSONALITY_STYLES)
    current_style = next((s for s, text in PERSONALITY_STYLES.items()
                          if text == st.session_state[personality_key]), CUSTOM_STYLE)

    def use_style():
        text = PERSONALITY_STYLES[st.session_state[f"{key}_style"]]
        if text:
            st.session_state[personality_key] = text

    st.selectbox("Estilo", styles, index=styles.index(current_style), key=f"{key}_style", on_change=use_style,
                 help="Elige uno para empezar y ajusta el texto de abajo si quieres.")
    personality = st.text_area(
        "Cómo habla", key=personality_key,
        help="Solo cambia el tono. El asistente sigue contestando únicamente con la información a la que tiene acceso.")
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

    st.subheader("Acceso a la información")
    st.caption("Lo que no esté aquí no llega al asistente: no puede citarlo ni usarlo para contestar. "
               "Sin nada elegido, consulta todo.")
    documents = api("GET", "/documents")
    faqs = api("GET", "/faqs")
    left, right = st.columns(2)
    selected = left.multiselect(
        "Categorías completas", sorted(set(categories) | set(p.get("categories", []))),
        default=p.get("categories", []), key=f"{key}_categories", placeholder="Elige categorías",
        help="Incluye todos los documentos y preguntas frecuentes de esas categorías, también los que se agreguen después.")
    sources = sorted({d["source"] for d in documents} | set(p.get("documents", [])))
    selected_documents = right.multiselect(
        "Documentos sueltos", sources, default=p.get("documents", []), key=f"{key}_documents",
        placeholder="Elige documentos",
        help="Documentos concretos, aunque su categoría no esté elegida.")
    if selected or selected_documents:
        allowed = [d["source"] for d in documents if d["category"] in selected or d["source"] in selected_documents]
        allowed_faqs = sum(1 for f in faqs.values() if f["category"] in selected)
        st.write(f"Puede consultar {len(allowed)} de {len(documents)} documentos y "
                 f"{allowed_faqs} de {len(faqs)} preguntas frecuentes.")
        if allowed:
            st.caption(", ".join(allowed))
    else:
        st.write(f"Puede consultar todo: {len(documents)} documentos y {len(faqs)} preguntas frecuentes.")

    wake_words = st.text_input(
        "Nombres a los que responde en una reunión (separados por comas)",
        ", ".join(p.get("wake_words", [])), key=f"{key}_wake_words", placeholder=name or "TecBot",
        help="En modo reunión solo contesta cuando alguien dice uno de estos nombres. Vacío = su nombre.")

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
            "role": role.strip(), "documents": selected_documents,
            "wake_words": [word.strip() for word in wake_words.split(",") if word.strip()],
        })
        notify(f"Asistente «{name.strip()}» guardado.")
    if not is_new:
        if delete.button("Eliminar", disabled=len(profiles) <= 1):
            api("DELETE", f"/profiles/{profile_id}")
            notify(f"Asistente «{p['name']}» eliminado.")
        link.link_button("Abrir en la página del avatar", f"{AVATAR_URL}?perfil={profile_id}")


# ---------- Personajes ----------

def page_avatars():
    st.title("Personajes")
    st.caption("Apariencia del avatar. Además de los cinco de ejemplo puedes subir uno propio en formato .glb.")
    avatars = api("GET", "/avatars")

    with st.expander("Subir un personaje", expanded=False):
        st.markdown(
            "El archivo debe ser un `.glb` con esqueleto tipo Mixamo, las 52 formas faciales de ARKit y los "
            "15 visemas de Oculus. Los que exportan Ready Player Me, Avaturn o Avatar SDK ya vienen así. "
            "Revisa la licencia antes de usarlo con estudiantes.")
        file = st.file_uploader("Archivo .glb", type=["glb"])
        left, middle = st.columns(2)
        name = left.text_input("Nombre del personaje")
        body = middle.selectbox("Cuerpo", ["F", "M"], format_func={"F": "Femenino", "M": "Masculino"}.get)
        license_text = st.text_input("Licencia o procedencia", placeholder="Por ejemplo: creado por el equipo, uso libre")
        if st.button("Subir personaje", type="primary", disabled=not (file and name.strip())):
            saved = api("POST", "/avatars", files={"file": (file.name, file.getvalue())},
                        data={"name": name.strip(), "body": body, "license": license_text}, timeout=300)
            notify(f"Personaje «{saved['name']}» agregado. Asígnalo a un asistente en **Asistentes**.")

    table = pd.DataFrame({
        "Nombre": [a["name"] for a in avatars],
        "Identificador": [a["id"] for a in avatars],
        "Licencia": [a.get("license", "") for a in avatars],
        "Origen": ["Propio" if a.get("custom") else "Ejemplo" for a in avatars],
    })
    st.dataframe(table, hide_index=True, width="stretch")
    custom = [a for a in avatars if a.get("custom")]
    if custom:
        target = st.selectbox("Eliminar un personaje propio", [a["id"] for a in custom],
                              format_func=lambda i: next(a["name"] for a in custom if a["id"] == i))
        if st.button("Eliminar personaje"):
            api("DELETE", f"/avatars/{target}")
            notify("Personaje eliminado.")


# ---------- Probar ----------

def page_test():
    st.title("Probar")
    st.caption("Haz una pregunta y revisa la respuesta y los fragmentos que usó. Incluye los borradores, así "
               "que puedes probar un cambio antes de publicarlo. Estas pruebas no se guardan en el historial.")
    profiles = api("GET", "/profiles")

    with st.form("test"):
        left, middle, right = st.columns([2, 2, 1])
        profile = left.selectbox("Asistente", list(profiles), format_func=lambda k: profiles[k]["name"])
        language = middle.selectbox("Idioma", list(LANGUAGES), format_func=LANGUAGES.get)
        include_drafts = right.toggle("Con borradores", value=True)
        message = st.text_input("Pregunta")
        submitted = st.form_submit_button("Preguntar", type="primary")
    if submitted and message.strip():
        with st.spinner("Pensando…"):
            st.session_state["test_result"] = api(
                "POST", "/test", json={"message": message.strip(), "language": language, "profile": profile,
                                       "include_drafts": include_drafts})

    result = st.session_state.get("test_result")
    if result:
        if result["answered"]:
            st.success(result["answer"])
        else:
            st.warning(f"Sin información en la base de conocimiento.\n\n{result['answer']}")
        st.caption(f"Intención: {INTENTS.get(result.get('intent'), result.get('intent'))} · "
                   f"consulta de búsqueda: {result['search_query']}")
        st.subheader(f"Fragmentos consultados ({len(result['chunks'])})")
        for chunk in result["chunks"]:
            similarity = max(0.0, 1 - chunk["distance"])
            state = "" if chunk.get("published", True) else "  ·  BORRADOR"
            with st.expander(f"{chunk['source']}  ·  {chunk['category']}  ·  parecido {similarity:.0%}{state}"):
                st.text(chunk["text"])

    st.divider()
    st.subheader("Evaluación")
    st.caption("Corre las preguntas de control de tests/preguntas.jsonl. Úsala después de cambiar documentos o asistentes.")
    eval_drafts = st.toggle("Evaluar también con los borradores", value=False, key="eval_drafts")
    if st.button("Correr evaluación"):
        with st.spinner("Evaluando; tarda alrededor de un minuto…"):
            st.session_state["eval_result"] = api("POST", "/eval", params={"include_drafts": eval_drafts},
                                                  timeout=1800)
    evaluation = st.session_state.get("eval_result")
    if evaluation:
        passed = sum(case["passed"] for case in evaluation)
        st.metric("Preguntas correctas", f"{passed} de {len(evaluation)}")
        table = pd.DataFrame({
            "Resultado": ["Pasa" if case["passed"] else "Falla" for case in evaluation],
            "Pregunta": [case["question"] for case in evaluation],
            "Debía contestar": ["Sí" if case["expected_answer"] else "No" for case in evaluation],
            "Respuesta": [case["answer"] for case in evaluation],
        })
        st.dataframe(table, hide_index=True, width="stretch")


# ---------- Reuniones ----------

MEETING_STATES = {
    "idle": "Sin reunión", "starting": "Preparando", "joining": "Entrando",
    "lobby": "En la sala de espera", "needs_user": "Necesita tu ayuda",
    "in_meeting": "En la reunión", "ended": "Terminada", "error": "Error",
}


def page_meetings():
    st.title("Reuniones")
    st.caption("Pega el enlace de una reunión de Teams y pulsa Unirse: el asistente entra solo, como invitado, "
               "con su avatar y su voz. En la reunión contesta cuando alguien dice su nombre.")
    profiles = api("GET", "/profiles")
    status = api("GET", "/meeting")
    active = status.get("active", False)

    # Es un formulario para que baste pegar el enlace y pulsar Intro.
    with st.form("unirse", border=False):
        url = st.text_input("Enlace de la reunión", placeholder="Pega aquí el enlace y pulsa Intro", disabled=active)
        left, right = st.columns(2)
        profile_id = left.selectbox("Asistente", list(profiles), format_func=lambda key: profiles[key]["name"],
                                    disabled=active)
        name = right.text_input("Nombre con el que aparece", placeholder="El nombre del asistente", disabled=active)
        if st.form_submit_button("Unirse", type="primary", disabled=active):
            if not url.strip():
                st.warning("Pega primero el enlace de la reunión.")
            else:
                api("POST", "/meeting/join", json={"url": url.strip(), "profile": profile_id,
                                                   "name": name.strip() or None})
                notify("El asistente está entrando a la reunión.")
    if st.button("Salir de la reunión", disabled=not active):
        api("POST", "/meeting/leave")
        notify("El asistente está saliendo de la reunión.")

    @st.fragment(run_every=2)
    def show_status():
        current = api("GET", "/meeting")
        st.subheader(MEETING_STATES.get(current["state"], current["state"]))
        if current["state"] != "idle":
            st.write(current["detail"])
        if current.get("active"):
            minutes, seconds = divmod(current["seconds"], 60)
            st.caption(f"{profiles.get(current['profile'], {}).get('name', current['profile'])} · "
                       f"aparece como «{current['name']}» · {minutes} min {seconds:02d} s")
        if current.get("active") != active:
            st.rerun()  # la reunión empezó o terminó: se actualizan los botones

    show_status()
    with st.expander("Cómo funciona y qué hacer si no entra"):
        st.markdown("""
- Se abren dos ventanas de navegador en esta computadora: una con el avatar y otra con Teams. No las cierres ni las minimices mientras dure la reunión.
- Entra tú primero a la reunión. Si nadie la ha empezado, el asistente se queda esperando.
- Cuando te salga el aviso de que quiere unirse, admítelo.
- El asistente solo entra como invitado. Nunca abre la aplicación de Teams de esta computadora ni usa tus cuentas: si la reunión exige iniciar sesión, cancela la entrada y lo dice aquí.
- Para preguntarle algo en la reunión, di primero su nombre.
""")


# ---------- Historial ----------

RATINGS = {None: "Sin valorar", "good": "Buena", "bad": "Mala"}


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
    cells[4].metric("Valoraciones", f"{stats['good']} buenas, {stats['bad']} malas")

    left, middle, right, last = st.columns([2, 1, 1, 1])
    left.caption("Preguntas por día")
    left.bar_chart(pd.Series(stats["by_day"], name="Preguntas"))
    middle.caption("Por idioma")
    middle.bar_chart(pd.Series({LANGUAGES.get(k, k): v for k, v in stats["by_language"].items()}, name="Preguntas"))
    right.caption("Por asistente")
    right.bar_chart(pd.Series(stats["by_profile"], name="Preguntas"))
    last.caption("Por intención")
    last.bar_chart(pd.Series({INTENTS.get(k, k): v for k, v in stats.get("by_intent", {}).items()}, name="Preguntas"))

    if stats["top_unanswered"]:
        st.subheader("Preguntas sin respuesta más repetidas")
        st.caption("Son la guía para saber qué documentos o preguntas frecuentes faltan.")
        st.dataframe(pd.DataFrame(stats["top_unanswered"], columns=["Pregunta", "Veces"]),
                     hide_index=True, width="stretch")

    head, download = st.columns([3, 1])
    head.subheader("Preguntas recientes")
    download.download_button("Descargar CSV", api("GET", "/history.csv", raw=True).content,
                             file_name="historial.csv", mime="text/csv")
    only_unanswered = st.toggle("Solo sin respuesta")
    entries = api("GET", "/history", params={"limit": 300, "unanswered": only_unanswered})
    if not entries:
        st.info("No hay preguntas con ese filtro.")
        return
    table = pd.DataFrame({
        "Fecha": [e["time"].replace("T", " ") for e in entries],
        "Asistente": [e["profile"] for e in entries],
        "Idioma": [e["language"] for e in entries],
        "Intención": [INTENTS.get(e.get("intent"), e.get("intent")) for e in entries],
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
    st.caption("Cambia la columna Valoración para marcar una respuesta como buena o mala. Los estudiantes "
               "también pueden valorar desde la página del avatar.")
    by_label = {label: rating for rating, label in RATINGS.items()}
    changed = [i for i in range(len(entries)) if edited["Valoración"][i] != table["Valoración"][i]]
    for i in changed:
        api("PUT", f"/history/{entries[i]['id']}/feedback", json={"rating": by_label[edited["Valoración"][i]]})
    if changed:
        notify("Valoración guardada.")


# ---------- Navegación ----------

st.set_page_config(page_title="Consola del Asistente Tec", layout="wide")

if require_login():
    pages = [
        st.Page(page_meetings, title="Reuniones", url_path="reuniones", default=True),
        st.Page(page_documents, title="Documentos", url_path="documentos"),
        st.Page(page_faqs, title="Preguntas frecuentes", url_path="preguntas"),
        st.Page(page_profiles, title="Asistentes", url_path="asistentes"),
        st.Page(page_avatars, title="Personajes", url_path="personajes"),
        st.Page(page_test, title="Probar", url_path="probar"),
        st.Page(page_history, title="Historial", url_path="historial"),
    ]
    page = st.navigation(pages)

    with st.sidebar:
        st.link_button("Abrir página del avatar", AVATAR_URL)
        try:
            health = api("GET", "/health", timeout=10)
            st.caption(f"API conectada · {health['chunks']} fragmentos · {health['llm']}")
            if not health.get("admin_token"):
                st.caption("Sin clave de administración (ADMIN_TOKEN). Úsala así solo en esta computadora.")
        except ApiError as error:
            st.error(str(error))

    if notice := st.session_state.pop("notice", None):
        st.toast(notice)
    try:
        page.run()
    except ApiError as error:
        st.error(str(error))
