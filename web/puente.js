// Puente con la pestaña de la reunión (conexión directa a Teams, sin OBS ni cables).
//
// Esta página produce la "cámara" y el "micrófono" del asistente y los envía por una conexión
// WebRTC local a la pestaña de Teams, que los entrega a Teams como si fueran dispositivos.
// En sentido contrario llega el audio de la reunión, que es lo que el asistente escucha.
// El intercambio de la oferta y la respuesta lo hace el programa que controla los dos
// navegadores (app/teams.py), llamando a window.puente.offer() y window.puente.finish().

const WIDTH = 1280;
const HEIGHT = 720;
const FPS = 30;
// Mismos colores que web/style.css: papel, tinta y un acento, sin degradados.
const PAPER = "#f3efe6";
const SURFACE = "#fffdf8";
const RULE = "#cfc8b8";
const INK = "#1c1b19";
const STATUS_COLORS = { idle: "#1d3f72", listening: "#b3261e", thinking: "#8a5a00", speaking: "#1a6b3f", loading: "#5a564e" };

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  ctx.fill();
}

function wrap(ctx, text, maxWidth) {
  const lines = [];
  let line = "";
  for (const word of text.split(/\s+/)) {
    const candidate = line ? `${line} ${word}` : word;
    if (line && ctx.measureText(candidate).width > maxWidth) {
      lines.push(line);
      line = word;
    } else {
      line = candidate;
    }
  }
  if (line) lines.push(line);
  return lines;
}

// Dibuja en un lienzo 2D lo que se verá en la reunión: fondo, avatar, estado y subtítulo.
// Se dibuja justo después de cada cuadro del avatar, que es cuando su imagen está disponible.
function createCompositor(head, getView) {
  const canvas = document.createElement("canvas");
  canvas.width = WIDTH;
  canvas.height = HEIGHT;
  const ctx = canvas.getContext("2d");

  function draw() {
    const { status, label, subtitle } = getView();
    ctx.fillStyle = PAPER;
    ctx.fillRect(0, 0, WIDTH, HEIGHT);

    // Avatar: escala hasta cubrir el cuadro y recorta lo que sobre, centrado.
    const source = head.renderer.domElement;
    if (status !== "loading" && source.width && source.height) {
      const scale = Math.max(WIDTH / source.width, HEIGHT / source.height);
      const w = source.width * scale;
      const h = source.height * scale;
      ctx.drawImage(source, (WIDTH - w) / 2, (HEIGHT - h) / 2, w, h);
    }

    // Indicador de estado, arriba a la derecha.
    ctx.font = "500 20px system-ui, 'Segoe UI', sans-serif";
    ctx.textBaseline = "middle";
    ctx.textAlign = "left";
    const pillWidth = ctx.measureText(label).width + 52;
    ctx.fillStyle = RULE;
    roundRect(ctx, WIDTH - pillWidth - 29, 23, pillWidth + 2, 42, 7);
    ctx.fillStyle = SURFACE;
    roundRect(ctx, WIDTH - pillWidth - 28, 24, pillWidth, 40, 6);
    ctx.fillStyle = STATUS_COLORS[status] ?? STATUS_COLORS.loading;
    ctx.beginPath();
    ctx.arc(WIDTH - pillWidth - 8, 44, 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = INK;
    ctx.fillText(label, WIDTH - pillWidth + 8, 45);

    // Subtítulo, abajo al centro.
    if (subtitle) {
      ctx.font = "500 30px system-ui, 'Segoe UI', sans-serif";
      ctx.textAlign = "center";
      const lines = wrap(ctx, subtitle, WIDTH - 220).slice(-4);
      const lineHeight = 42;
      const boxWidth = Math.max(...lines.map((line) => ctx.measureText(line).width)) + 56;
      const boxHeight = lines.length * lineHeight + 28;
      const top = HEIGHT - 36 - boxHeight;
      ctx.fillStyle = INK;
      roundRect(ctx, (WIDTH - boxWidth) / 2, top, boxWidth, boxHeight, 6);
      ctx.fillStyle = "#ffffff";
      lines.forEach((line, i) => ctx.fillText(line, WIDTH / 2, top + 14 + lineHeight * (i + 0.5)));
    }
  }

  const render = head.renderer.render.bind(head.renderer);
  head.renderer.render = (scene, camera) => {
    render(scene, camera);
    draw();
  };
  draw();
  return canvas.captureStream(FPS);
}

function iceComplete(pc) {
  if (pc.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve) => {
    const check = () => pc.iceGatheringState === "complete" && resolve();
    pc.addEventListener("icegatheringstatechange", check);
    setTimeout(resolve, 3000);  // con lo reunido hasta entonces basta en la misma máquina
  });
}

// Crea el puente. `getView()` devuelve { status, label, subtitle } para dibujar la imagen.
// Devuelve { inbound, offer, finish }: `inbound` es un nodo de audio con lo que se oye en la reunión.
export function createBridge(head, getView) {
  const audioCtx = head.audioCtx;
  const video = createCompositor(head, getView);
  const voice = audioCtx.createMediaStreamDestination();
  head.audioReverbNode.connect(voice);
  // La voz va a la reunión, no a las bocinas de esta máquina.
  audioCtx.setSinkId?.({ type: "none" }).catch(console.warn);

  const outgoing = new MediaStream([...video.getVideoTracks(), ...voice.stream.getAudioTracks()]);
  const inbound = new GainNode(audioCtx);
  let pc = null;
  let source = null;
  let player = null;
  const info = { state: "new", offers: 0 };

  async function offer() {
    pc?.close();
    source?.disconnect();
    pc = new RTCPeerConnection();
    info.offers++;
    info.state = "connecting";
    const connection = pc;
    pc.onconnectionstatechange = () => connection === pc && (info.state = pc.connectionState);
    pc.ontrack = ({ track }) => {
      if (track.kind !== "audio") return;
      const remote = new MediaStream([track]);
      // Chrome solo entrega a Web Audio el sonido de una conexión si además suena en un elemento.
      player = new Audio();
      player.muted = true;
      player.srcObject = remote;
      player.play().catch(() => {});
      source = audioCtx.createMediaStreamSource(remote);
      source.connect(inbound);
    };
    for (const track of outgoing.getTracks()) pc.addTrack(track, outgoing);
    for (const sender of pc.getSenders()) {
      if (sender.track?.kind !== "video") continue;
      const parameters = sender.getParameters();
      parameters.degradationPreference = "maintain-resolution";
      parameters.encodings = [{ ...(parameters.encodings?.[0] ?? {}), maxBitrate: 4_000_000, maxFramerate: FPS }];
      await sender.setParameters(parameters).catch(console.warn);
    }
    await pc.setLocalDescription(await pc.createOffer());
    await iceComplete(pc);
    return pc.localDescription.sdp;
  }

  async function finish(answer) {
    await pc.setRemoteDescription({ type: "answer", sdp: answer });
  }

  return { inbound, offer, finish, info };
}
