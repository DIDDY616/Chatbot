// Corta el audio de la reunión en frases: detecta cuándo alguien empieza y deja de hablar.
// Corre en el hilo de audio, así que sigue funcionando aunque la ventana esté en segundo plano.
//
// Mensajes que envía:
//   { type: "start" }                         alguien empezó a hablar
//   { type: "sustained" }                     lleva hablando lo suficiente como para interrumpir
//   { type: "partial", samples, sampleRate }  lo dicho hasta ahora, para buscar el nombre sin esperar al final
//   { type: "segment", samples, sampleRate }  frase terminada (Float32Array mono)
//   { type: "discard" }                       era un ruido corto, no una frase

const MIN_LEVEL = 0.006;      // nivel mínimo para contar como voz (≈ -44 dB)
const FLOOR_FACTOR = 3;       // la voz debe superar este múltiplo del ruido de fondo
const START_MS = 120;         // voz continua para dar por empezada una frase
const END_MS = 900;           // silencio que da por terminada la frase
const SUSTAINED_MS = 700;     // voz acumulada que cuenta como interrupción
const PARTIAL_MS = [800, 1600];  // voz acumulada tras la que se adelanta lo dicho ("Oye TecBot, …")
const MIN_VOICED_MS = 300;    // por debajo de esto es un ruido, no una frase
const MAX_MS = 20000;         // corta frases interminables
const PREROLL_MS = 400;       // audio previo al inicio, para no comerse la primera sílaba

class Segmenter extends AudioWorkletProcessor {
  constructor() {
    super();
    this.floor = 0;
    this.preroll = [];      // bloques recientes mientras no hay voz
    this.blocks = null;     // bloques de la frase en curso
    this.aboveMs = 0;
    this.silenceMs = 0;
    this.voicedMs = 0;
    this.totalMs = 0;
    this.sustained = false;
  }

  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input) return true;
    const block = input.slice();
    const blockMs = (block.length / sampleRate) * 1000;
    let sum = 0;
    for (const sample of block) sum += sample * sample;
    const level = Math.sqrt(sum / block.length);
    const voiced = level > Math.max(MIN_LEVEL, this.floor * FLOOR_FACTOR);

    if (!this.blocks) {
      this.floor = this.floor * 0.999 + level * 0.001;
      this.preroll.push(block);
      if (this.preroll.length * blockMs > PREROLL_MS) this.preroll.shift();
      this.aboveMs = voiced ? this.aboveMs + blockMs : Math.max(0, this.aboveMs - blockMs);
      if (this.aboveMs >= START_MS) {
        this.blocks = this.preroll;
        this.preroll = [];
        this.silenceMs = 0;
        this.voicedMs = this.aboveMs;
        this.totalMs = 0;
        this.sustained = false;
        this.partials = 0;
        this.port.postMessage({ type: "start" });
      }
      return true;
    }

    this.blocks.push(block);
    this.totalMs += blockMs;
    if (voiced) {
      this.voicedMs += blockMs;
      this.silenceMs = 0;
    } else {
      this.silenceMs += blockMs;
    }
    if (!this.sustained && this.voicedMs >= SUSTAINED_MS) {
      this.sustained = true;
      this.port.postMessage({ type: "sustained" });
    }
    if (this.voicedMs >= PARTIAL_MS[this.partials]) {
      this.partials++;
      this.send("partial");
    }
    if (this.silenceMs >= END_MS || this.totalMs >= MAX_MS) this.finish();
    return true;
  }

  send(type) {
    const samples = new Float32Array(this.blocks.reduce((total, b) => total + b.length, 0));
    let offset = 0;
    for (const b of this.blocks) {
      samples.set(b, offset);
      offset += b.length;
    }
    this.port.postMessage({ type, samples, sampleRate }, [samples.buffer]);
  }

  finish() {
    if (this.voicedMs >= MIN_VOICED_MS) {
      this.send("segment");
    } else {
      this.port.postMessage({ type: "discard" });
    }
    this.blocks = null;
    this.aboveMs = 0;
  }
}

registerProcessor("segmenter", Segmenter);
