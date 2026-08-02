#!/usr/bin/env python3
"""Regenerate the diegetic UI sound effects in frontend/public/audio/ui/.

The previous assets were renders of the WebAudio fallback in frontend/src/sfx.ts:
one white-noise buffer through one gentle biquad, or one oscillator sweep. That
recipe has two audible failure modes.

  1. Undifferentiated noise. A single filtered noise burst has a spectral
     flatness of 0.6-0.75 (white noise is 1.0) and a crest factor around 5.
     Real paper foley is *grain* - dozens of discrete micro-transients, crest
     factor 15+. Without them you hear one smooth cloud of static swelling and
     fading, which is what "fuzzy static" describes.

  2. Everything living below 250 Hz. The old click put 85% of its energy under
     250 Hz and *zero* above 4 kHz. Laptop and phone drivers cannot reproduce
     172 Hz, so they distort instead - the buzz. Crispness lives at 2-8 kHz.

So this generator uses two techniques the fallback never had:

  * modal synthesis for anything struck or clicked - a short broadband
    transient exciting a bank of inharmonic decaying resonances, which is what
    a physical body actually does when you hit it; and
  * granular synthesis for anything made of paper - a Poisson cloud of tiny
    filtered-noise grains with heavy-tailed amplitudes, which restores the
    crest factor and the grain.

Every sound keeps the duration of the asset it replaces, so UI pacing is
unchanged. Seeds are fixed, so re-running reproduces the committed files.

Usage:
    python3 tools/generate_ui_sfx.py                 # write the wavs
    python3 tools/generate_ui_sfx.py --analyse       # write, then measure
    python3 tools/generate_ui_sfx.py --out /tmp/sfx  # write elsewhere
"""

from __future__ import annotations

import argparse
import os
import wave

import numpy as np

SR = 44100
OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "frontend",
    "public",
    "audio",
    "ui",
)


# --------------------------------------------------------------------------
# DSP primitives
# --------------------------------------------------------------------------

def n_samples(dur: float) -> int:
    return int(round(SR * dur))


def t_axis(dur: float) -> np.ndarray:
    return np.arange(n_samples(dur)) / SR


def band_noise(n: int, rng, lo=None, hi=None, order=2) -> np.ndarray:
    """Gaussian noise shaped by a zero-phase Butterworth magnitude response.

    Sources are filtered *before* they are enveloped, so transients stay sharp -
    filtering after the envelope smears the attack, which is half of why the old
    assets had no bite.
    """
    x = rng.standard_normal(n)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    h = np.ones_like(f)
    if lo:
        r = (f / lo) ** order
        h *= r / np.sqrt(1.0 + r * r)
    if hi:
        h /= np.sqrt(1.0 + (f / hi) ** (2 * order))
    return np.fft.irfft(X * h, n)


def modal(dur: float, spec, rng=None, detune=0.0) -> np.ndarray:
    """Sum of exponentially decaying sinusoids: spec = [(freq, amp, tau), ...].

    This is the impulse response of a struck body. Inharmonic ratios read as
    plastic/wood/metal; harmonic ratios read as a musical tone, which is what
    made the old click sound like a synth blip rather than a button.
    """
    t = t_axis(dur)
    y = np.zeros_like(t)
    for freq, amp, tau in spec:
        f = freq * (1.0 + rng.uniform(-detune, detune)) if (rng and detune) else freq
        y += amp * np.exp(-t / tau) * np.sin(2 * np.pi * f * t)
    return y


def transient(dur: float, rng, tau=0.0006, lo=1200, hi=12000) -> np.ndarray:
    """The initial spike: sub-millisecond broadband energy. This is the 'tick'."""
    n = n_samples(dur)
    src = band_noise(n, rng, lo=lo, hi=hi)
    return src * np.exp(-np.arange(n) / (SR * tau))


def grain_cloud(
    dur: float,
    rng,
    density: float,
    lo: float,
    hi: float,
    tau: float = 0.0012,
    env: np.ndarray | None = None,
    tail: float = 1.8,
) -> np.ndarray:
    """Poisson cloud of tiny filtered-noise grains - the texture of paper.

    Grain amplitudes are drawn from a Pareto distribution: most are quiet, a few
    are loud. That heavy tail is what produces a high crest factor, and a high
    crest factor is what the ear reads as 'discrete events' rather than 'static'.
    """
    n = n_samples(dur)
    y = np.zeros(n)
    src = band_noise(n + 4096, rng, lo=lo, hi=hi)
    glen = max(8, int(SR * tau * 7))
    shape = np.exp(-np.arange(glen) / (SR * tau))
    count = max(1, int(density * dur))
    onsets = np.sort(rng.uniform(0.0, dur, count))
    for onset in onsets:
        i = int(onset * SR)
        if i + glen >= n:
            continue
        amp = min(rng.pareto(tail) + 0.15, 8.0)
        if env is not None:
            amp *= float(env[i])
        y[i : i + glen] += src[i : i + glen] * shape * amp
    return y


def ad_env(dur: float, attack: float, tau: float, power: float = 1.0) -> np.ndarray:
    """Attack/decay envelope that starts at exactly zero (no boundary pop)."""
    t = t_axis(dur)
    return ((1.0 - np.exp(-t / max(attack, 1e-6))) * np.exp(-t / tau)) ** power


def swell(dur: float, peak_at: float, tau: float) -> np.ndarray:
    """Envelope that rises to a peak partway through, then decays - a swish."""
    t = t_axis(dur)
    rise = np.clip(t / max(peak_at, 1e-6), 0, 1) ** 1.6
    fall = np.exp(-np.maximum(t - peak_at, 0) / tau)
    return rise * fall


def norm(x: np.ndarray) -> np.ndarray:
    m = float(np.max(np.abs(x)))
    return x / m if m > 0 else x


def place(dst: np.ndarray, src: np.ndarray, at: float, gain: float = 1.0, unit: bool = True) -> None:
    """Mix src into dst starting at `at` seconds, clipped to the buffer.

    Layers are peak-normalised before mixing unless unit=False, so a layer's
    gain means 'how loud is this element relative to the others' rather than
    'whatever amplitude the synthesis happened to produce'. Without this the
    transient - the most important 5 ms of a click - gets buried under a modal
    bank whose amplitudes sum arbitrarily.
    """
    i = int(at * SR)
    j = min(len(dst), i + len(src))
    if i >= len(dst):
        return
    layer = norm(src) if unit else src
    dst[i:j] += layer[: j - i] * gain


def finish(
    y: np.ndarray,
    peak: float,
    hp: float = 90.0,
    fade_out: float = 0.005,
    fade_in: float = 0.0004,
) -> np.ndarray:
    """DC removal, a safety high-pass, raised-cosine edges, peak normalisation.

    Both edges must reach exactly zero. A non-zero boundary sample is a DC step,
    which is a broadband pop - the artefact the old map_select.wav had at its
    tail. The head needs it too: transient() starts on an arbitrary noise sample
    at full amplitude, so without a fade every impact opens on a step. 0.4 ms is
    shorter than one cycle at 2.5 kHz, so it costs nothing perceptually.
    """
    y = y - y.mean()
    if hp:
        X = np.fft.rfft(y)
        f = np.fft.rfftfreq(len(y), 1 / SR)
        r = f / hp
        X *= r / np.sqrt(1.0 + r * r)
        y = np.fft.irfft(X, len(y))
    k = min(len(y), int(SR * fade_in))
    if k > 1:
        y[:k] *= 0.5 * (1 - np.cos(np.linspace(0, np.pi, k)))
    k = min(len(y), int(SR * fade_out))
    if k > 1:
        y[-k:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, k)))
    m = float(np.max(np.abs(y)))
    return y * (peak / m) if m > 0 else y


def write_wav(path: str, y: np.ndarray, rng) -> None:
    """16-bit PCM with TPDF dither.

    Undithered quantisation of a long exponential decay produces granular
    distortion in the tail - a small but real contributor to the old fuzz.
    """
    dither = (rng.random(len(y)) - rng.random(len(y))) / 32768.0
    q = np.clip(y + dither, -1.0, 1.0)
    pcm = np.round(q * 32767.0).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# --------------------------------------------------------------------------
# The sounds
# --------------------------------------------------------------------------

def make_click(rng):
    """Toggles, dropdowns, compact controls: a small plastic dome switch.

    Body modes sit at 2.3-7 kHz where small speakers are actually efficient.
    A single 190 Hz mode supplies weight without asking a laptop for bass.
    """
    dur = 0.055
    y = np.zeros(n_samples(dur))
    place(y, transient(0.006, rng, tau=0.00035, lo=1800, hi=11000), 0.0, 0.85)
    place(
        y,
        modal(
            0.05,
            [(2320, 1.00, 0.0075), (3610, 0.72, 0.0055), (5180, 0.46, 0.0040),
             (7040, 0.28, 0.0028), (1480, 0.34, 0.0110)],
            rng,
            detune=0.02,
        )
        * ad_env(0.05, 0.00025, 0.010),
        0.0,
        1.0,
    )
    # A second, softer contact 6 ms later: the dome bottoming out.
    place(
        y,
        modal(0.03, [(2760, 1.0, 0.0035), (4380, 0.5, 0.0026)], rng, detune=0.02)
        * ad_env(0.03, 0.0002, 0.0045),
        0.006,
        0.30,
    )
    # Body weight. Kept at 245 Hz with a short decay and low gain: enough to
    # feel solid, not enough to ask a laptop driver for bass it cannot make.
    place(
        y,
        modal(0.05, [(245, 1.0, 0.009), (830, 0.55, 0.012)], rng) * ad_env(0.05, 0.0008, 0.011),
        0.0,
        0.16,
    )
    return finish(y, peak=0.62, hp=120)


def make_pin_push(rng):
    """A pushpin puncturing corkboard: bright puncture, dull fibrous body."""
    dur = 0.12
    y = np.zeros(n_samples(dur))
    place(y, transient(0.01, rng, tau=0.0007, lo=1600, hi=9000), 0.0, 0.70)
    place(
        y,
        modal(0.09, [(1120, 1.0, 0.014), (1930, 0.62, 0.010), (3240, 0.34, 0.006)], rng, detune=0.03)
        * ad_env(0.09, 0.0004, 0.018),
        0.0,
        1.0,
    )
    # Cork is fibrous: a short crackle of compressed material, not a clean tone.
    cork_env = ad_env(0.07, 0.0006, 0.020)
    place(y, grain_cloud(0.07, rng, 900, 600, 4200, tau=0.0012, env=cork_env), 0.001, 0.45)
    place(y, band_noise(n_samples(0.06), rng, lo=180, hi=900) * ad_env(0.06, 0.0015, 0.020), 0.002, 0.40)
    place(y, modal(0.1, [(240, 1.0, 0.030), (395, 0.5, 0.020)], rng) * ad_env(0.1, 0.001, 0.028), 0.001, 0.35)
    return finish(y, peak=0.72, hp=110)


def make_stamp_thunk(rng):
    """Rubber stamp onto paper onto a wooden desk.

    Wants weight, but the weight is carried by a 205 Hz desk mode plus a strong
    500-3000 Hz slap, so it still reads as heavy on a phone speaker.
    """
    dur = 0.24
    y = np.zeros(n_samples(dur))
    place(y, transient(0.012, rng, tau=0.0009, lo=800, hi=7000), 0.0, 0.45)
    # Rubber contact: broad, fast, mid-heavy. This is what carries the impact
    # on a small speaker, so it is the loudest layer, not the desk resonance.
    place(y, band_noise(n_samples(0.05), rng, lo=600, hi=3400) * ad_env(0.05, 0.0004, 0.011), 0.0, 1.0)
    # Desk resonance.
    place(
        y,
        modal(
            0.22,
            [(205, 1.00, 0.038), (342, 0.78, 0.032), (611, 0.60, 0.024), (1130, 0.34, 0.014)],
            rng,
            detune=0.02,
        )
        * ad_env(0.22, 0.0008, 0.038),
        0.001,
        0.34,
    )
    # Paper compressing under the stamp.
    place(y, grain_cloud(0.12, rng, 700, 1200, 6500, tau=0.0012, env=ad_env(0.12, 0.001, 0.028)), 0.003, 0.30)
    return finish(y, peak=0.80, hp=95)


def make_page_turn(rng):
    """A flick, then the page flopping down. Two gestures, not one swish."""
    dur = 0.34
    y = np.zeros(n_samples(dur))
    # Phase 1 - the flick: dense crackle rising then falling.
    e1 = swell(0.19, 0.075, 0.055)
    place(y, grain_cloud(0.19, rng, 2600, 1100, 7000, tau=0.0016, env=e1), 0.0, 1.0)
    place(y, band_noise(n_samples(0.19), rng, lo=800, hi=4200) * e1, 0.0, 0.40)
    # Phase 2 - the settle: sparser, duller, plus a soft low flap.
    e2 = swell(0.15, 0.035, 0.045)
    place(y, grain_cloud(0.15, rng, 1300, 550, 3600, tau=0.0022, env=e2), 0.185, 0.62)
    place(y, modal(0.13, [(268, 1.0, 0.030), (430, 0.45, 0.020)], rng) * ad_env(0.13, 0.004, 0.028), 0.19, 0.30)
    return finish(y, peak=0.68, hp=140)


def make_paper_slide(rng):
    """A sheet sliding across a desk: sustained friction with jittering grain."""
    dur = 0.24
    n = n_samples(dur)
    env = swell(dur, 0.05, 0.10)
    # Friction is not steady - the amplitude wanders as the sheet catches.
    jitter = 1.0 + 0.55 * band_noise(n, rng, hi=45, order=1) / 0.02
    jitter = np.clip(jitter, 0.25, 1.9)
    y = norm(band_noise(n, rng, lo=650, hi=4000) * env * jitter) * 0.45
    y += norm(grain_cloud(dur, rng, 1500, 1100, 6500, tau=0.0017, env=env))
    return finish(y, peak=0.58, hp=150)


def make_sheet_pull(rng):
    """Pulling a sheet clear of a folder: long friction, then it comes free."""
    dur = 0.42
    n = n_samples(dur)
    env = swell(dur, 0.10, 0.16)
    jitter = np.clip(1.0 + 0.5 * band_noise(n, rng, hi=32, order=1) / 0.02, 0.3, 1.8)
    y = norm(band_noise(n, rng, lo=550, hi=3600) * env * jitter) * 0.45
    y += norm(grain_cloud(dur, rng, 1250, 950, 6000, tau=0.0018, env=env))
    # The moment it clears the folder.
    place(y, grain_cloud(0.08, rng, 1900, 1500, 7500, tau=0.0013), 0.33, 0.45)
    place(y, modal(0.09, [(310, 1.0, 0.022)], rng) * ad_env(0.09, 0.003, 0.020), 0.335, 0.20)
    return finish(y, peak=0.58, hp=150)


def make_pencil_scratch(rng):
    """Four strokes of graphite. Each is independently random - no loop.

    The old asset repeated one 145 ms burst four times identically, which is
    audible as a machine-gun stutter.
    """
    dur = 0.58
    y = np.zeros(n_samples(dur))
    at = 0.0
    for i in range(4):
        slen = 0.105 + rng.uniform(-0.012, 0.018)
        n = n_samples(slen)
        env = swell(slen, 0.018, 0.045)
        # Stick-slip: friction noise gated by a fast irregular modulation.
        rough = np.clip(1.0 + 1.2 * band_noise(n, rng, lo=45, hi=380, order=1) / 0.02, 0.0, 2.2)
        centre = 2600 * (1.0 + rng.uniform(-0.16, 0.16))
        stroke = norm(band_noise(n, rng, lo=centre * 0.5, hi=centre * 1.9) * env * rough) * 0.65
        stroke += norm(grain_cloud(slen, rng, 2100, 1600, 8000, tau=0.0011, env=env)) * 0.8
        # Graphite drag against the desk beneath the paper.
        stroke += norm(band_noise(n, rng, lo=260, hi=700) * env) * 0.20
        place(y, stroke, at, 1.0 - 0.12 * i)
        at += slen + rng.uniform(0.028, 0.045)
        if at > dur - 0.06:
            break
    return finish(y, peak=0.55, hp=150)


def make_lens_adjust(rng):
    """A magnifier's focus ring: two detents with a little ratchet between."""
    dur = 0.18
    y = np.zeros(n_samples(dur))
    for at, gain in ((0.0, 1.0), (0.086, 0.78)):
        place(y, transient(0.005, rng, tau=0.0004, lo=2000, hi=10000), at, 0.60 * gain)
        place(
            y,
            modal(0.05, [(1960, 1.0, 0.008), (3140, 0.6, 0.006), (4870, 0.3, 0.004), (760, 0.42, 0.010)], rng, detune=0.03)
            * ad_env(0.05, 0.0003, 0.011),
            at,
            1.0 * gain,
        )
    # Metal-on-metal glide between the two detents.
    place(y, grain_cloud(0.085, rng, 620, 1800, 7000, tau=0.001, env=swell(0.085, 0.03, 0.05)), 0.004, 0.22)
    return finish(y, peak=0.55, hp=180)


def make_map_select(rng):
    """Selecting a location: a wooden marker tap with a small confirming ring."""
    dur = 0.205
    y = np.zeros(n_samples(dur))
    place(y, transient(0.008, rng, tau=0.0005, lo=1500, hi=9000), 0.0, 0.70)
    place(
        y,
        modal(0.12, [(740, 1.00, 0.020), (1290, 0.6, 0.014), (2180, 0.32, 0.009), (3560, 0.16, 0.006)], rng, detune=0.02)
        * ad_env(0.12, 0.0003, 0.024),
        0.0,
        1.0,
    )
    # Felt contact under the marker - keeps it from reading as a pure tone.
    place(y, grain_cloud(0.05, rng, 800, 1400, 9000, tau=0.001, env=ad_env(0.05, 0.0005, 0.012)), 0.0, 0.42)
    # A soft ring an octave up - reads as confirmation, kept quiet so it is a
    # texture rather than a jingle.
    place(y, modal(0.16, [(1480, 1.0, 0.055), (2960, 0.28, 0.030)], rng) * ad_env(0.16, 0.004, 0.055), 0.022, 0.22)
    return finish(y, peak=0.60, hp=160)


def make_evidence_inspect(rng):
    """Lifting an item for a closer look: handling rustle plus a glassy tap."""
    dur = 0.34
    y = np.zeros(n_samples(dur))
    env = swell(0.18, 0.05, 0.07)
    place(y, grain_cloud(0.18, rng, 1400, 1000, 6000, tau=0.0017, env=env), 0.0, 0.7)
    place(y, band_noise(n_samples(0.18), rng, lo=700, hi=3800) * env, 0.0, 0.28)
    # The item settling against the desk: a small hard tap, slightly late.
    place(y, transient(0.006, rng, tau=0.0004, lo=2000, hi=10000), 0.15, 0.45)
    place(
        y,
        modal(0.18, [(1620, 1.0, 0.030), (2740, 0.55, 0.020), (4310, 0.3, 0.012), (860, 0.4, 0.040)], rng, detune=0.02)
        * ad_env(0.18, 0.0004, 0.040),
        0.15,
        0.65,
    )
    return finish(y, peak=0.58, hp=160)


def make_question_send(rng):
    """A question leaving the desk: pen tap, then a card flicked away."""
    dur = 0.255
    y = np.zeros(n_samples(dur))
    place(y, transient(0.005, rng, tau=0.0004, lo=1800, hi=9500), 0.0, 0.60)
    place(
        y,
        modal(0.08, [(1840, 1.0, 0.012), (2980, 0.5, 0.008), (620, 0.35, 0.020)], rng, detune=0.02)
        * ad_env(0.08, 0.0003, 0.016),
        0.0,
        1.0,
    )
    env = swell(0.19, 0.055, 0.06)
    place(y, grain_cloud(0.19, rng, 1700, 1300, 7000, tau=0.0015, env=env), 0.055, 0.55)
    place(y, band_noise(n_samples(0.19), rng, lo=1000, hi=4500) * env, 0.055, 0.22)
    return finish(y, peak=0.55, hp=170)


def make_location_shift(rng):
    """Moving between locations: an airy pass-by with paper caught in it.

    Deliberately centred 300-2500 Hz. A sub-bass whoosh is exactly the sound a
    laptop speaker turns into flapping distortion.
    """
    dur = 0.48
    n = n_samples(dur)
    env = swell(dur, 0.16, 0.13)
    # Sweep the noise band downward by crossfading two filtered layers.
    ramp = np.linspace(0.0, 1.0, n) ** 1.3
    hi_layer = band_noise(n, rng, lo=700, hi=2800)
    lo_layer = band_noise(n, rng, lo=240, hi=1100)
    y = norm((hi_layer * (1 - ramp) + lo_layer * ramp) * env)
    y += norm(grain_cloud(dur, rng, 500, 900, 4500, tau=0.002, env=env)) * 0.40
    place(y, modal(0.3, [(320, 1.0, 0.070), (498, 0.45, 0.045)], rng) * ad_env(0.3, 0.010, 0.070), 0.10, 0.28)
    return finish(y, peak=0.56, hp=170)


SOUNDS = {
    "click": (make_click, 11),
    "pin_push": (make_pin_push, 12),
    "stamp_thunk": (make_stamp_thunk, 13),
    "page_turn": (make_page_turn, 14),
    "paper_slide": (make_paper_slide, 15),
    "sheet_pull": (make_sheet_pull, 16),
    "pencil_scratch": (make_pencil_scratch, 17),
    "lens_adjust": (make_lens_adjust, 18),
    "map_select": (make_map_select, 19),
    "evidence_inspect": (make_evidence_inspect, 20),
    "question_send": (make_question_send, 21),
    "location_shift": (make_location_shift, 22),
}


# --------------------------------------------------------------------------
# Measurement - the same metrics used to diagnose the originals
# --------------------------------------------------------------------------

def analyse(path: str) -> str:
    with wave.open(path, "rb") as w:
        n = w.getnframes()
        a = np.frombuffer(w.readframes(n), dtype="<i2").astype(float) / 32768.0
        sr = w.getframerate()
    spec = np.abs(np.fft.rfft(a * np.hanning(len(a))))
    f = np.fft.rfftfreq(len(a), 1 / sr)
    # Gate 60 dB below the spectral peak. The 16-bit dither floor is broadband,
    # so an ungated magnitude-weighted centroid reports the dither, not the sound.
    keep = spec > spec.max() * 1e-3
    spec = np.where(keep, spec, 0.0)
    power = spec**2
    energy = float(power.sum()) or 1.0
    centroid = float((power * f).sum() / power.sum())
    voiced = spec[keep]
    flat = float(np.exp(np.mean(np.log(voiced))) / np.mean(voiced)) if voiced.size else 0.0
    bands = [
        100 * float(power[(f >= lo) & (f < hi)].sum()) / energy
        for lo, hi in ((0, 250), (250, 1000), (1000, 4000), (4000, 22050))
    ]
    peak = float(np.abs(a).max())
    rms = float(np.sqrt(np.mean(a**2)))
    name = os.path.basename(path)
    return (
        f"{name:22} {len(a)/sr:5.2f}s  peak {peak:4.2f}  crest {peak/rms:5.1f}  "
        f"onsets {onset_rate(a, sr):5.0f}/s  flat {flat:5.3f}  centroid {centroid:6.0f}Hz  "
        f"bands <250 {bands[0]:5.1f}% | 250-1k {bands[1]:5.1f}% | 1-4k {bands[2]:5.1f}% | >4k {bands[3]:5.1f}%"
    )


def onset_rate(a: np.ndarray, sr: int) -> float:
    """Discrete attacks per second - the metric that separates foley from static.

    Crest factor says 'there are peaks'; this says 'there are many separate
    events'. Only meaningful for textures (paper, friction): a one-shot impact
    like click or stamp_thunk is a single event and correctly reports ~0.
    """
    hop = max(1, int(sr * 0.002))
    env = np.array([np.abs(a[i : i + hop]).max() for i in range(0, len(a) - hop, hop)])
    if env.size < 9 or env.max() <= 0:
        return 0.0
    # Smooth, then keep only rises that clear a local moving average by 60%.
    # Band-limited noise wanders constantly at frame resolution; without an
    # adaptive threshold this just counts that wander and reports static as
    # grain, which is worse than reporting nothing.
    k = np.ones(3) / 3.0
    env = np.convolve(env, k, mode="same")
    flux = np.maximum(np.diff(env), 0.0)
    win = 15
    local = np.convolve(flux, np.ones(win) / win, mode="same")
    strong = flux > np.maximum(local * 1.6, 0.06 * env.max())
    peaks = strong[1:-1] & (flux[1:-1] >= flux[:-2]) & (flux[1:-1] > flux[2:])
    return float(peaks.sum()) / (len(a) / sr)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=OUT_DIR, help="output directory")
    ap.add_argument("--analyse", action="store_true", help="print metrics after writing")
    ap.add_argument("--only", nargs="*", help="only regenerate these sounds")
    ap.add_argument(
        "--check",
        metavar="DIR",
        help="measure existing wavs in DIR and exit - use this to audition "
        "candidate audio from a text-to-audio model against the same metrics "
        "(see docs/sfx_prompt_library.md)",
    )
    args = ap.parse_args()

    if args.check:
        for entry in sorted(os.listdir(args.check)):
            if entry.lower().endswith(".wav"):
                print(analyse(os.path.join(args.check, entry)))
        return

    os.makedirs(args.out, exist_ok=True)
    names = args.only or list(SOUNDS)
    for name in names:
        if name not in SOUNDS:
            raise SystemExit(f"unknown sound: {name}")
        build, seed = SOUNDS[name]
        rng = np.random.default_rng(seed)
        path = os.path.join(args.out, f"{name}.wav")
        write_wav(path, build(rng), np.random.default_rng(seed + 1000))
        print(f"wrote {path}")

    if args.analyse:
        print()
        for name in names:
            print(analyse(os.path.join(args.out, f"{name}.wav")))


if __name__ == "__main__":
    main()
