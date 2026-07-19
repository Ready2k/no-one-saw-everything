import { Howler } from "howler";
import { audioManager } from "./audio";

// Diegetic UI sounds — paper, pins, pencil, rubber stamp. Production assets
// play through the audio manifest, with WebAudio synthesis kept as a fallback.
// Everything routes through Howler's master gain, so the existing mute button
// and volume slider govern these too.

const COOLDOWN_MS = 70;
const lastPlayed: Record<string, number> = {};

let noiseBuffer: AudioBuffer | null = null;

function ctx(): AudioContext | null {
  const c = Howler.ctx as AudioContext | undefined;
  if (!c || c.state === "closed") return null;
  if (c.state === "suspended") {
    // First gesture may fire us before Howler's own unlock listener.
    c.resume();
    return null;
  }
  return c;
}

function output(c: AudioContext): AudioNode {
  return (Howler as unknown as { masterGain?: GainNode }).masterGain ?? c.destination;
}

function getNoise(c: AudioContext): AudioBuffer {
  if (!noiseBuffer || noiseBuffer.sampleRate !== c.sampleRate) {
    noiseBuffer = c.createBuffer(1, c.sampleRate, c.sampleRate);
    const data = noiseBuffer.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  }
  return noiseBuffer;
}

function throttled(name: string): boolean {
  const now = performance.now();
  if (lastPlayed[name] && now - lastPlayed[name] < COOLDOWN_MS) return true;
  lastPlayed[name] = now;
  return false;
}

/** Filtered noise swish with a gentle envelope — the sound of paper. */
function noiseSwish(
  c: AudioContext,
  opts: {
    at?: number;
    duration: number;
    volume: number;
    filter: "bandpass" | "highpass" | "lowpass";
    freqFrom: number;
    freqTo: number;
    q?: number;
  }
) {
  const t = (opts.at ?? c.currentTime) + 0.001;
  const src = c.createBufferSource();
  src.buffer = getNoise(c);
  src.loop = true;
  // Random start offset so repeats never sound identical
  const offset = Math.random() * (src.buffer.duration - opts.duration - 0.01);

  const filter = c.createBiquadFilter();
  filter.type = opts.filter;
  filter.Q.value = opts.q ?? 0.9;
  filter.frequency.setValueAtTime(opts.freqFrom, t);
  filter.frequency.exponentialRampToValueAtTime(opts.freqTo, t + opts.duration);

  const gain = c.createGain();
  gain.gain.setValueAtTime(0.0001, t);
  gain.gain.exponentialRampToValueAtTime(opts.volume, t + opts.duration * 0.25);
  gain.gain.exponentialRampToValueAtTime(0.0001, t + opts.duration);

  src.connect(filter).connect(gain).connect(output(c));
  src.start(t, offset, opts.duration + 0.05);
}

/** Pitched thump — oscillator dropping in pitch, fast decay. */
function thump(
  c: AudioContext,
  opts: { at?: number; freqFrom: number; freqTo: number; duration: number; volume: number; type?: OscillatorType }
) {
  const t = (opts.at ?? c.currentTime) + 0.001;
  const osc = c.createOscillator();
  osc.type = opts.type ?? "triangle";
  osc.frequency.setValueAtTime(opts.freqFrom, t);
  osc.frequency.exponentialRampToValueAtTime(opts.freqTo, t + opts.duration);

  const gain = c.createGain();
  gain.gain.setValueAtTime(opts.volume, t);
  gain.gain.exponentialRampToValueAtTime(0.0001, t + opts.duration);

  osc.connect(gain).connect(output(c));
  osc.start(t);
  osc.stop(t + opts.duration + 0.05);
}

export const sfx = {
  /** Folder tab / view change: a sheet sliding across the desk. */
  paperSlide() {
    if (throttled("paperSlide")) return;
    if (audioManager.playUi("paper_slide")) return;
    const c = ctx();
    if (!c) return;
    noiseSwish(c, {
      duration: 0.22,
      volume: 0.05,
      filter: "bandpass",
      freqFrom: 1100 + Math.random() * 300,
      freqTo: 450,
      q: 0.7,
    });
  },

  /** Page turn: brighter, longer flick for opening covers and modals. */
  pageTurn() {
    if (throttled("pageTurn")) return;
    if (audioManager.playUi("page_turn")) return;
    const c = ctx();
    if (!c) return;
    noiseSwish(c, {
      duration: 0.16,
      volume: 0.045,
      filter: "bandpass",
      freqFrom: 500,
      freqTo: 2400 + Math.random() * 500,
      q: 1.1,
    });
    noiseSwish(c, {
      at: c.currentTime + 0.13,
      duration: 0.1,
      volume: 0.03,
      filter: "highpass",
      freqFrom: 1800,
      freqTo: 1200,
    });
  },

  /** Board pin pressed into cork. */
  pinPush() {
    if (throttled("pinPush")) return;
    if (audioManager.playUi("pin_push")) return;
    const c = ctx();
    if (!c) return;
    thump(c, { freqFrom: 1900, freqTo: 900, duration: 0.03, volume: 0.09, type: "square" });
    thump(c, { at: c.currentTime + 0.012, freqFrom: 240, freqTo: 110, duration: 0.07, volume: 0.14 });
  },

  /** Rubber stamp hitting the case file. */
  stampThunk() {
    if (throttled("stampThunk")) return;
    if (audioManager.playUi("stamp_thunk")) return;
    const c = ctx();
    if (!c) return;
    thump(c, { freqFrom: 150, freqTo: 55, duration: 0.16, volume: 0.4, type: "sine" });
    noiseSwish(c, {
      duration: 0.05,
      volume: 0.08,
      filter: "lowpass",
      freqFrom: 900,
      freqTo: 300,
    });
  },

  /** Pencil scribbling a note — a few irregular scratch bursts. */
  pencilScratch() {
    if (throttled("pencilScratch")) return;
    if (audioManager.playUi("pencil_scratch")) return;
    const c = ctx();
    if (!c) return;
    let t = c.currentTime;
    const bursts = 3 + Math.floor(Math.random() * 3);
    for (let i = 0; i < bursts; i++) {
      noiseSwish(c, {
        at: t,
        duration: 0.05 + Math.random() * 0.06,
        volume: 0.02 + Math.random() * 0.015,
        filter: "highpass",
        freqFrom: 1400 + Math.random() * 800,
        freqTo: 2200 + Math.random() * 800,
        q: 0.6,
      });
      t += 0.07 + Math.random() * 0.08;
    }
  },

  /** Small mechanical click for toggles, dropdowns, and compact controls. */
  click() {
    if (throttled("click")) return;
    if (audioManager.playUi("click")) return;
    const c = ctx();
    if (!c) return;
    thump(c, { freqFrom: 1700, freqTo: 900, duration: 0.025, volume: 0.06, type: "square" });
    thump(c, { at: c.currentTime + 0.008, freqFrom: 260, freqTo: 130, duration: 0.045, volume: 0.08 });
  },

  /** Evidence reveal: force the authored clue stinger, with a bright fallback. */
  evidenceFound() {
    if (audioManager.playStinger("clue_discovered", { force: true })) return;
    const c = ctx();
    if (!c) return;
    thump(c, { freqFrom: 520, freqTo: 1180, duration: 0.12, volume: 0.12, type: "sine" });
    thump(c, { at: c.currentTime + 0.06, freqFrom: 780, freqTo: 1760, duration: 0.16, volume: 0.08, type: "sine" });
    noiseSwish(c, {
      at: c.currentTime + 0.02,
      duration: 0.18,
      volume: 0.035,
      filter: "highpass",
      freqFrom: 1800,
      freqTo: 3600,
      q: 0.8,
    });
  },
};
