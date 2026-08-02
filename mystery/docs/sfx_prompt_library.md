# SFX Prompt Library

Prompts for generating the game's audio with a text-to-audio model, plus the
acceptance metrics a candidate has to pass before it goes in the manifest.

The synthesised assets in `frontend/public/audio/ui/` (see
`tools/generate_ui_sfx.py`) are good enough to ship. This document is the path to
the thing synthesis cannot fake: recorded material. Real foley carries
irregularity — every page turn is a different page — and no procedural generator
reproduces that without becoming a foley library itself.

## Why the original assets failed

Worth stating up front, because it is exactly what these prompts are written to
avoid. The previous assets were renders of the WebAudio fallback in
`frontend/src/sfx.ts`: one white-noise buffer through one gentle biquad, or one
oscillator sweep. Two consequences, both measurable:

* **No grain.** Spectral flatness 0.6–0.75 (white noise is 1.0) with a crest
  factor around 5. Real paper is dozens of discrete micro-transients; a single
  enveloped noise burst is one smooth cloud. That reads as static.
* **No usable band.** The old `click.wav` put 85% of its energy below 250 Hz and
  *zero* above 4 kHz. Laptop and phone drivers cannot reproduce 172 Hz, so they
  distort instead. Perceived crispness lives at 2–8 kHz.

Any generated replacement that scores like the old files sounds like the old
files, whatever it cost to produce.

## How to prompt a text-to-audio model

These models respond to **physical description**, not to quality adjectives.
"Crisp, satisfying click" is close to meaningless; "index finger pressing a small
plastic dome switch, close-mic'd" produces a click. Five things to specify, in
roughly this order of impact:

1. **Material and mechanism.** What is made of what, doing what to what.
   Plastic, cork, rubber, cartridge paper, graphite, brass. This is the single
   biggest lever.
2. **Gesture and speed.** "Flicked quickly", "drawn slowly", "pressed once".
   Speed determines the envelope, and the envelope is most of the identity.
3. **Perspective.** "Close-mic'd, 15 cm" versus "across a room". Everything in
   this game is a desk sound heard by someone sitting at the desk.
4. **Space.** Always say *dry* — "no reverb, no room tone". Generated reverb
   cannot be removed later, and it will fight the ambient bed the game already
   plays underneath.
5. **Exclusions.** Say what must not be there: "no music, no voice, no hum, no
   background". Models add atmosphere unprompted.

Two more rules that matter for this project specifically:

* **Ask for one take, not a montage.** Models love giving you three page turns in
  a row. Say "a single isolated event" and set the duration short.
* **Duration is a hint, not a contract.** Generate longer than you need and trim.
  The durations below are the *final* targets, matched to the existing assets so
  UI pacing is unchanged.

### Model notes

Availability and naming change quickly — check current docs rather than trusting
this list. Broadly, as of writing:

| Kind | Good for | Watch out for |
|---|---|---|
| Dedicated SFX generators (e.g. ElevenLabs Sound Effects) | Short one-shot foley. The best fit for everything in the `ui/` set. | Tends to add tails; trim hard. |
| Text-to-audio diffusion (e.g. Stable Audio and its open variants) | Longer textures, ambience, stingers. | Often outputs 44.1 kHz stereo with a slow fade-in — trim the head. |
| Research models (e.g. AudioGen-class) | Cheap bulk iteration, self-hosted. | Lower fidelity; usually 16 kHz, which is fatal here since the band we need is 2–8 kHz. **Do not use a 16 kHz model for UI clicks.** |
| Music models | Ambient beds and stingers only. | Never for foley. |

Whatever you use, generate 5–10 candidates per sound. Hit rate on short foley is
low, and picking is much cheaper than prompt-tuning.

---

## UI sounds

Filenames map to `frontend/public/audio/manifest.json` under `ui`. Durations are
post-trim targets.

### `click.wav` — 55 ms
> A single small plastic dome switch being pressed once by a fingertip. Tight
> mechanical tick with a short bright body and a faint second contact as the dome
> bottoms out. Close-mic'd at 15 cm, completely dry, no reverb, no room tone, no
> music, no voice. One isolated event.

### `pin_push.wav` — 120 ms
> A brass pushpin being pressed into a cork noticeboard by a thumb. A bright
> puncture at the front, then a soft fibrous compression as the cork gives.
> Close-mic'd, dry, no reverb, no background, single event.

### `stamp_thunk.wav` — 240 ms
> A wooden-handled rubber stamp struck down onto a sheet of paper on a wooden
> desk. Firm rubber slap, dull wooden resonance underneath, paper compressing.
> Close-mic'd, dry, no reverb, no music, one isolated impact.

### `page_turn.wav` — 340 ms
> A single page of a hardback casebook being turned by hand. The paper is flicked
> up and over, then flops down onto the page beneath. Two distinct gestures — the
> flick, then the settle. Close-mic'd, dry, no reverb, no room tone, no voice.

### `paper_slide.wav` — 240 ms
> One sheet of cartridge paper sliding across a wooden desk, pushed by a hand.
> Continuous dry friction with the paper catching and releasing slightly.
> Close-mic'd, dry, no reverb, no background, single continuous movement.

### `sheet_pull.wav` — 420 ms
> A single sheet of paper being drawn out of a stiff cardboard folder. Long dry
> friction that ends as the sheet clears the folder edge. Close-mic'd, dry, no
> reverb, no background, one movement.

### `pencil_scratch.wav` — 580 ms
> A graphite pencil writing four short strokes on paper laid on a wooden desk.
> Rough, irregular, each stroke slightly different in length and pressure.
> Close-mic'd, dry, no reverb, no music, no voice.

> [!NOTE]
> "Each stroke slightly different" is load-bearing. The asset this replaces was
> one 145 ms burst repeated four times identically, which is audible as a
> stutter. If the generated take sounds mechanically regular, reject it.

### `lens_adjust.wav` — 180 ms
> The focus ring of a brass magnifying glass being turned two detents by hand.
> Two small metallic clicks with a faint gritty glide between them. Close-mic'd,
> dry, no reverb, no background, single movement.

### `map_select.wav` — 205 ms
> A small wooden marker being set down onto a paper map on a desk. A muted
> wooden tap with a brief hollow ring. Close-mic'd, dry, no reverb, no music,
> one isolated event.

### `evidence_inspect.wav` — 340 ms
> A small item being picked up off a desk and turned over in the hand — light
> handling rustle, then the item settling back against the wood with a small hard
> tap. Close-mic'd, dry, no reverb, no background, no voice.

### `question_send.wav` — 255 ms
> A fountain pen tapped once on a desk, then an index card flicked away across
> the surface. Close-mic'd, dry, no reverb, no music, no voice, single gesture.

### `location_shift.wav` — 480 ms
> A soft airy pass-by, as of a hand sweeping papers aside on a desk. Mid-range
> movement of air with paper caught in it, fading away. Close-mic'd, dry, no
> reverb, no music, no voice.

> [!IMPORTANT]
> Do not accept a sub-bass whoosh here, however impressive it sounds on
> headphones. A laptop speaker converts sub-bass into flapping distortion. Keep
> the energy centred 300 Hz–2.5 kHz — see the acceptance metrics.

---

## Stingers

These are dramatic rather than diegetic, so they tolerate music-model output.
They live under `stingers` in the manifest, and the game plays the `_short`
variants. They are generated by `tools/generate_stingers.py`.

**Key: E minor.** Taken from the assets originally shipped — `case_solved` was a
G–B–E triad and `clue_discovered` an A–E fifth — so the set stays consistent with
the ambient beds. Any replacement should stay in E minor or be checked against
the beds, because a sting a semitone off the bed is worse than no sting.

The originals had the same defect as the old click, more severely:
`contradiction_locked`, `pressure_cracking`, `case_failed` and `intro_tension`
carried 99.5–100% of their energy below 250 Hz with centroids of 62–131 Hz, and
none of them had *any* energy above 4 kHz. The fix is not "move everything up" —
dread needs low notes. It is that a low note must have **harmonics**. A bowed
string at E2 puts partials at 165, 247, 330, 412 Hz and up, so a laptop renders
the note through those and the ear supplies the missing fundamental. A sine at
E2 gives the driver nothing it can reproduce, so it distorts. Prompts below ask
for instruments rather than tones for exactly this reason.

### `clue_discovered_short.wav` — 0.9 s
> A short dramatic sting for a moment of realisation. A single bowed string note
> rising with a soft bell struck over it, resolving quickly. Sparse, dry, no
> percussion loop, no drums, ends cleanly.

### `contradiction_locked_short.wav` — 0.95 s
> A short dark sting for a lie being caught. A low string swell and a single dull
> metallic impact, decaying fast. Tense, sparse, no drums, no melody, ends
> cleanly.

### `pressure_defensive_short.wav` — 1.15 s
> A short uneasy sting: a quiet dissonant string tremolo rising slightly and
> stopping. Restrained, no percussion, no melody, dry.

### `pressure_cracking_short.wav` — 1.2 s
> A short sting of someone starting to break: a strained high string note over a
> low sustained drone, unstable, ending unresolved. No drums, no melody, dry.

### `accusation_submitted_short.wav` — 0.8 s
> A short decisive sting: one dry timpani-like impact with a low string note
> underneath, cutting off quickly. No cymbals, no reverb tail, no melody.

### `case_solved_short.wav` — 2.1 s
> A short resolving cadence for a mystery solved: warm strings settling onto a
> major chord with a single soft bell. Restrained and melancholy rather than
> triumphant. No drums, no fanfare, ends cleanly.

### `case_failed_short.wav` — 2.1 s
> A short sting for failure: low strings descending to an unresolved minor
> chord, fading. Bleak, quiet, no drums, no fanfare.

### `intro_tension.wav` — 1.25 s
> A short rising sting of unease: a low sustained string drone with a high
> tremolo string entering over it. Ends abruptly rather than fading. No drums,
> no melody, no reverb tail.

### `intro_discovery.wav` — 1.55 s
> A short sting for a case opening: one soft low drum, a single struck bell, and
> strings swelling to a suspended chord that does not resolve. Sparse, dry, no
> drums beyond the single hit.

### `intro_drama.wav` — 2.1 s
> A dramatic opening sting: a low drum hit, tremolo strings swelling underneath,
> a struck metallic accent, decaying away. Tense, restrained, no fanfare, no
> drum loop.

## Ambient beds

Under `ambient` in the manifest; these loop, so **seamlessness is the acceptance
criterion**. Generate 3–4× the length you need and find a loop point at a zero
crossing rather than trusting the model to loop.

### Investigation bed — 2–3 min, loops
> A sparse, slow, unsettling ambient bed for a detective story. Sustained low
> strings, occasional distant piano notes, faint room tone. No drums, no beat, no
> melody, no builds, no resolution. Uniform intensity throughout so it can loop.

### Accusation bed — 2–3 min, loops
> A tense sustained ambient bed. Low drone, high sustained string, a slow pulse.
> No drums, no melody, no builds. Uniform intensity throughout.

---

## Acceptance metrics

Do not judge these on headphones alone — the whole failure mode being fixed is
inaudible on good monitors and obvious on a laptop. Check the numbers, then
listen on the worst speaker you own.

```bash
python3 tools/generate_ui_sfx.py --check path/to/candidates
```

### UI sounds

Targets, derived from the shipped set:

| Metric | Target | What it catches |
|---|---|---|
| `crest` (peak ÷ RMS) | **> 8**, ideally 10–15 | Near 5 means an enveloped noise cloud with no transients — static. |
| `onsets/s` | **> 25** for textures (paper, friction) | Discrete events versus continuous wander. Meaningless for one-shot impacts, which correctly read ~0. |
| `<250 Hz` band | **< 25%** for clicks and textures; **< 45%** for impacts | Energy a small speaker will turn into buzz. |
| `1–4 kHz` band | **> 30%** for anything that must read as "crisp" | The band that carries perceived definition. |
| `centroid` | 2–4 kHz for clicks, 3–6 kHz for paper, 0.8–2 kHz for impacts | Overall brightness sanity check. |
| `peak` | 0.55–0.80 | Consistent headroom across the set. |

### Stingers

Different targets. Sustained music legitimately has a lower crest factor than
foley, and a low drone is a legitimate choice — so the gate is not "no bass", it
is **"enough content in the band a laptop can reproduce"**:

| Metric | Target | What it catches |
|---|---|---|
| `250 Hz–4 kHz` combined | **> 40%** | The real test. The originals scored 0–0.5% here; the shipped set scores 43–86%. |
| `<250 Hz` | < 60% | A bass-only cue. Fine to be bass-*heavy*, fatal to be bass-*only*. |
| `centroid` | 350–1100 Hz | The originals sat at 62–131 Hz. |
| `crest` | > 4.5, impacts > 8 | Distinguishes an articulated cue from a held tone. |

Also check by ear, since no metric covers these:

- **Silence at both ends.** A non-zero first or last sample is a DC step, which
  is an actual click artefact. The old `map_select.wav` ended on a non-zero
  sample.
- **No breath, no voice, no room.** Generated foley frequently smuggles in a
  faint room tone that becomes obvious once it loops under the ambient bed.
- **No musicality in the UI set.** If a click has a discernible pitch, it will
  clash with the ambient bed in some key. That is what made the old assets read
  as synth blips.

## Installing a candidate

1. Trim to the target duration, silence-to-silence.
2. Convert to **mono, 44.1 kHz, 16-bit PCM WAV** — matching the existing set.
3. High-pass at ~120 Hz (impacts) or ~150 Hz (textures) to drop rumble.
4. Apply a 5 ms raised-cosine fade at the tail so it ends at exactly zero.
5. Normalise to the peak target above.
6. Drop it in `frontend/public/audio/ui/` under the manifest's filename. No code
   change is needed — `manifest.json` already points at these names, and
   `audio.ts` fetches it at runtime.
7. Re-run `--check` and listen on a laptop speaker.

Keep `tools/generate_ui_sfx.py` even once real recordings land: `frontend/src/sfx.ts`
still synthesises live as a fallback when the manifest fails to load, and the
script documents what each sound is supposed to be.

---

## Choosing a method

The two halves of this audio set have **opposite** answers, which is the single
most useful thing to know before spending money or time.

### UI foley — synthesis gets you most of the way

Clicks, paper, friction. Procedural synthesis does well here because these
sounds are physically simple: a struck body is a bank of decaying resonances,
and paper is a cloud of tiny transients. Both are directly modellable, which is
what `tools/generate_ui_sfx.py` does.

What it *cannot* fake is irregularity. Every real page turn is a different page,
and a generator reproduces variety only by having variety programmed into it.
That ceiling is real but it is not very high above where the current assets sit.

**If you want to beat it:** record your own. These are desk sounds — paper, a
pencil, a pushpin, a stamp. A phone on a table in a quiet room at 1 am will
capture them, and 20 minutes of that will beat any amount of prompt-tuning,
because you are recording the actual objects the game depicts. Failing that,
CC0 packs from freesound.org. Generative models are the *weakest* option for
this half: short percussive foley is where they hallucinate most, and a 16 kHz
model cannot produce the 2–8 kHz band these sounds live in at all.

### Stingers — synthesis has a much lower ceiling

Here the ranking inverts. "A string section swelling" is precisely what additive
synthesis cannot convincingly fake: a real section is dozens of players with
independent bow noise, vibrato, and intonation, and `bowed()` approximates that
with four detuned voices and a random walk. It is a decent approximation — good
enough that these no longer sound broken — but a listener who knows strings will
know.

**If you want to beat it,** in order of effort:

1. **A licensed sting pack** (£30–80 for a cinematic/noir collection). Best
   result per unit effort by a wide margin, because you are buying recordings of
   real players. The catch is key: check each sting against E minor or plan to
   pitch-shift.
2. **A music-generation model.** A genuinely good fit for stingers — unlike
   foley, these are musical, short, and tolerate a little vagueness. The usual
   problems are that you cannot easily pin the key, and models add reverb tails
   you cannot remove. Generate many, keep the few in the right key.
3. **A sample library in a DAW.** Best possible control and quality, and the
   most work. Only worth it if you already own the library and know the tool.

### What I would actually do

Ship the synthesised set — it is measurably fine and it cost nothing. Then, if
audio matters enough to spend on: buy one sting pack for the seven dramatic cues
(the moments the player remembers), and record the twelve UI sounds yourself in
an evening. That is a few hours and under £100 for the whole set, and it beats
any amount of further generator work.

Whatever you pick, the durable asset here is not the audio — it is the
**measurable gate**. `--check` is what tells you a replacement is actually
better rather than merely different, and every claim in this document is a
number you can reproduce. The original assets shipped and stayed shipped because
nobody had a way to tell that a 69 Hz sine was not a sound.
