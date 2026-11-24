// Se inyecta en la pestaña de Teams antes de que cargue (app/teams.py): entrega a Teams la
// imagen y la voz del asistente como cámara y micrófono, y devuelve el audio de la reunión.
(() => {
  if (window.__tecPuente) return;

  // Nunca se abre la aplicación de Teams instalada en la computadora: el asistente vive solo
  // en esta pestaña. Se cancela cualquier intento de la página de ir a un enlace msteams:.
  const APP_LINK = /^(msteams|ms-teams|msteams-l|ms-teams-l):/i;
  let appBlocked = 0;
  const isAppLink = (url) => {
    const found = APP_LINK.test(String(url ?? ""));
    if (found) appBlocked++;
    return found;
  };
  window.navigation?.addEventListener("navigate", (event) => {
    if (event.cancelable && isAppLink(event.destination.url)) event.preventDefault();
  });
  const nativeOpen = window.open;
  window.open = function (url, ...rest) {
    return isAppLink(url) ? null : nativeOpen.call(this, url, ...rest);
  };
  const frameSrc = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, "src");
  Object.defineProperty(HTMLIFrameElement.prototype, "src", {
    ...frameSrc,
    set(value) {
      if (!isAppLink(value)) frameSrc.set.call(this, value);
    },
  });
  document.addEventListener("click", (event) => {
    const link = event.target.closest?.("a[href]");
    if (link && isAppLink(link.getAttribute("href"))) {
      event.preventDefault();
      event.stopPropagation();
    }
  }, true);

  // Si Teams corre dentro de un marco del mismo sitio, se usa el puente de la página principal.
  const top = (() => {
    try {
      return window.top !== window && window.top.__tecPuente ? window.top.__tecPuente : null;
    } catch {
      return null;
    }
  })();

  const NativePC = window.RTCPeerConnection;
  const devices = navigator.mediaDevices;
  const nativeGetUserMedia = devices.getUserMedia.bind(devices);

  const own = {
    pc: null,
    video: null,      // pista de video del asistente
    audio: null,      // pista de voz del asistente
    waiting: [],      // peticiones de cámara/micrófono que esperan a que llegue el puente
    ctx: null,
    mix: null,        // mezcla del audio de la reunión
    heard: new Set(),
    spare: [],        // fuentes de audio conectadas que no son la mezcla principal
    hasMain: false,
    stats: { requests: 0, served: 0, inbound: 0 },
    log: [],          // qué pidió Teams y qué se le entregó (para diagnosticar)
  };
  const bridge = top ?? own;

  function mixer() {
    if (!bridge.ctx) {
      bridge.ctx = new AudioContext();
      bridge.mix = bridge.ctx.createMediaStreamDestination();
    }
    bridge.ctx.resume().catch(() => {});
    return bridge.mix;
  }

  // Audio que llega de los demás participantes. Teams manda una mezcla de todos ("mainAudio")
  // y además pistas que ya van dentro de esa mezcla: cuando aparece la mezcla se usa solo ella,
  // para no oír doble.
  function addInbound(event) {
    const track = event.track;
    if (track.kind !== "audio" || bridge.heard.has(track.id)) return;
    bridge.heard.add(track.id);
    const main = [track.id, ...event.streams.map((stream) => stream.id)].some((id) => id.includes("mainAudio"));
    if (!main && bridge.hasMain) return;
    bridge.stats.inbound++;
    const stream = new MediaStream([track]);
    const player = new Audio();  // Chrome solo pasa a Web Audio lo que además suena en un elemento
    player.muted = true;
    player.srcObject = stream;
    player.play().catch(() => {});
    mixer();
    const source = bridge.ctx.createMediaStreamSource(stream);
    source.connect(bridge.mix);
    if (main) {
      bridge.hasMain = true;
      bridge.spare.splice(0).forEach((other) => other.disconnect());
    } else {
      bridge.spare.push(source);
    }
  }

  class HookedPC extends NativePC {
    constructor(...args) {
      super(...args);
      this.addEventListener("track", addInbound);
    }
  }
  window.RTCPeerConnection = HookedPC;
  if (window.webkitRTCPeerConnection) window.webkitRTCPeerConnection = HookedPC;

  function ready(timeoutMs) {
    if (bridge.video && bridge.audio) return Promise.resolve(true);
    return new Promise((resolve) => {
      bridge.waiting.push(resolve);
      setTimeout(() => resolve(false), timeoutMs);
    });
  }

  // Hace pasar una pista del asistente por la del dispositivo falso que pidió Teams.
  function disguise(track, fake) {
    const settings = fake.getSettings();
    const capabilities = fake.getCapabilities?.() ?? {};
    const constraints = fake.getConstraints?.() ?? {};
    const original = track.getSettings.bind(track);
    Object.defineProperty(track, "label", { get: () => fake.label, configurable: true });
    track.getSettings = () => ({ ...settings, ...original(), deviceId: settings.deviceId, groupId: settings.groupId });
    track.getCapabilities = () => capabilities;
    track.getConstraints = () => constraints;
    track.applyConstraints = async () => {};
    return track;
  }

  devices.getUserMedia = async (constraints) => {
    bridge.stats.requests++;
    const entry = { asked: JSON.stringify(constraints).slice(0, 300), result: "pending" };
    bridge.log.push(entry);
    let base;
    try {
      base = await nativeGetUserMedia(constraints);
    } catch (error) {
      entry.result = `error: ${error.name} ${error.message}`;
      throw error;
    }
    if (!(await ready(20000))) {  // sin puente, Teams al menos entra con el dispositivo falso
      entry.result = "sin puente: dispositivo falso";
      return base;
    }
    entry.result = `entregado: ${base.getTracks().map((t) => t.kind).join("+")}`;
    const stream = new MediaStream();
    for (const fake of base.getTracks()) {
      const ours = fake.kind === "audio" ? bridge.audio : bridge.video;
      stream.addTrack(disguise(ours.clone(), fake));
      fake.stop();
    }
    bridge.stats.served++;
    return stream;
  };

  function iceComplete(pc) {
    if (pc.iceGatheringState === "complete") return Promise.resolve();
    return new Promise((resolve) => {
      pc.addEventListener("icegatheringstatechange", () => pc.iceGatheringState === "complete" && resolve());
      setTimeout(resolve, 3000);
    });
  }

  // Recibe la oferta de la página del avatar y devuelve la respuesta.
  own.accept = async (offer) => {
    own.pc?.close();
    const pc = (own.pc = new NativePC());
    pc.ontrack = ({ track }) => {
      own[track.kind] = track;
      if (own.video && own.audio) own.waiting.splice(0).forEach((resolve) => resolve(true));
    };
    await pc.setRemoteDescription({ type: "offer", sdp: offer });
    const heard = mixer().stream.getAudioTracks()[0];
    for (const transceiver of pc.getTransceivers()) {
      if (transceiver.receiver.track.kind !== "audio") continue;
      transceiver.direction = "sendrecv";
      await transceiver.sender.replaceTrack(heard);
    }
    await pc.setLocalDescription(await pc.createAnswer());
    await iceComplete(pc);
    return pc.localDescription.sdp;
  };
  own.status = () => ({
    connection: own.pc?.connectionState ?? "none",
    video: own.video?.readyState ?? "none",
    audio: own.audio?.readyState ?? "none",
    ...own.stats,
    log: own.log.slice(-8),
    appBlocked,
  });

  window.__tecPuente = own;
})();
