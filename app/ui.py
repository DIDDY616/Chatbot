"""Chat de texto y voz.  Uso:  streamlit run app/ui.py   (requiere la API corriendo)"""
import os
import uuid

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")  # no "localhost": en Windows agrega ~2 s por llamada
LANGUAGES = {"Español": "es", "English": "en", "Français": "fr", "Svenska": "sv", "Deutsch": "de"}

st.set_page_config(page_title="Asistente Tec", page_icon="🎓")
st.title("Asistente Tec")

state = st.session_state
if "session_id" not in state:
    state.session_id = uuid.uuid4().hex
    state.messages = []
    state.audio_key = 0      # cambia para vaciar la grabadora tras cada pregunta
    state.autoplay = False   # reproducir el audio de la última respuesta


ENGINES = {"Piper (rápida)": "piper", "Chatterbox (natural, más lenta)": "chatterbox"}


@st.cache_data(ttl=60)
def get_voices(language: str, engine: str) -> list[str]:
    try:
        resp = requests.get(f"{API_URL}/voices", params={"language": language, "engine": engine}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return []


with st.sidebar:
    language = LANGUAGES[st.selectbox("Idioma", list(LANGUAGES))]
    speak = st.toggle("Responder con voz", value=True)
    engine = ENGINES[st.selectbox("Motor de voz", list(ENGINES))] if speak else None
    voice = st.selectbox("Voz", get_voices(language, engine)) if speak else None
    if st.button("Nueva conversación"):
        requests.delete(f"{API_URL}/sessions/{state.session_id}", timeout=10)
        state.session_id = uuid.uuid4().hex
        state.messages = []
        st.rerun()

history = st.container()
recording = st.audio_input("Pregunta por voz", key=f"audio_{state.audio_key}")
typed = st.chat_input("Escribe tu pregunta")


def ask(prompt: str) -> None:
    """Envía la pregunta, guarda la respuesta (con audio si aplica) y redibuja."""
    resp = requests.post(
        f"{API_URL}/chat",
        json={"session_id": state.session_id, "message": prompt, "language": language},
        timeout=120,
    )
    resp.raise_for_status()
    bot = {"role": "assistant", **resp.json()}
    if speak and voice:
        tts = requests.post(
            f"{API_URL}/tts",
            json={"text": bot["answer"], "language": language, "voice": voice, "engine": engine},
            timeout=300,
        )
        tts.raise_for_status()
        bot["audio"] = tts.content
    state.messages += [{"role": "user", "answer": prompt}, bot]
    state.autoplay = "audio" in bot


try:
    if recording:
        with st.spinner("Escuchando..."):
            stt = requests.post(
                f"{API_URL}/stt",
                files={"audio": ("pregunta.wav", recording.getvalue(), "audio/wav")},
                params={"language": language},
                timeout=120,
            )
            stt.raise_for_status()
            heard = stt.json()["text"]
        state.audio_key += 1
        if heard:
            with st.spinner("Pensando..."):
                ask(heard)
        else:
            st.toast("No se entendió el audio, intenta de nuevo")
        st.rerun()
    elif typed:
        with st.spinner("Pensando..."):
            ask(typed)
        st.rerun()
except requests.RequestException as e:
    st.error(f"No se pudo contactar la API en {API_URL}: {e}")

with history:
    for i, msg in enumerate(state.messages):
        with st.chat_message(msg["role"]):
            st.write(msg["answer"])
            if msg.get("answered") is False:
                st.caption("⚠️ Sin información en la base de conocimiento")
            if msg.get("sources"):
                st.caption("Fuentes: " + ", ".join(msg["sources"]))
            if msg.get("audio"):
                last = i == len(state.messages) - 1
                st.audio(msg["audio"], format="audio/wav", autoplay=last and state.autoplay)
    state.autoplay = False
