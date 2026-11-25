// Página del avatar: personaje 3D (TalkingHead) + labios guiados por el audio (HeadAudio).
// Toda la inteligencia está en la API: /chat (RAG), /stt (voz a texto) y /tts (texto a voz).
import { TalkingHead } from "talkinghead";
import { HeadAudio } from "headaudio";
import { LANGUAGES, TEXTS } from "./i18n.js";
import { startMeetingListener } from "./reunion.js";
import { createBridge } from "./puente.js";

const $ = (id) => document.getElementById(id);

// Preferencias de este navegador (los dispositivos de audio cambian de una máquina a otra).
function recall(key) {
  try { return localStorage.getItem(key) || ""; } catch { return ""; }
}
function remember(key, value) {
  try { localStorage.setItem(key, value); } catch { /* sin almacenamiento: vale solo esta vez */ }
}

// Encuadre: normalmente el personaje va arriba para dejar libre la zona del diálogo; en
// reunión va más cerca y centrado, porque la imagen se ve pequeña en el mosaico de Teams.
const CAMERA = { cameraY: 0.28, cameraDistance: -0.1 };
const MEETING_CAMERA = { cameraY: -0.2, cameraDistance: -1.4 };
const MEETING_TITLE = "Asistente Tec - Reunion";
const ATTENTIVE_MS = 10000;    // tras oír solo su nombre, espera la pregunta este tiempo

const PARAMS = new URLSearchParams(location.search);
// Conexión directa: la imagen y la voz van a la pestaña de Teams por un puente (puente.js).
const BRIDGED = PARAMS.has("puente");

const state = {
  meeting: PARAMS.has("reunion") || BRIDGED,
  bargeIn: recall("bargeIn") === "voice" ? "voice" : "name",  // qué interrumpe al asistente en reunión
  autoLanguage: recall("autoLanguage") !== "off",  // al hablar, contesta en el idioma que oye
  micId: recall("micId"),
  outputId: recall("outputId"),
  profiles: {},
  avatars: [],
  profileId: null,
  language: "es",
  engine: "piper",
  voice: null,
  avatarId: null,
  sessionId: crypto.randomUUID(),
  status: "loading",
  turn: 0,          // sube con cada pregunta o interrupción; descarta respuestas viejas
  handsFree: false,
};

let head = null;      // TalkingHead
let listening = null; // grabación en curso: { stream, recorder, chunks, spoke, send }
let audioLipsync = false;  // true solo cuando una frase llega sin visemas (respaldo por audio)
let stopMeeting = null;    // cierra la escucha continua del modo reunión
let bridge = null;         // puente con la pestaña de Teams (solo en conexión directa)
let meetingChange = 0;     // sube con cada cambio del modo reunión; descarta aperturas viejas
let attentiveUntil = 0;    // hasta cuándo la siguiente frase cuenta como pregunta sin decir el nombre
let heard = Promise.resolve();  // las frases oídas se transcriben de una en una

const profile = () => state.profiles[state.profileId];
const avatar = () => state.avatars.find((a) => a.id === state.avatarId) || state.avatars[0];
const t = (key) => TEXTS[state.language]?.[key] ?? TEXTS.es[key] ?? key;
// En reunión, "listo" significa que está oyendo la reunión a la espera de su nombre.
const statusText = (status) => t(state.meeting && status === "idle" ? "meetingIdle" : status);

// ---------- Utilidades ----------

async function api(path, options) {
  const resp = await fetch(path, options);
  if (!resp.ok) throw new Error(`${path}: ${resp.status}`);
  return resp;
}

const postJSON = (path, body) =>
  api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

function setStatus(status, label) {
  state.status = status;
  document.body.dataset.status = status;
  $("status-label").textContent = label ?? statusText(status);
  const ready = head !== null && status !== "loading";
  for (const id of ["mic", "question", "send"]) $(id).disabled = !ready;
}

let toastTimer = null;
function toast(message) {
  $("toast").textContent = message;
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("toast").hidden = true), 4500);
}

function show(id, text, className) {
  const el = $(id);
  el.hidden = !text;
  el.textContent = text || "";
  if (className !== undefined) el.className = className;
  if (id === "subtitle" && text) {  // reinicia la animación de entrada
    el.style.animation = "none";
    void el.offsetWidth;
    el.style.animation = "";
  }
}

function clearDialog() {
  show("user-line", "");
  show("subtitle", "");
  show("meta", "");
  hideFeedback();
}

// ---------- Valoración (👍 / 👎) ----------

let feedbackId = null;  // respuesta que se está valorando (id del historial)

function hideFeedback() {
  feedbackId = null;
  $("feedback").hidden = true;
}

function offerFeedback(id) {
  if (!id || state.meeting) return;
  feedbackId = id;
  $("feedback-label").textContent = t("useful");
  for (const button of $("feedback").querySelectorAll("button")) {
    button.disabled = false;
    button.setAttribute("aria-pressed", "false");
  }
  $("feedback").hidden = false;
}

async function sendFeedback(button) {
  const id = feedbackId;
  if (!id) return;
  for (const b of $("feedback").querySelectorAll("button")) b.disabled = true;
  button.setAttribute("aria-pressed", "true");
  try {
    await api(`/feedback/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rating: button.dataset.rating }),
    });
    if (id === feedbackId) $("feedback-label").textContent = t("thanks");
  } catch (error) {
    console.error(error);
    for (const b of $("feedback").querySelectorAll("button")) b.disabled = false;
    button.setAttribute("aria-pressed", "false");
  }
}

function fillSelect(el, entries, selected) {
  el.replaceChildren(...entries.map(([value, label]) => new Option(label, value, false, value === selected)));
}

function applyTexts() {
  document.documentElement.lang = state.language;
  for (const el of document.querySelectorAll("[data-i18n]")) el.textContent = t(el.dataset.i18n);
  for (const el of document.querySelectorAll("[data-i18n-placeholder]")) el.placeholder = t(el.dataset.i18nPlaceholder);
  for (const el of document.querySelectorAll("[data-i18n-label]")) el.setAttribute("aria-label", t(el.dataset.i18nLabel));
  $("status-label").textContent = statusText(state.status);
}

// El texto se va cortando en trozos para empezar a hablar con el primero mientras llega el
// resto. Se corta al final de una frase; si la frase es larga, también en una coma o dos puntos
// (antes en el primer trozo, para que la voz arranque pronto).
const SENTENCE_END = /[.!?…]["”»)]?\s+(?=[\p{Lu}¿¡"“«(\d])/gu;
const CLAUSE_END = /[,;:]\s+/g;

function cutPoint(buffer, isFirst) {
  for (const match of buffer.matchAll(SENTENCE_END)) {
    const end = match.index + match[0].length;
    if (end >= 20) return end;
  }
  if (buffer.length > (isFirst ? 70 : 180)) {
    for (const match of buffer.matchAll(CLAUSE_END)) {
      const end = match.index + match[0].length;
      if (end >= 45) return end;
    }
  }
  return -1;
}

// Lee una respuesta con una línea JSON por evento (/chat/stream).
async function* readEvents(resp) {
  const reader = resp.body.pipeThrough(new TextDecoderStream()).getReader();
  let pending = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      pending += value;
      const lines = pending.split("\n");
      pending = lines.pop();
      for (const line of lines) if (line.trim()) yield JSON.parse(line);
    }
    if (pending.trim()) yield JSON.parse(pending);
  } finally {
    reader.cancel().catch(() => {});
  }
}

// ---------- Avatar ----------

// Los labios se animan con los visemas que calcula el servidor (/speak). HeadAudio, que
// deduce la boca directamente del sonido, queda de respaldo para frases sin visemas.
async function initLipsync() {
  await head.audioCtx.audioWorklet.addModule("vendor/headaudio/headworklet.min.mjs");
  const headaudio = new HeadAudio(head.audioCtx, {
    parameterData: { vadGateActiveDb: -40, vadGateInactiveDb: -60 },
  });
  await headaudio.loadModel("vendor/headaudio/model-en-mixed.bin");
  head.audioSpeechGainNode.connect(headaudio);
  headaudio.onvalue = (key, value) => {
    const morph = audioLipsync && head.mtAvatar?.[key];
    if (morph) Object.assign(morph, { newvalue: value, needsUpdate: true });
  };
  head.opt.update = headaudio.update.bind(headaudio);
}

function decodeBase64(text) {
  return Uint8Array.from(atob(text), (c) => c.charCodeAt(0)).buffer;
}

async function loadAvatar() {
  const a = avatar();
  interrupt();
  setStatus("loading", t("loadingAvatar"));
  await head.showAvatar(
    { url: `avatars/${a.file}`, avatarMood: profile().mood || "neutral", lipsyncLang: "en", ...a.options },
    (ev) => {
      if (!ev.lengthComputable) return;
      const percent = Math.min(100, Math.round((ev.loaded / ev.total) * 100));
      const label = `${t("loadingAvatar")} ${percent}%`;
      $("status-label").textContent = label;
      $("start-progress").textContent = label;
    },
  );
  $("license").textContent = `${a.name}: ${a.license}`;
  setStatus("idle");
}

// ---------- Hablar ----------

function interrupt() {
  state.turn++;
  head?.stopSpeaking();
}

// Sintetiza un trozo de texto y lo pone en la cola de habla del avatar.
async function speakChunk(text, turn) {
  if (turn !== state.turn) return;
  try {
    const resp = await postJSON("/speak", {
      text, language: state.language, voice: state.voice, engine: state.engine,
    });
    const { audio: encoded, visemes, vtimes, vdurations } = await resp.json();
    const audio = await head.audioCtx.decodeAudioData(decodeBase64(encoded));
    if (turn !== state.turn) return;
    const hasVisemes = visemes.length > 0;
    head.speakMarker(() => {
      if (turn !== state.turn) return;
      audioLipsync = !hasVisemes;
      setStatus("speaking");
      show("subtitle", text);
    });
    // TalkingHead solo usa los visemas si también recibe la lista de palabras (aquí vacía).
    head.speakAudio(hasVisemes
      ? { audio, words: [], wtimes: [], wdurations: [], visemes, vtimes, vdurations }
      : { audio });
  } catch (error) {
    console.error(error);
    if (turn !== state.turn) return;
    show("subtitle", text);  // sin voz, al menos se lee la respuesta
    toast(t("error"));
  }
}

// Cola de habla de un turno: recibe texto a medida que llega y lo dice en orden.
function createSpeaker(turn) {
  let buffer = "";
  let isFirst = true;
  let chain = Promise.resolve();
  const say = (text) => {
    if (text.trim()) chain = chain.then(() => speakChunk(text.trim(), turn));
    isFirst = false;
  };
  return {
    add(text) {
      buffer += text;
      for (let cut; (cut = cutPoint(buffer, isFirst)) > 0; buffer = buffer.slice(cut)) say(buffer.slice(0, cut));
    },
    async finish() {
      say(buffer);
      buffer = "";
      await chain;
      if (turn !== state.turn) return;
      if (head.isSpeaking) head.speakMarker(() => turn === state.turn && finishTurn());
      else finishTurn();
    },
  };
}

function finishTurn() {
  // Si acaba de contestar "¿Sí? Adelante.", sigue atento a la pregunta que viene.
  if (state.meeting && performance.now() < attentiveUntil) setStatus("listening", t("attentive"));
  else setStatus("idle");
  if (state.handsFree) listen();
  if (state.meeting) {
    // En la reunión el subtítulo se ve en la cámara: se quita poco después de terminar.
    const turn = state.turn;
    setTimeout(() => turn === state.turn && state.status === "idle" && show("subtitle", ""), 2500);
  }
}

function greet() {
  const p = profile();
  clearDialog();
  if (!p.greeting || state.language !== p.language) return;
  const turn = ++state.turn;
  setStatus("thinking", t("preparing"));
  const speaker = createSpeaker(turn);
  speaker.add(state.meeting ? `${p.greeting} ${t("meetingHint")}` : p.greeting);
  speaker.finish();
}

async function ask(text) {
  text = text.trim();
  if (!text || !head) return;
  interrupt();
  const turn = state.turn;
  show("user-line", text);
  show("subtitle", "");
  show("meta", "");
  hideFeedback();
  setStatus("thinking");
  head.lookAtCamera(600);
  try {
    const resp = await postJSON("/chat/stream", {
      session_id: state.sessionId, message: text, language: state.language, profile: state.profileId,
    });
    const speaker = createSpeaker(turn);
    for await (const event of readEvents(resp)) {
      if (turn !== state.turn) return;
      if (event.type === "delta") {
        speaker.add(event.text);
        continue;
      }
      if (!event.answered) show("meta", t("noInfo"), "meta warning");
      else if (event.sources.length) show("meta", `${t("sources")}: ${event.sources.join(", ")}`, "meta");
      if (event.intent === "consulta") offerFeedback(event.id);
    }
    await speaker.finish();
  } catch (error) {
    console.error(error);
    if (turn !== state.turn) return;
    toast(t("error"));
    setStatus("idle");
  }
}

// ---------- Escuchar ----------

// Abre el micrófono elegido; si ya no existe (se desconectó), vuelve al predeterminado.
async function withMic(open) {
  try {
    return await open(state.micId);
  } catch (error) {
    if (!state.micId || !["OverconstrainedError", "NotFoundError"].includes(error.name)) throw error;
    remember("micId", (state.micId = ""));
    return open("");
  }
}

async function listen() {
  if (listening || !head || state.meeting) return;
  interrupt();
  let stream;
  try {
    stream = await withMic((deviceId) => navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true, noiseSuppression: true, autoGainControl: true,
        ...(deviceId && { deviceId: { exact: deviceId } }),
      },
    }));
  } catch (error) {
    console.error(error);
    toast(t("micDenied"));
    return;
  }
  const recorder = new MediaRecorder(stream);
  listening = { stream, recorder, chunks: [], spoke: false, send: false };
  recorder.ondataavailable = (ev) => listening?.chunks.push(ev.data);
  recorder.onstop = onRecorded;
  recorder.start();

  // El detector de silencio de TalkingHead avisa cuando la persona empieza y termina de hablar.
  const analyser = head.audioCtx.createAnalyser();
  head.audioCtx.createMediaStreamSource(stream).connect(analyser);
  head.startListening(analyser, { listeningSilenceThresholdMs: 1100, listeningSilenceDurationMax: 8000 }, (event) => {
    if (!listening) return;
    if (event === "start") listening.spoke = true;
    else if (event === "stop" && listening.spoke) stopListening(true);
    else if (event === "maxsilence" && !listening.spoke) stopListening(false);
    else if (event === "maxactive") stopListening(true);
  });
  setStatus("listening");
}

function stopListening(send) {
  if (!listening || listening.recorder.state === "inactive") return;
  listening.send = send;
  head.stopListening();
  listening.recorder.stop();
}

async function onRecorded() {
  const { stream, recorder, chunks, send } = listening;
  listening = null;
  stream.getTracks().forEach((track) => track.stop());
  if (!send) {
    setStatus("idle");
    return;
  }
  const turn = ++state.turn;
  setStatus("thinking", t("transcribing"));
  try {
    const form = new FormData();
    form.append("audio", new Blob(chunks, { type: recorder.mimeType }), "pregunta.webm");
    // Con detección automática Whisper reconoce el idioma y la API dice si conviene cambiarlo
    // (solo a uno de los cinco del asistente y si está seguro).
    const query = state.autoLanguage ? `current=${state.language}` : `language=${state.language}`;
    const resp = await api(`/stt?${query}`, { method: "POST", body: form });
    const { text, reply_language: replyLanguage } = await resp.json();
    if (turn !== state.turn) return;
    if (text && replyLanguage && replyLanguage !== state.language && LANGUAGES[replyLanguage]) {
      await setLanguage(replyLanguage, { clear: false });
      if (turn !== state.turn) return;
    }
    if (text) return ask(text);
    toast(t("notHeard"));
    finishTurn();
  } catch (error) {
    console.error(error);
    toast(t("error"));
    setStatus("idle");
  }
}

// ---------- Modo reunión ----------
// El micrófono queda abierto oyendo la reunión. El asistente solo contesta las frases que lo
// nombran. Mientras habla se calla si lo nombran (o, según la configuración, con cualquier voz).

// En reunión el título de la ventana es fijo, para reconocerla entre las del navegador.
function setTitle() {
  document.title = state.meeting ? MEETING_TITLE : profile()?.name ?? "Asistente Tec";
}

async function setMeeting(on) {
  const change = ++meetingChange;
  state.meeting = on;
  setTitle();
  document.body.classList.toggle("meeting", on);
  $("meeting").checked = on;
  $("hands-free").disabled = on;
  attentiveUntil = 0;
  if (on) {
    state.handsFree = false;
    $("hands-free").checked = false;
    if (listening) stopListening(false);
  }
  stopMeeting?.();
  stopMeeting = null;
  if (!head) return;
  Object.assign(head.opt, on ? MEETING_CAMERA : CAMERA);  // también vale para el próximo personaje
  head.setView("upper");
  if (state.status === "idle") setStatus("idle");  // la etiqueta de "listo" cambia con el modo
  if (!on) return;
  try {
    const callbacks = {
      onSustained: onInterrupted,
      onPartial: onOverheard,
      onSegment: (wav) => (heard = heard.then(() => onHeard(wav))),
    };
    const stop = bridge
      ? await startMeetingListener(head.audioCtx, bridge.inbound, callbacks)
      : await withMic((deviceId) => startMeetingListener(head.audioCtx, deviceId, callbacks));
    if (change === meetingChange) stopMeeting = stop;
    else stop();  // mientras se abría el micrófono cambiaron el modo otra vez
  } catch (error) {
    console.error(error);
    toast(t("micDenied"));
  }
}

// Transcribe audio de la reunión y dice si nombra al asistente.
async function transcribeMeeting(wav) {
  const form = new FormData();
  form.append("audio", wav, "reunion.wav");
  const query = new URLSearchParams({ language: state.language, wake_profile: state.profileId });
  return (await api(`/stt?${query}`, { method: "POST", body: form })).json();
}

// Deja de hablar y espera la pregunta: la siguiente frase cuenta aunque no repita el nombre.
// Con `reply` contesta antes algo corto en voz alta ("¿Sí? Adelante."), para que quien lo
// llamó sepa que lo oyó aunque no esté mirando la pantalla.
function attend(reply) {
  interrupt();
  show("subtitle", "");
  const wait = ATTENTIVE_MS + (reply ? 3500 : 0);  // lo que tarda en decir la respuesta no cuenta
  attentiveUntil = performance.now() + wait;
  if (reply) {
    setStatus("thinking", t("preparing"));
    const speaker = createSpeaker(state.turn);
    speaker.add(reply);
    speaker.finish();
  } else {
    setStatus("listening", t("attentive"));
  }
  setTimeout(() => {
    if (state.status === "listening" && performance.now() >= attentiveUntil) setStatus("idle");
  }, wait + 100);
}

function silence() {
  interrupt();
  show("subtitle", "");
  attentiveUntil = 0;
  setStatus("idle");
}

// Alguien lleva un rato hablando. Solo interrumpe si así está configurado.
function onInterrupted() {
  if (state.bargeIn === "voice" && state.status === "speaking") silence();
}

// Lo dicho hasta ahora por alguien que habla mientras el asistente también habla: si ya lo
// nombró, se calla sin esperar a que termine la frase.
async function onOverheard(wav) {
  if (!state.meeting || state.bargeIn !== "name" || state.status !== "speaking") return;
  const turn = state.turn;
  try {
    const { addressed } = await transcribeMeeting(wav);
    if (addressed && state.meeting && turn === state.turn) attend();
  } catch (error) {
    console.error(error);
  }
}

async function onHeard(wav) {
  if (!state.meeting) return;
  try {
    const { text, addressed, question, stop, ping } = await transcribeMeeting(wav);
    if (!state.meeting || !text) return;
    // En la configuración se ve lo último que oyó: sirve para saber cómo escribe su nombre.
    show("heard", `${t("lastHeard")}: «${text}» (${t(addressed ? "heardName" : "heardNoName")})`);
    const attentive = performance.now() < attentiveUntil;
    if (addressed && stop) silence();                            // "TecBot, espera", "gracias, TecBot"
    else if (addressed && ping) attend(t("hereIAm"));            // "TecBot, ¿me escuchas?"
    else if (addressed && !question) attend(t("yesTellMe"));     // solo su nombre: viene la pregunta
    else if (addressed || attentive) {
      attentiveUntil = 0;
      ask(addressed ? question : text);
    }
  } catch (error) {
    console.error(error);
  }
}

// ---------- Dispositivos de audio ----------

async function refreshDevices(askPermission = false) {
  let devices = await navigator.mediaDevices.enumerateDevices();
  if (askPermission && devices.some((d) => d.kind === "audioinput" && !d.label)) {
    // El navegador solo da los nombres de los dispositivos después de permitir el micrófono.
    try {
      (await navigator.mediaDevices.getUserMedia({ audio: true })).getTracks().forEach((track) => track.stop());
      devices = await navigator.mediaDevices.enumerateDevices();
    } catch (error) {
      console.warn(error);
    }
  }
  const options = (kind) => [
    ["", t("systemDefault")],
    ...devices
      .filter((d) => d.kind === kind && d.label && !["default", "communications"].includes(d.deviceId))
      .map((d) => [d.deviceId, d.label]),
  ];
  fillSelect($("mic-device"), options("audioinput"), state.micId);
  fillSelect($("output-device"), options("audiooutput"), state.outputId);
}

// Manda la voz del asistente al dispositivo elegido (p. ej. el cable de audio hacia Teams).
async function applyOutput() {
  if (!head?.audioCtx.setSinkId) return;
  try {
    await head.audioCtx.setSinkId(state.outputId || "");
  } catch (error) {
    console.warn(error);
    if (state.outputId) {  // el dispositivo guardado ya no existe: vuelve al predeterminado
      remember("outputId", (state.outputId = ""));
      await head.audioCtx.setSinkId("").catch(() => {});
    }
  }
}

// ---------- Configuración ----------

function warmup() {
  postJSON("/warmup", { language: state.language, voice: state.voice, engine: state.engine })
    .catch((error) => console.warn("warmup", error));
}

async function refreshVoices() {
  const query = new URLSearchParams({ language: state.language, engine: state.engine });
  const voices = await (await api(`/voices?${query}`)).json();
  const preferred = state.engine === profile().engine ? profile().voices?.[state.language] : null;
  state.voice = voices.includes(preferred) ? preferred : voices[0] ?? null;
  fillSelect($("voice"), voices.map((v) => [v, v]), state.voice);
}

// Cambia el idioma de la interfaz, de la voz y de las respuestas.
async function setLanguage(code, { clear = true } = {}) {
  state.language = code;
  $("language").value = code;
  applyTexts();
  if (clear) clearDialog();
  refreshDevices().catch(console.warn);  // traduce la opción "predeterminado"
  await refreshVoices().catch(reportError);
}

async function applyProfile(id) {
  state.profileId = id;
  const p = profile();
  state.language = p.language;
  state.engine = p.engine;
  state.avatarId = state.avatars.some((a) => a.id === p.avatar) ? p.avatar : state.avatars[0].id;
  state.sessionId = crypto.randomUUID();

  $("assistant-name").textContent = p.name;
  $("assistant-description").textContent = p.description;
  setTitle();
  $("profile").value = id;
  $("language").value = state.language;
  $("engine").value = state.engine;
  $("character").value = state.avatarId;
  applyTexts();
  await refreshVoices();
  if (head) {
    await loadAvatar();
    greet();
  }
}

function bindSettings() {
  $("settings-open").onclick = () => {
    $("settings").hidden = false;
    refreshDevices(true).catch(console.warn);
  };
  $("settings-close").onclick = () => ($("settings").hidden = true);
  navigator.mediaDevices.addEventListener("devicechange", () => refreshDevices().catch(console.warn));
  $("output-device").disabled = !("setSinkId" in AudioContext.prototype);

  $("mic-device").onchange = (ev) => {
    remember("micId", (state.micId = ev.target.value));
    if (state.meeting) setMeeting(true);  // reabre la escucha con el micrófono nuevo
  };
  $("output-device").onchange = (ev) => {
    remember("outputId", (state.outputId = ev.target.value));
    applyOutput();
  };
  $("meeting").onchange = (ev) => setMeeting(ev.target.checked);
  $("barge-in").value = state.bargeIn;
  $("barge-in").onchange = (ev) => remember("bargeIn", (state.bargeIn = ev.target.value));

  $("profile").onchange = (ev) => applyProfile(ev.target.value).catch(reportError);
  $("language").onchange = async (ev) => {
    interrupt();
    await setLanguage(ev.target.value);
    setStatus("idle");
  };
  $("auto-language").checked = state.autoLanguage;
  $("auto-language").onchange = (ev) => {
    state.autoLanguage = ev.target.checked;
    remember("autoLanguage", state.autoLanguage ? "on" : "off");
  };
  $("character").onchange = (ev) => {
    state.avatarId = ev.target.value;
    loadAvatar().catch(reportError);
  };
  $("engine").onchange = async (ev) => {
    state.engine = ev.target.value;
    await refreshVoices().catch(reportError);
    warmup();
  };
  $("voice").onchange = (ev) => (state.voice = ev.target.value);
  $("hands-free").onchange = (ev) => {
    state.handsFree = ev.target.checked;
    if (state.handsFree && state.status === "idle") listen();
  };
  $("new-chat").onclick = () => {
    fetch(`/sessions/${state.sessionId}`, { method: "DELETE" }).catch(() => {});
    state.sessionId = crypto.randomUUID();
    interrupt();
    greet();
    if (state.status !== "thinking") setStatus("idle");
  };
}

function reportError(error) {
  console.error(error);
  toast(t("error"));
  if (head) setStatus("idle");
}

// ---------- Controles ----------

function bindControls() {
  $("mic").onclick = () => (listening ? stopListening(true) : listen());
  for (const button of $("feedback").querySelectorAll("button")) button.onclick = () => sendFeedback(button);
  $("ask-form").onsubmit = (ev) => {
    ev.preventDefault();
    const text = $("question").value;
    $("question").value = "";
    if (listening) stopListening(false);
    ask(text);
  };
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") {
      $("settings").hidden = true;
      if (listening) stopListening(false);
      interrupt();
      if (head && state.status !== "loading") setStatus("idle");
    }
  });
}

// ---------- Arranque ----------

async function start() {
  $("start-button").disabled = true;
  try {
    head = new TalkingHead($("avatar"), {
      ttsEndpoint: "",
      lipsyncModules: [],
      cameraView: "upper",
      ...(state.meeting ? MEETING_CAMERA : CAMERA),
      cameraRotateEnable: false,
      modelFPS: 60,
      modelPixelRatio: Math.min(window.devicePixelRatio || 1, 2),
      avatarIdleEyeContact: 0.6,
      avatarSpeakingEyeContact: 0.85,
      lightAmbientIntensity: 2.4,
      lightDirectIntensity: 26,
    });
    window.assistant = { state, head, ask, listen, interrupt, setMeeting };  // para depurar desde la consola
    await initLipsync();
    warmup();
    if (BRIDGED) {
      bridge = createBridge(head, () => ({
        status: state.status,
        label: $("status-label").textContent,
        subtitle: $("subtitle").hidden ? "" : $("subtitle").textContent,
      }));
    } else {
      await applyOutput();
    }
    await loadAvatar();
    $("start").classList.add("hidden");
    if (state.meeting) await setMeeting(true);
    // En conexión directa el saludo espera a que el asistente ya esté dentro de la reunión.
    if (BRIDGED) window.puente = { offer: bridge.offer, finish: bridge.finish, info: bridge.info, greet, state };
    else greet();
  } catch (error) {
    console.error(error);
    head = null;
    $("start-progress").textContent = `${t("error")} (${error.message})`;
    $("start-button").disabled = false;
  }
}

async function init() {
  // En la ventana propia del modo reunión, ajusta el tamaño para que la página mida justo
  // 1280x720 (la imagen de la cámara); en una pestaña normal el navegador lo ignora.
  if (state.meeting) window.resizeTo(1280 + outerWidth - innerWidth, 720 + outerHeight - innerHeight);
  document.body.classList.toggle("meeting", state.meeting);
  $("meeting").checked = state.meeting;
  $("hands-free").disabled = state.meeting;
  bindSettings();
  bindControls();
  try {
    [state.profiles, state.avatars] = await Promise.all([
      api("/profiles").then((r) => r.json()),
      api("avatars.json").then((r) => r.json()),
    ]);
    fillSelect($("profile"), Object.entries(state.profiles).map(([id, p]) => [id, p.name]));
    fillSelect($("language"), Object.entries(LANGUAGES));
    fillSelect($("character"), state.avatars.map((a) => [a.id, a.name]));
    const requested = PARAMS.get("perfil");
    await applyProfile(state.profiles[requested] ? requested : Object.keys(state.profiles)[0]);
    $("start-progress").textContent = "";
    $("start-button").disabled = false;
    $("start-button").onclick = start;
    // Con ?auto arranca sin pulsar Comenzar. Solo sirve si el navegador se abrió permitiendo
    // audio sin interacción, como hace app/teams.py.
    if (PARAMS.has("auto") || BRIDGED) start();
  } catch (error) {
    console.error(error);
    $("start-progress").textContent = `${t("error")} (${error.message})`;
  }
}

init();
