// Escucha continua para el modo reunión: mantiene el micrófono abierto y entrega cada frase
// que oye como un WAV. El corte en frases lo hace escucha-worklet.js.

const moduleLoaded = new WeakMap();  // el módulo se registra una sola vez por AudioContext

function encodeWav(samples, sampleRate) {
  const view = new DataView(new ArrayBuffer(44 + samples.length * 2));
  const text = (offset, value) => [...value].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  text(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  text(8, "WAVEfmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);              // PCM
  view.setUint16(22, 1, true);              // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([view], { type: "audio/wav" });
}

// Escucha la reunión y avisa de lo que oye. `source` es el identificador del micrófono a
// abrir (el cable de audio de la reunión; vacío = el predeterminado) o un nodo de audio que
// ya trae el sonido de la reunión (conexión directa, ver puente.js).
//   onStart()       alguien empezó a hablar
//   onSustained()   lleva hablando lo suficiente como para interrumpir al asistente
//   onPartial(wav)  lo dicho hasta ahora, a mitad de frase
//   onSegment(wav)  frase completa, lista para transcribir
// Devuelve una función que cierra la escucha.
export async function startMeetingListener(audioCtx, source, { onStart, onSustained, onPartial, onSegment }) {
  let stream = null;
  if (!(source instanceof AudioNode)) {
    // El audio de la reunión ya llega limpio: los filtros del navegador solo lo empeorarían.
    const audio = { echoCancellation: false, noiseSuppression: false, autoGainControl: false };
    if (source) audio.deviceId = { exact: source };
    stream = await navigator.mediaDevices.getUserMedia({ audio });
  }

  if (!moduleLoaded.has(audioCtx)) moduleLoaded.set(audioCtx, audioCtx.audioWorklet.addModule("escucha-worklet.js"));
  await moduleLoaded.get(audioCtx);
  const input = stream ? audioCtx.createMediaStreamSource(stream) : source;
  const segmenter = new AudioWorkletNode(audioCtx, "segmenter", { numberOfOutputs: 1, channelCount: 1, channelCountMode: "explicit" });
  const mute = new GainNode(audioCtx, { gain: 0 });  // mantiene el nodo activo sin que se oiga
  input.connect(segmenter).connect(mute).connect(audioCtx.destination);

  segmenter.port.onmessage = ({ data }) => {
    if (data.type === "start") onStart?.();
    else if (data.type === "sustained") onSustained?.();
    else if (data.type === "partial") onPartial?.(encodeWav(data.samples, data.sampleRate));
    else if (data.type === "segment") onSegment?.(encodeWav(data.samples, data.sampleRate));
  };

  return () => {
    segmenter.port.onmessage = null;
    input.disconnect(segmenter);
    segmenter.disconnect();
    mute.disconnect();
    stream?.getTracks().forEach((track) => track.stop());
  };
}
