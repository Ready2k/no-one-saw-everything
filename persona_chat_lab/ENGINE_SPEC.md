# Interview Engine v2 — Specification

Written after a night of adversarial testing of two deterministic matching
approaches (literal keywords, concept clusters) against a real Owen/Priya
grounding pack. Every requirement below traces to a specific, reproduced
failure — this is not a generic "best practices" document. Where a finding
doesn't have a fix, that's stated explicitly as an accepted limitation, not
glossed over.

## 0. Non-negotiable invariants (carried from the shipped game, unchanged)

These are not up for redesign — they're why the architecture below is a
*layered* system rather than "swap the matcher for an LLM":

- **The truth firewall.** Hidden facts (killer identity, motive, method,
  lie flags) are never sent to any generation step that could leak them
  into player-facing text. A deterministic ground-truth computation happens
  *first*; anything downstream (rewrite, reasoning) only ever sees the
  already-sanitised allowed-facts list, never the case file.
- **Deterministic fallback always exists.** The game must be fully playable
  with zero network access. The engine below is a fallback-first design:
  everything through Layer 4 works with no LLM configured. Layers 5–6 are
  additive, not required.
- **Fairness/reproducibility.** Nothing about difficulty or available
  information may depend on whether an LLM happens to be reachable. A
  player who solves the case offline must have had access to the same
  clues as one with a model configured — only *delivery* differs.

## 1. Problem statement

A pure pattern-matching engine (keyword or concept, we tested both) is
provably good enough for casual play and provably insufficient for a
skilled interrogator. Concretely, over one evening we found and either
fixed or explicitly declined to fix:

| # | Failure | Class | Fixed? |
|---|---|---|---|
| 1 | Bare "hi" didn't match "hi " (trailing-space hack) | matching mechanics | yes |
| 2 | "partnership" (generic) beat "partnership letter" (specific) on a tie | scoring | yes — length/count weighting |
| 3 | Small talk unconditionally pre-empted better-fitting facts | architecture | yes — unified scoring |
| 4 | Typos ("yoursefl", "marcuss") | vocabulary | yes — bounded fuzzy correction |
| 5 | Short-word typos ("ma"→"me") unsafely correctable | vocabulary | **no — declared unfixable safely** |
| 6 | Reasonable questions triggered hostile deflects regardless of tone | tone calibration | yes — tiered deflect pools |
| 7 | "hi" alone matched nothing (word-boundary bug reintroduced) | matching mechanics | yes — regex `\b` throughout |
| 8 | Word-order sensitivity ("where you were" vs "where were you") | phrasing coverage | yes, per-instance — **not general** |
| 9 | Missing basic vocabulary ("alibi" itself; "cash" for "money") | content gap | yes/partial (see §7) |
| 10 | Concept ties resolved by declaration order, not relevance | scoring | **yes — see §6 update below** |
| 11 | Bare-word concepts caused false positives ("feeling" → murder reaction) | authoring discipline | yes — full-phrase concepts |
| 12 | **Entity misattribution**: third-party names answered with the wrong person's facts | missing dimension | yes — exclusion guards, but linear cost per fact |
| 13 | Fuzzy-typo-correction silently corrupted real words ("going"→"owing") | vocabulary | yes — raised threshold, measured gap |
| 14 | Zero replay variety — identical output every playthrough | content depth | yes — session-seeded variant pools |
| 15 | **Multi-fact reasoning**: synthesising two prior claims into a new inference | missing capability | **no — architecturally out of reach without LLM** |

Rows 5, 12, 15 are the load-bearing ones: they don't have a "write more
keywords" fix. They define where Layer 4 ends and Layer 6 begins. Row 10
*did* have a real fix (§6) — it's included in the table because it was
initially shipped as a known, accepted limitation before being properly
closed, and that history is worth keeping visible: the first version of
this build shipped the coarser metric not because it was inherent to
concept clustering, but because the better one hadn't been built yet.

## 2. Architecture overview

```
Player input
    │
    ▼
[Layer 1] Normalisation & Vocabulary Safety
    │  text-speak expansion, bounded fuzzy typo-correction
    ▼
[Layer 2] Structured Claim Store  ◄──────────────┐
    │  every authored fact has time/location/subject       │
    ▼                                                        │
[Layer 3] Entity & Subject Resolution                        │
    │  who is this question actually about?                 │
    ▼                                                        │
[Layer 4] Hybrid Matcher (deterministic, always available)   │
    │  concept clusters + precision-literal overrides        │
    ▼                                                        │
[Layer 5] Session & Pressure State                            │
    │  repeat tracking, escalation, seeded replay variety     │
    ▼                                                        │
[Layer 6] Tension Detector (deterministic, narrow)            │
    │  time/location arithmetic across the claim store ───────┘
    ▼
[Layer 7] LLM Reasoning Extension (optional — only if configured)
    │  full claim history in, sanitiser out
    ▼
[Layer 8] Persona Voice Renderer (always runs, both paths)
    │  archetype-based sentence restructuring
    ▼
Display text
```

Layers 1–5 and 8 are the deterministic floor — this is what tonight's
sandbox actually built and tested. Layer 6 is a narrow, worthwhile
deterministic extension. Layer 7 is where "barrister-tier" reasoning
actually lives, and it cannot be reached any other way (finding #15, §1).

### 2.1 Status and build order

This section is the source of truth for "what's actually done" — kept
current on every pass over this doc, so it never silently drifts out of
sync with the code the way an earlier draft of §4/§10 did.

| Step | Layer | Status | Where |
|---|---|---|---|
| 1 | Layer 1 — Normalisation (§3) | Built | `engine.py` (`_normalize`, `_fuzzy_correct`). Missing: the standing adversarial word-list test §3 calls for. |
| 2 | Layer 2 schema (§4/§4.1) | **Built, tested** | `claims.py` — `Fact`/`Trigger`/`GateCondition`/`Claim`/`ClaimStore`. 15 passing tests in `test_claims.py`, three of them run against real `personas.py` facts. |
| 3 | Layer 2 migration (§4.2) | Not started | `fact_from_legacy()` exists in `claims.py` and is tested, but the full `personas.py` migration — including the human `subject` audit — hasn't been run. |
| 4 | Layer 3 — Entity/Subject Resolution (§5) | Not started | Blocked on step 3: `subject` doesn't exist until the migration assigns it. |
| 5 | Layer 4 — Hybrid Matcher (§6) | Built, verified | `concepts.py` + `engine.py`. Length-weighted concept scoring already shipped and confirmed against three real ties. |
| 6 | Layer 5 — Session/Pressure (§7) | Built | `engine.py`'s `PersonaSession` — carried forward unchanged. |
| 7 | Layer 6 — Tension Detector (§8) | Not started | Blocked on step 3: needs a populated `ClaimStore` to reason over, which needs the migration run and wired into `engine.py`. |
| 8 | Layer 7 — LLM Reasoning (§9) | Designed, not started | Optional layer; blocked on steps 3 and 7. |
| 9 | Layer 8 generalisation (§10) | Not started | `_render_owen`/`_render_priya` exist as bespoke functions; the archetype system that replaces them is unbuilt. |

**Build order, and why**: step 3 (running the migration, including the
subject audit) is the one hard dependency almost everything else sits
behind — Layers 3 and 6 both read fields (`subject`, a populated claim
store) that don't exist until it's done, and `engine.py` still matches
against the old flat dicts until `ClaimStore` is actually wired in to
replace them. Layer 8's generalisation and Layer 1's remaining test-suite
gap don't depend on the migration and can happen in parallel with it.
Layer 7 stays last regardless — it's optional, and everything it needs
(§9.1's danger table) is itself built on the claim store the migration
produces.

- Text-speak expansion (`u`→`you`, `ur`→`your`) — word-boundary tokenised,
  small fixed table.
- Fuzzy typo-correction, but **bounded, not general**:
  - Only words ≥5 letters are eligible (shorter words are provably unsafe —
    finding #5: any cutoff loose enough to fix "ma"→"me" also corrupts
    "who"→"how", "she"→"the").
  - Cutoff must be empirically re-validated against the *current* vocabulary
    every time a new word is added, not set once. Tonight's cutoff moved
    from 0.78 to 0.85 after "going"→"owing" was found in production-style
    testing (finding #13) — 0.78 was chosen to make one test case pass, not
    validated against a word list. **Ship a standing adversarial word list
    (~50 common English words) as a unit test that runs against the live
    vocabulary on every content change**, not a one-off manual check.
  - Only correct *into* the persona's own vocabulary, never a fixed
    dictionary — the correction target must be a word that actually appears
    in some fact's trigger list, so a typo can never "correct" into
    something no fact would have matched anyway.

## 4. Layer 2 — Structured Claim Store

**Implemented in `claims.py`, tested in `test_claims.py` (see §2.1).** The
schema below is no longer a proposal — treat this section as documentation
of what's built, not a spec to (re-)implement.

**This is the single biggest structural change from tonight's sandbox**,
and it's what makes Layers 3 and 6 possible at all. Replace flat
`topic → text` facts with a claim schema that mirrors the shipped game's
`Claim` model (`models.py`) rather than reinventing one:

```python
Fact(
    topic: str,
    subject: AgentRef,           # who this fact is actually about — see §5
    time_reference: str | None,  # "07:05" — enables §6 arithmetic
    location_reference_id: str | None,
    trigger: Trigger,            # concept_groups OR literal keywords — see §4.1
    opening_variants: list[str], # 2+, session-seeded, same facts/different words
    repeat_variants: list[str],  # shorter restatements for same-session repeats
    truthfulness: Literal["true","false","mistaken"],
    sensitive: bool,             # extra pressure bump
    accusation: bool,            # exempt from concept clustering — see §5.3
    asserts_presence: bool,      # False = a denial ("never at the fountain") — see claims.py
    gate: GateCondition | None,  # see §4.1
)
```

Every fact the detective can extract becomes a first-class, timestamped
claim the moment it's revealed — logged into a **session claim store**,
not just rendered as text and forgotten. This claim store is what Layer 6
reasons over, and it's exactly the input the shipped game's
`testimony.py:find_conflict` already expects (same tolerances: 5 minutes
for bilocation, 20 for denial) — reuse that module rather than rebuilding
contradiction math.

### 4.1 `Trigger` and `GateCondition`, defined

Both types were left as placeholders in an earlier draft of this spec.
Pinning them down here because §4 is the layer everything else depends on —
a guessed-at schema here is the most expensive place in the whole doc to
get wrong.

```python
Trigger = ConceptTrigger(concept_groups: list[frozenset[str]]) \
        | LiteralTrigger(keywords: list[str])

GateCondition(topic: str, min_ask: int = 1)
```

- **`Trigger` moves matcher choice from persona-level to per-fact.**
  Tonight's sandbox picks concepts-vs-keywords once per persona
  (`personas.py`'s `matcher` field) — but §5.3 already requires a
  concept-matched persona to have *specific* facts (accusation,
  confession-adjacent) fall back to literal-only matching. That only works
  cleanly if the trigger type is a property of the fact, not the persona:
  every fact carries its own `Trigger`, and §5.3's exemption list becomes
  "these facts get authored with a `LiteralTrigger`," not a special case in
  the matcher. The persona-level `matcher` field goes away entirely.
- **`GateCondition` formalises what `gate_topic`/`gate_min_ask` already do**
  in the sandbox (`engine.py:_match_fact`'s `gate_topic and
  self.ask_counts.get(gate_topic, 0) < fact.get("gate_min_ask", 1)`): a fact
  becomes eligible only once `topic` has been asked at least `min_ask`
  times. No behaviour change, just a named type instead of two loose dict
  keys.

### 4.2 Migrating the existing content

`personas.py`'s ~574 lines of flat-dict facts need to become this schema.
**The mechanical half is already written and tested**: `claims.py`'s
`fact_from_legacy()` does `keywords` → `LiteralTrigger`, `concept_groups` →
`ConceptTrigger`, `gate_topic`/`gate_min_ask` → `GateCondition`,
`opening`/`repeat` → `opening_variants`/`repeat_variants`, and the
minutes-int → "HH:MM" conversion `time_reference` needs — confirmed against
real facts from both `OWEN` and `OWEN_TWIN` in `test_claims.py`.

**What's still not done is the run, not the tool.** `fact_from_legacy()`
requires `subject` as an explicit keyword argument rather than guessing it,
because it's the one field a script cannot derive — it doesn't exist in
the current data at all (subject exclusion is currently done via
`exclude_keywords`/`exclude_concepts`, which the migration drops per §5),
so every one of `personas.py`'s facts still needs a human (or an agent
reading each fact's content) to decide its `subject` and call
`fact_from_legacy(raw, subject=...)` for it. That per-fact judgment call —
not the schema conversion — is the real cost of this layer, and it's the
same audit finding #12 already required, just done properly this time
instead of as an ever-growing exclusion list. `location_reference_id` is
also currently a slugified stand-in (`_slugify()` in `claims.py`), not a
real cross-referenceable ID — there's no location registry in this sandbox
to point at, unlike the shipped game's `loc_*` IDs.

## 5. Layer 3 — Entity & Subject Resolution

Finding #12 is the single most important fix of the night, and it should
never again be implemented as a per-fact `exclude_keywords` list (which is
what tonight's sandbox shipped, and which costs linear authoring time per
fact, audited by hand). Instead:

### 5.1 Every fact declares its subject explicitly
`Fact.subject` is not optional. `alibi`/`relationship`/`temper` etc. have
`subject = SELF` (the persona being interviewed). `opinion_isabella` has
`subject = "agent_isabella"`.

### 5.2 Subject resolution runs before topic matching, not after
Extract every named entity in the question (via the same concept/keyword
machinery, just for names instead of topics). If a named entity is present
and it is **not** the fact's declared subject, the fact is ineligible —
full stop, no exclusion list to maintain. If no entity is named, `SELF` is
assumed. This turns finding #12's fix from "audit N facts and add a name
list to each" into "declare one field per fact, correctly, once" — the
exclusion logic becomes structural instead of an ever-growing checklist
that's trivially forgotten (which is exactly how finding #12 first slipped
through on `alibi` itself despite being fixed everywhere else that round).

### 5.3 Precision-literal exemption for high-stakes intents
Not every trigger should be concept-clustered. Finding #11 showed that
loosely-scoped concepts (bare "feel"/"feeling") cause false positives
exactly where the stakes are highest. Keep a short, explicit list of
intents that use bounded literal phrases only, never single-word concept
membership: **accusation, confession-adjacent language, self-harm/distress
indicators (if ever added)**. The rule: if getting it wrong is
embarrassing or narratively dangerous, it doesn't get a loose synonym
cluster. Everything else (business status, temper, quality-of-work) is
fair game for concept clustering. In the §4.1 schema, this is simply
authoring those facts with a `LiteralTrigger`.

### 5.4 Scope: named entities only, not pronouns
§5.2's entity extraction resolves *named* entities ("Marcus", "Isabella")
only. "What did **he** say to you?" / "were **they** close?" are not
resolved to a subject — a bare pronoun falls through to `SELF`, same as an
unnamed question, which is silently wrong whenever the detective's previous
turn just named a third party. Real coreference (tracking the
most-recently-named entity across turns) is a materially harder problem
than named-entity matching and is explicitly out of scope for this pass —
see §13.

## 6. Layer 4 — Hybrid Matcher

Take the better half of each technique tested tonight rather than picking
one:

- **Concept clusters** for shared, low-stakes vocabulary (money, busy/quiet,
  violence-adjacent words) — this is where concepts demonstrably won
  tonight (findings: "close", "cash" caught for free).
- **Length-weighted scoring even for concepts**, not raw integer counts.
  Finding #10 was the concept engine's one unforced structural loss all
  night ("did he pay you ok" / "hey Owen, how are you" both lost to ties
  that keyword's character-length weighting resolved correctly). **Built
  and verified**: score a concept match by the total character length of
  the matched surface forms, not the count of concepts satisfied
  (`concepts.py:detected_concepts`/`concept_group_score`). Confirmed
  against three real cases — the two above, plus a third found afterward
  in live testing (`alibi_corroboration`'s bare "col" vs a new
  `col_relationship` fact's full phrase "how do you know col", identical
  1-concept ties, declaration order deciding the winner). Fixing the
  scoring resolved all three at once, retroactively, with no per-case
  patching. This keeps concept clustering's authoring-cost advantage while
  removing its only measured disadvantage — there was never a reason to
  ship the coarser metric other than not having built the fairer one yet.
- **Word-boundary regex everywhere**, never raw substring (`\b` on both
  sides where both sides are word characters, one-sided where the phrase
  ends in punctuation — finding #7's fix, generalised).

## 7. Layer 5 — Session & Pressure State

Carried forward from tonight's build largely unchanged, it held up well:

- Pressure escalates from sensitivity/accusation/confrontation-detection,
  not from raw miss-count alone — tiered deflection (mild → sharp) so an
  ordinary miss doesn't read as the character being randomly hostile.
- Repeat answers select a **different, shorter, pre-authored variant**, not
  the same text with a prefix bolted on.
- **Session-seeded replay variety** (finding #14): a fresh session mixes a
  random seed into every stable-hash pick — filler choice, body-language
  action, *and* which equally-complete opening variant plays — so two
  playthroughs asking the same first question don't get byte-identical
  output. Content depth (how many variants are authored) remains a
  separate, ongoing cost — the mechanism doesn't manufacture content, it
  only stops what exists from feeling stale on replay #2.

## 8. Layer 6 — Tension Detector (deterministic, narrow)

This is the one piece of "multi-fact reasoning" worth building without an
LLM, because it's genuinely bounded: **time-gap arithmetic between two
already-revealed claims about the same person.**

```
On each new question:
  1. Detect which of the player's own words reference an ALREADY-REVEALED
     claim's time or location (via Layer 4's own matcher — same mechanism,
     applied to the claim store instead of the fact bank).
  2. If exactly two claims are referenced together, compute the
     relationship (time delta via `case_store.minutes()`, or location
     adjacency if authored).
  3. If the delta is inside an authored "tight" threshold, render a canned
     acknowledgment referencing the actual numbers — not inventing new
     content, just doing arithmetic on what's already true and already
     told to the player.
```

**Edge cases (step 2), stated explicitly rather than left to whoever
implements it**: zero or one claim referenced isn't this detector's job —
falls through to normal Layer 4 matching. **Three or more** claims
referenced, or an ambiguous tie between two equally-scored candidate pairs,
is an honest miss, not a guess at which pair the player meant — the same
"a detector that cries wolf is worse than none" principle §4 already
inherits from `testimony.py`. Exactly two, unambiguous, or nothing fires.

**Where the "tight" threshold lives**: it's a property of a *pair* of
claims, not of a single fact, so it doesn't belong in the §4.1 `Fact`
schema. Author it as a single case-level constant (e.g.
`case.tension_threshold_minutes`), the same way `testimony.py` already
hardcodes its 5-minute/20-minute tolerances — this is deliberately a
different, looser number than testimony's contradiction tolerances, since
tension flags a dramatically tight gap, not a provable bilocation.

**Scope discipline**: this detector does exactly one thing (time-gap
tension between two claims). It is not a general reasoning engine, and it
should not grow into a library of hand-built detectors for every possible
clever combination — that path is finding #15's actual lesson: the
authoring cost of bespoke detectors grows combinatorially with the number
of facts a character has, and a barrister will always find a combination
nobody wrote a detector for. Build this one because it's cheap and the
gap-arithmetic is genuinely mechanical; do not treat it as a template to
repeat for every future "isn't it interesting that..." pattern.

## 9. Layer 7 — LLM Reasoning Extension (optional)

This is where the actual requirement — "handles a skilled barrister doing
indirect, multi-step cross-examination" — gets met. Everything before this
layer is the floor; this is the ceiling, and it is not reachable
otherwise (finding #15).

- **Input**: the full **structured claim store** (§4), not just recent chat
  text — the model should receive "Owen claimed: at 07:05, outside the
  cafe, argued with victim" and "Owen claimed: at 07:15, in his yard,
  alone" as structured facts, not have to re-parse them from prose. This
  is strictly more than the shipped game's current `recent_exchange`
  context and is what actually lets the model do what the tension
  detector in §8 can only do narrowly.
- **Output constraint**: same sanitiser contract as the shipped
  `dialogue_rewriter.py` — forbidden-facts list, unsupported-fact check (no
  named character the grounded context didn't already mention),
  ungrounded-violence-vocabulary check — **plus §9.1–§9.4 below, which are
  mandatory, not optional hardening. Do not ship this layer with only the
  single-fact forbidden-facts check.**

The risk this layer introduces — the model synthesising a new
true-but-hidden inference from two individually-safe claims (the same thing
a human barrister does deliberately) — is not a new *kind* of problem. The
shipped game already solves the single-facet version of it:
`dialogue_rewriter._concept_combination_leak` rejects a rewrite that clears
a solution facet's `min_groups` threshold across multiple concept groups,
even though no single group would trip it, using the *identical* threshold
`judge.py` uses to grade a correct accusation. The design below generalises
that mechanism from "3 hand-authored facets" to "arbitrary pairs of Layer-2
claims" — it does not invent semantic-synthesis detection from scratch, and
it specifically avoids a live LLM judge call: any generation step is bound
by the truth firewall in §0, and a judge call that has to see the hidden
solution to compare against it is exactly the kind of step §0 forbids.

### 9.1 Combination-leak detection: precomputed, not inferred at runtime

Compute a **danger table offline, at case-build time**: for every pair of an
agent's allowed claims, concatenate their `claim_text` and run the existing
`_concept_combination_leak` logic against it. Any pair that clears a facet's
threshold when neither claim alone does gets recorded as
`(claim_id_a, claim_id_b) → facet` in a new locked, server-only file
alongside `solution.json` — never served to the client, same firewall as
everything else in `case_store.py`. This is O(n²) claims per agent (tens,
not thousands), pure reuse of already-tested scoring code, and it runs once
per case at validation time, the same place `validator.py` already checks
timeline/clue-graph invariants.

### 9.2 Runtime enforcement: citation-grounded generation, O(1) lookup

Extend the rewrite schema (`RewriteResult` / `DialogueRewrite`) with
`source_claim_ids: list[str]` — the model must declare which Layer-2 claims
it drew on, not just emit free prose. The sanitiser's new check is a set
lookup against §9.1's table: does `source_claim_ids` hit a recorded
dangerous pair? Reject → fall back. No extra LLM call, no runtime exposure
of the hidden solution — the table is opaque IDs computed offline.

### 9.3 Backstops (citation compliance and vocabulary coverage are both imperfect)

- Keep the *existing* live `_concept_combination_leak` scan running against
  the actual output text too, in parallel with the citation lookup — catches
  a model that paraphrases into the grading vocabulary without honestly
  citing its sources. Fail closed: missing or empty citations on a
  claim-grounded answer are treated as maximally dangerous, not waved
  through.
- Hard-cap `source_claim_ids` at **2 per turn**. This mirrors §8's own
  "exactly two claims" discipline, keeps the danger table pairwise (never
  needs triples, which is where the combinatorics stop being cheap), and
  forces a barrister to build a combination across several turns rather
  than one LLM leap — safer, and closer to how real cross-examination
  actually works.

### 9.4 Scope carve-out: identity/time-location narrowing never reaches this layer

The riskiest leak class isn't motive/method/opportunity phrasing, it's
**identity via time/location narrowing** ("only Marcus was near the shed at
8:05") — and that's exactly what `testimony.py`'s bilocation/denial math and
§8's tension detector already own, deterministically. Layer 7 must never be
handed two time/location claims to freely cross-reference; that reasoning
stays in Layer 6. Layer 7's mandate is scoped to motive/method/opportunity-
flavoured claim pairs — precisely the surface §9.1's danger table covers.
This is a scope decision that closes the gap, not a sanitiser sophisticated
enough to close it after the fact.

- **Fallback**: if the model is unreachable, the sanitiser rejects the
  output, or the citation cap/lookup trips, degrade to Layer 6's narrow
  tension detector, then to a plain deflect — never to a blank response,
  matching `_diegetic_fallback`'s existing behaviour.
- **Residual risk, stated plainly (same spirit as §13)**: coverage depends
  on concept-group vocabulary completeness — the same caveat the *existing*
  single-fact checker already lives with today, not a new one this
  introduces. A model could still in principle imply a connection through
  phrasing subtle enough to dodge both the citation cap and the text-level
  backstop. This is a real, bounded residual, not a claim of zero-leak.

## 10. Layer 8 — Persona Voice Renderer

**Corrected from an earlier draft, which overstated this as done.** What
tonight's sandbox actually built is two bespoke, hand-written functions
(`_render_owen`, `_render_priya` in `engine.py`) — not an archetype system.
Generalising them into voice-card-driven archetypes
(clipped/rambling/measured/blunt/soft-spoken/clinical/lecturing/decisive/
etc.) is real, unbuilt work, not a formality: it means replacing two
one-off functions with a single renderer parameterised by archetype, and
only then checking it against the shipped case data's real `voice_card`
text across all 7 hand-authored cases. Until that generalised renderer
exists and has been run against that data, "verified" doesn't apply —
treat the archetype list itself as a reasonable starting design, not a
tested one.

Two things worth keeping from tonight's build once that generalisation
happens:

- Pressure-band-gated body language, so a stage direction never contradicts
  the separately-computed `observable_tells` panel (the bug that motivated
  this in the first place).
- Per-archetype closers/actions/hedges as data (as `OWEN_CLOSERS`/
  `PRIYA_HEDGES` etc. already are), so adding a ninth archetype is
  authoring a table, not writing a new function.

## 11. Fallback contract (explicit, must be testable)

| Condition | Behaviour |
|---|---|
| No LLM configured | Layers 1–5, 8 only. Layer 6 tension detector active. Honest deflect on anything else — never a hallucinated answer. |
| LLM configured, reachable | Full stack. §9.1–§9.3's combination-leak checks are mandatory, not optional. |
| LLM configured, times out / errors mid-session | Same session marks itself LLM-unavailable (matches existing `session.llm_unavailable` behaviour) and drops to the no-LLM row for the remainder of that session — no silent partial-degradation per-question. |
| Sanitiser rejects an LLM output | Falls to Layer 6, then to canned deflect. Never re-prompts silently more than once (cost/latency control). |

## 12. Testing requirements (non-negotiable, not a suggestion)

Every category found to break something tonight becomes a standing
regression suite, run before any content or matcher change ships:

1. Casual/terse phrasing ("hi", single words, no punctuation).
2. Typos, both safe-to-correct (≥5 letters) and unsafe (<5 letters, must
   NOT be corrected — assert the miss, don't just skip testing it).
3. Third-party substitution (every named character, substituted into every
   self-referential fact's trigger shape).
4. Word-order variants of every authored trigger phrase.
5. Direct accusation, indirect accusation, and confrontational tone without
   an explicit question mark.
6. Contradiction/callback questions referencing two already-revealed
   claims (exercises Layer 6; also the honest-miss baseline for Layer 4
   alone).
7. Genuine nonsense (empty string, whitespace, emoji, gibberish, single
   punctuation) — assert **no crash and no hallucinated fact-match**, only
   an honest deflect.
8. Cross-session replay: same first N questions, fresh session, assert
   output differs from the previous run (catches finding #14 regressing).
9. Adversarial vocabulary sweep (finding #13's fix) — run on every change
   to the concept/keyword tables, not just once.

## 13. Explicitly accepted limitations (do not re-litigate without new data)

- Short-word typo correction (finding #5) — unsafe at any cutoff, by
  measurement, not by inspection.
- General word-order tolerance — only specific, discovered reorderings are
  covered; a third ordering will still miss. This is whack-a-mole and is
  labelled as such on purpose.
- General multi-fact reasoning beyond the one narrow time-gap detector
  (§8) — anything else routes to Layer 7 or is an honest miss.
- Pronoun resolution (§5.4) — subject resolution only recognises named
  entities; "him"/"her"/"them" fall through to `SELF`-scoped matching
  rather than the third party the detective actually means. Real
  coreference tracking (resolving a pronoun to whichever entity was most
  recently named in the exchange) is a materially harder problem than
  named-entity matching and is out of scope for this pass, not an
  oversight.

## 14. Epilogue — what actually shipped to production

This sandbox's job was to find and validate fixes before touching
`mystery/backend`, not to become the production engine itself. It's now
committed as the research trail behind the fixes below, not as code meant
to run again. Status verified against the actual code
(`mystery/backend/app/`), not against a summary of it — grep/read results,
not assumed from commit messages.

| Layer | Status in production | Evidence |
|---|---|---|
| 1 — Normalisation & Vocabulary Safety | **Shipped**, after this epilogue was first written. Word-boundary matching was already in (`question_classifier.py:_phrase_present`). Text-speak expansion and bounded fuzzy typo correction added to `reference_resolver.py:normalize_text` (opt-in `vocab` param), fed by a static phrase vocabulary (question_classifier.py's ~19 inline lists hoisted to named constants) merged with a new `case_vocabulary()` covering agent/location/object/clue-title proper nouns. Cutoff re-validated empirically at 0.86 (not the sandbox's 0.85 — see `test_typo_tolerance.py`), because 0.85 let "strange" wrongly correct to "storage", a collision unique to this production vocabulary (case_001 is *The Storage Room Murder*). 560 passed, same 10 pre-existing unrelated failures. | `reference_resolver.py`, `question_classifier.py`, `test_typo_tolerance.py` |
| 2 — Structured Claim Store | **Already existed**, predating this whole exercise — `models.py`'s `Claim` was the reference `claims.py` was built to mirror. One real bug fixed: `interview.py` was silently dropping `time_to`, flattening every alibi span into a point, breaking testimony contradictions across most of the case library. | `models.py`, `interview.py`, `testimony.py` |
| 3 — Entity & Subject Resolution | **Shipped, and exceeds this spec.** `reference_resolver.py` + `question_classifier.py`'s `_last_named_other_agent`/`_confidently_about_victim` do real coreference — tracking the most-recently-named entity across a conversation to resolve bare pronouns. §5.4 and §13 declared exactly this out of scope for the sandbox; production solved it anyway. | `question_classifier.py` |
| 4 — Hybrid Matcher | **Shipped**, after this epilogue was first written — and it was a real gap, not a different adequate mechanism (measured first, then fixed; §14.1 keeps the measurement). `classify_question` was a first-match cascade of `if _any_phrase(...): return`, so the earlier rule always won regardless of fit. Rules now *compete*: each scores the characters of the question it accounts for (`_coverage`, §6's length weighting), reference resolution reports the surface form it matched so a named entity can be weighed, and declaration order survives only as the tiebreak. §2's other half is now literal too — `CHALLENGE_PHRASES` and `CONFRONTATIONAL_BLUFF_PHRASES` are §5.3 precision-literal *overrides* that outrank scoring outright, because "I accuse you" is an act the player is performing, not a topic to be outweighed. 639 passed, same 10 pre-existing unrelated failures. | `question_classifier.py`, `reference_resolver.py`, `test_layer4_scored_matcher.py` |
| 5 — Session & Pressure State | **Shipped.** `session_seed`, persisted across save/reload, fresh on reset. | `session.py` |
| 6 — Tension Detector | **Shipped**, built on `testimony.py`'s existing claim/contradiction machinery rather than a new one, since Layer 2 already existed. | `testimony.py`, `test_claim_tension.py` |
| 7 — LLM Reasoning Extension (§9.1–9.4) | **Shipped**, after this epilogue was first written. §9.1's danger table is `danger_table.py`, built per agent over pairs of authored `AnswerClaim`s by concatenating them and re-running the *existing* `_concept_combination_leak` — recording only pairs that leak when neither half does alone. Committed as `danger_table.json` beside `solution.json` for cases 001–007 (2/0/0/0/1/1/6 pairs; every one of them on that case's killer), written by `save_case_to_disk` for generated cases, and never loaded into `CaseData` so nothing can project it. §9.2: `DialogueRewrite.source_claim_ids` + `_citation_leak`'s O(1) lookup, wired as `_sanitise` check 4c. §9.3: the live text scan stays as a parallel backstop, cap of 2 enforced, empty citations fail closed *when* claim reasoning was actually offered. §9.4: a cited pair where both claims carry a time and a place is refused outright, and never enters the table. Gated off by default behind `claim_reasoning_enabled` per §9's "optional — only if configured", so the deterministic floor is byte-identical. 587 passed, same 10 pre-existing unrelated failures. Subsequently validated end-to-end against a real local model rather than the `fake` provider — see §14.2. | `danger_table.py`, `dialogue_rewriter.py`, `interview.py`, `test_layer7_citation_guard.py` |
| 8 — Persona Voice Renderer | **Shipped, generalised properly.** `dialogue_processor.py:_voice_archetype()` derives an archetype from `agent.voice_card` and drives fillers/actions/deflections through one shared `_ARCHETYPES` table — not the sandbox's two bespoke functions. | `dialogue_processor.py` |

**Net effect**: all 8 layers are now satisfied or exceeded in production,
arrived at independently of this sandbox's own Layer 2 migration path
(production never needed that migration — it already had a real claim
store). Layer 7 — the layer this whole spec calls "the ceiling... not
reachable otherwise" — is built and enforced. Layer 4, which spent this
document's life labelled an open question, turned out once measured to be
the last real gap, and is now closed.

### 14.1 Layer 4, measured — then fixed

The question was whether production's `classify_question` is a different
adequate mechanism or a genuine gap. It was a gap. The measurement is kept
below because it is what turned "unclear" into a specific, reproducible
defect, and because it is the baseline the fix is judged against.

**Mechanism.** `classify_question` is ~18 `if _any_phrase(LIST, q_norm):
return QuestionIntent(...)` rules in priority order. Nothing is scored, so
no two candidates ever compete; the earliest rule that matches *anything*
wins outright. Length-weighted scoring (§6) cannot be "already satisfied by
other means" when there is no scoring step to satisfy it.

**It bites in natural phrasing.** Rule 4 (relationship) sits ahead of rules
7/8/9 (object/evidence/location) and its trigger list contains the bare
words `know`, `trust`, `think of`. Measured against case_001:

| Question | Intent |
|---|---|
| `did the till weight belong to him?` | `object` ✔ |
| `did the till weight belong to him as far as you know?` | `relationship` ✘ |

Four characters of incidental politeness discard a resolved
`obj_till_weight`. A sweep injecting each bare single-word trigger from an
earlier rule into questions that otherwise classify correctly flipped the
intent **55/55 times** — not a tie broken badly, a contest never held. (The
sweep's own sentences are frankly compound, so the honest evidence is the
natural pair above; the sweep establishes the mechanism, not the frequency.)

**There is no downstream recovery.** `free_text_api.py:256` consults the LLM
classifier only `if not intent`. A wrong-but-confident deterministic answer
(0.85 above) is final, so this never degrades to the LLM path.

**The guards that exist are the whack-a-mole §1 predicted.** Rule 4 excludes
questions containing "where"/"when"; rule 4b reroutes CONFLICT phrasing to
relationship; greetings are checked last so a compound opener doesn't swallow
the real question. Each is a correct, hand-patched instance of what one
scoring change would do generally — which is finding #8's "yes, per-instance
— not general", and finding #11's bare-word-concept hazard, both alive in
shipped code.

**The fix.** §6's, not a reordering: reordering rules or deleting `know`
from `RELATIONSHIP_PHRASES` would only trade this failure for its mirror
image. Every rule now returns a *candidate* rather than returning outright,
scored by `_coverage` — the count of question characters that rule's matched
phrases actually account for. Coverage rather than a sum of matched lengths
is what makes overlapping list entries safe (`RELATIONSHIP_PHRASES` spells
one idea three ways; it must not score triple for that). Entity references
score the surface form the player actually used, which required
`resolve_references` to start reporting *what* matched, not just the id —
hence `resolve_reference_matches`, with the old id-only view kept as a thin
wrapper so no caller changed. Declaration order remains, demoted to the
tiebreak, which is what preserves every deliberate precedence decision for
the genuinely ambiguous questions those guards were written for.

**And §2's other half, which the measurement missed.** The first cut of the
fix regressed one labelled case: `I accuse you of lying — Clara saw you.`
became `contradiction`, because "saw you" is one character longer than
"accuse". Length weighting alone is therefore *not* the whole of §6 — §2
calls Layer 4 "concept clusters **+ precision-literal overrides**" and §5.3
names the intents that get the override. `CHALLENGE_PHRASES` and
`CONFRONTATIONAL_BLUFF_PHRASES` are exact performatives with no synonym
cluster behind them: "I accuse you" is something the player is *doing*, and
it now outranks scoring outright rather than competing on length. Both still
require their own trigger — an early version scored the named entity alone
and turned every mention of an object into an accusation.

**Result.** Across an 85-question corpus spanning every §12 category,
exactly two classifications changed, and both are the defect above. The
corpus is now `test_layer4_scored_matcher.py`, including the §12.2 misses
asserted rather than skipped (`where wer you` stays an honest miss — "wer" is
under the ≥5-letter fuzzy threshold, which §13 accepts by measurement) and a
guard that scoring never overrides Layer 3's coreference refusal.

### 14.2 Layer 7, against a real model

Layer 7 shipped proven against `fake` and against a purpose-built stub that
echoed back the claim ids it was shown. That left one question the test suite
structurally cannot answer, because §9.3 makes silence fatal: **does a real
model populate `source_claim_ids` at all?** If it ignores the field, every
claim-grounded turn fails closed, and turning Layer 7 on makes dialogue
strictly worse — the guard would be rejecting the model's output not because
it was dangerous but because it was undeclared.

Measured 2026-07-31 against a real Ollama endpoint with
`claim_reasoning_enabled` on. Two models, and **the answer is not a property
of the engine — it is a property of the model**:

> **Corrected below — see §14.6.** The acceptance rates in this table were
> real, but the mechanism given for them was wrong, and the conclusion drawn
> from it was backwards. It is left in place because the correction is the
> point: acceptance was measured, model behaviour was *inferred*, and the
> inference was false.

| Model | Safe-pair turns accepted with Layer 7 on | Claimed mechanism (wrong) |
|---|---|---|
| `llama3.1:8b` | **10/10** | "cites reliably" |
| `gemma4:latest` | **0/10** | "omits the field" |
| `qwen2.5-coder:7b` | **0/6** | "omits the field" |

`qwen2.5-coder:7b` was tested on the theory that a code-tuned model would be
the *most* disciplined about emitting a declared structured field. That much
was genuinely disproved — but see §14.6 for what it actually does instead.

`llama3.1:8b` never once tripped the fail-closed rule. `gemma4:latest` trips
it on every claim-grounded turn, so enabling Layer 7 with it means 100%
fallback to deterministic text — §9.3's predicted failure mode, live. Both
models accept 6/6 with Layer 7 *off*, which confirms the fallback is the
citation contract and nothing else.

**So Layer 7 is a per-model capability, and must be treated as one.** The
engine is correct in both cases — it is refusing an undeclared combination
exactly as designed — but "correct" and "usable" diverge depending on who is
answering. Anything that ships this flag should verify the configured model
actually populates the field before enabling it, rather than assuming.

**The guard fires on real output, not just a stub.** Handed case_001's
recorded danger pair (`claim_clara_ledger_denial` + `claim_clara_morning_prep`)
and an adversarial prompt — *"you were prepping that morning, and you deny
touching the ledger; put those together for me"* — the model took the bait
every time:

| Trial | Outcome |
|---|---|
| Danger pair, adversarial prompt (×4) | **4/4 refused** — `cited a combination that gives away motive (2/4 concept groups)` |
| Safe pair (`relationship` + `fountain`) (×4) | 4/4 accepted, each citing exactly 1 claim |

**Ordinary play does not trip it.** Driven through the HTTP API the way a
player reaches that pair — examine the body, discover `clue_ledger_page`,
ask Clara about her morning, then confront her with the ledger — the turn was
*accepted*, no fallback. The pair was genuinely available to cite:
`record_claim` (`interview.py:175`) precedes the `claim_history` build
(`interview.py:268`) inside `answer_question`, so both claims were in the
model's prompt and it declined to combine them. The danger table is therefore
a backstop against the adversarial case, not a standing tax on normal
dialogue.

**Caveats, stated rather than buried.** Two models, one case, small samples.
Nothing here establishes a general rate — it establishes that the mechanism
engages, and that whether silence is the default failure mode depends entirely
on the model.

There is also no control for `claim_reasoning_enabled` in `LlmSettingsModal`,
so Layer 7 is reachable only via the API or
`MYSTERY_LLM_CLAIM_REASONING_ENABLED`. The `Optional[bool] = None`
preserve-on-omit fix was re-verified live for exactly this reason: a
modal-shaped save that omits the field leaves the flag on, rather than
silently disabling the layer.

### 14.3 The unguarded failure: rewrites that move the clock

Found while comparing models for §14.2, and it is not a Layer 7 issue — it
is a hole in the *whole* rewrite path, and the more serious of the two
findings.

Asked "where were you that morning?", against Clara's authored line — *"Down
at half six, prep until Marcus arrived at a quarter to seven... Owen turned up
around seven"* — `llama3.1:8b` misplaced Marcus **4 times out of 4**:

| Run | Marcus's arrival, as told to the player |
|---|---|
| 1, 2, 4 | "around 07:00" (authored: 06:45) |
| 3 | **"around 07:15"** — a time appearing nowhere in the source |

All four also dropped Owen's scene entirely. `gemma4:latest` on the same
prompt preserved it: "six forty-five" exactly once, "near quarter to seven"
once, and once correctly declining to state a time at all.

**The sanitiser cannot catch this, by construction.** Every check in
`_sanitise` asks whether the rewrite says something it was *not allowed* to
say — role labels, hidden facts, undeclared combinations. A wrong time is none
of those. It is a plausible distortion of a fact the model *was* allowed to
state, and it passes every gate.

This matters more here than in an ordinary chatbot. The player's entire method
is building a timeline from testimony and finding where two accounts cannot
both be true; `testimony.py` adjudicates bilocation on a **5-minute**
tolerance. A rewrite that shifts an arrival by fifteen minutes does not
degrade flavour — it manufactures and destroys contradictions in the layer the
game is *about*, and the player has no way to know the clock moved.

The honest conclusion is that dialogue rewriting is safe with respect to
*truth leakage* (which is what every existing test guards) and unguarded with
respect to *factual fidelity*.

**The fix — `numeric_fidelity.py`, wired as `_sanitise` check 7.** A rewrite
may *drop* a time; it may not *move* one. Two rules, because one is not
enough:

1. **No invented times.** A clock time in the rewrite must appear in the
   source. This catches the fabricated 07:15.
2. **No reattributed times.** Times the rewrite attaches to a named person
   must be times the source attached to *that* person. This is what catches
   the 07:00, and rule 1 is structurally blind to it: 07:00 genuinely is in
   the source — as when *Owen* turned up. The model moved Marcus onto Owen's
   minute, and a set-membership check waves that through.

Equivalent phrasings must compare equal or the gate becomes noise, so
everything normalises to minutes mod 12h: `06:30`, `6:30`, `half six`, `half
past six` and `six-thirty` are one value; `quarter to seven` and `six
forty-five` are another. Overlap resolution is **longest-match-first**, and
that is load-bearing rather than cosmetic — "from six-thirty" also contains
"from six", and resolving by earliest start reads 06:00 and rejects a faithful
rewrite for inventing a time it never stated. (That bug was live in the first
cut, caught by the fixture of real model output before wiring.) A bare numeral
is only a time behind a temporal preposition, so "seven crates" stays a
quantity.

Attribution is deliberately conservative, following `testimony.py`'s tolerance
philosophy: a name binds a time only when it is in the same sentence and
precedes it, pronouns are never resolved, and a time the source never attached
to anyone is left to rule 1 alone. Guessing at attribution would invent
violations, and *a detector that cries wolf is worse than none* — the fallback
text is perfectly good, so a rewrite rejected for nothing is pure loss.

**Result, re-measured against both models.** 16 rewrites of Clara's morning,
every rejection audited against its raw model output:

| Model | Accepted | Rejected | False positives |
|---|---|---|---|
| `llama3.1:8b` | 0/8 | **8/8** — all "Marcus → 07:00" | **0** |
| `gemma4:latest` | 7/8 | 1/8 — "Marcus arrived near seven" | **0** |

Every single rejection was real drift. On a control question whose source
contains no times at all, both models pass 5/5, so the gate is narrow rather
than a general tax. 701 backend tests pass, no regressions.

What this changes is the standing of the two models. `llama3.1:8b` was
corrupting the timeline on *every* attempt at this question and the player had
no way to see it; it now falls back to the authored line every time, which is
correct but means it contributes nothing on timeline answers. `gemma4:latest`
was already largely faithful and stays usable. The check does not make a weak
model good — it makes a weak model *honest*, which is the only guarantee the
deterministic floor was ever offering.

### 14.4 The turn budget: a thinking model thinking on the player's time

`gemma4:latest` was the better writer and unusable anyway, at a median **12.5
seconds per line**. An interrogation is a conversation; ten seconds of silence
between question and answer is the difference between a suspect and a progress
bar.

The cost was not generation. Measured on one line of Clara's dialogue,
gemma4 emitted **~1,800 characters of hidden reasoning to produce ~220
characters of speech** — the player waits through an essay they never see.

Suppressing it (`reasoning_effort: "none"`) collapses the turn to **1.6s
median**, and — the part that decides it — acceptance under the sanitiser is
*unchanged*: 4/6 either way, same rewrites, same single failure mode. The
reasoning bought latency and nothing else. Over a larger sample with reasoning
off, gemma4 accepts **9/12** timeline rewrites at 2.5s median, against
`llama3.1:8b`'s **0/12** at 2.0s.

Two measured details that make this a real fix rather than a lucky flag:
`"low"` does **not** disable thinking (7.2s, reasoning intact) — only `"none"`
does; and capping `max_tokens` does not help, it only truncates the answer into
invalid JSON.

`reasoning_effort` is an OpenAI-API parameter rather than an Ollama one, so it
cannot simply be sent to every configured endpoint. `client.py` therefore
*probes and remembers*: the field goes out by default, an endpoint that rejects
it is retried once without and never sent it again, cached per (endpoint,
model). One extra request per configuration, never one per turn — and a server
that has never heard of the parameter degrades to exactly today's behaviour
instead of failing the turn.

### 14.5 Three models, and the failure nobody is guarding

All three models on the box, all four axes, with reasoning suppression on:

| Model | Median turn | Timeline fidelity | No-times question | Cites for Layer 7 | Refuses danger pair |
|---|---|---|---|---|---|
| `gemma4:latest` | 1.6s | **11/12** | 6/6 | 0/6 | 4/4 |
| `qwen2.5-coder:7b` | 1.5s | **12/12** | 6/6 | 0/6 | 4/4 |
| `llama3.1:8b` | 1.2s | **0/12** | 6/6 | **5/6** | 4/4 |

The tradeoff did not dissolve. The only model that can drive Layer 7 is the
only one that cannot keep a clock straight, and it fails *every* timeline
rewrite. Layer 7 and faithful dialogue remain mutually exclusive here.

**The new finding is a third failure mode, and it is unguarded.** Acceptance
was never a measure of usefulness: a rewrite can pass every check in
`_sanitise` by *saying nothing*. Against Clara's authored 150-character answer
about Marcus:

| Model | Behaviour |
|---|---|
| `gemma4:latest` | 149–166ch, 4/4 — substance intact |
| `qwen2.5-coder:7b` | 174–194ch three times, then **"I don't recall him personally."** (30ch) |
| `llama3.1:8b` | 76ch — *the identical sentence all four times*, half the authored content |

qwen's fourth answer is the sharp case: it leaks nothing, invents nothing,
moves no clock, and passes cleanly — while replacing a characterising answer
with a refusal the author never wrote, in a game where "I don't recall" is a
*meaningful* thing for a suspect to say. llama's is the quieter one: it halves
every answer and returns byte-identical text at temperature 0.2, so the
"variety" the rewrite layer exists to add is not there at all.

So the sanitiser guards leakage (checks 1–6) and, since §14.3, fidelity of
times (check 7). Nothing guards **content preservation** — that the rewrite
still says what the authored line said. That is the next gate, and it is the
one that separates a model that helps from a model that merely fails safely.
It also needs the most care of the three: an authored deflection legitimately
*is* short and evasive, so a naive length floor would reject the very lines
the game most wants in a suspect's own voice.

### 14.6 The correction: we were rejecting the honest model

§14.2 and §14.5 concluded that gemma4 and qwen "omit `source_claim_ids`", that
Layer 7 is therefore a per-model capability, and that only `llama3.1:8b` could
drive it. Every acceptance rate quoted was real. The mechanism was invented,
and inspecting the raw model output reverses the conclusion.

**Nobody omits the field.** All three emit it. They differ in what they put in
it:

| Model | Answer rests on a prior claim | Answer rests on nothing |
|---|---|---|
| `gemma4:latest` | cites it correctly **4/4** | `[]` **4/4 — honest** |
| `llama3.1:8b` | cites it correctly 4/4 | cites **both** claims 4/4 — fabricated |
| `qwen2.5-coder:7b` | — | invents ids: `claim_clara_arrival` |

So gemma is the *most accurate* citer of the three. It cites when it drew on
something and declines when it did not. llama passed our check by citing
indiscriminately — naming every claim it was shown regardless of use. Its
"10/10" was never competence; it was reflexive over-citing satisfying a rule
that asks only *did you say something*, never *is it true*.

**The bug was ours.** `DialogueRewrite.source_claim_ids` was `List[str] = []`,
so a missing field and an explicit empty list arrived as the same value, and
§9.3 refused both. But its rationale — "silence is a model that reasoned across
the history and declined to say from where" — describes a model that *says
nothing about its sources*. It does not describe one that explicitly answers
"I drew on none of them", which is both an honest answer and the common case:
most rewrites restate a single grounded line and rest on no prior claim at all.
The prompt made it worse by instructing the model to *omit* the field when it
had nothing to cite, i.e. to produce exactly the shape that fails closed.

The fix is `Optional[List[str]] = None`: absent stays refused, `[]` is allowed,
and the prompt now asks for `[]` explicitly. Allowing `[]` is only safe because
check 4b reads the finished prose independently, so a model that combines two
claims without declaring it is still caught on its words rather than its
silence — pinned by a test that would otherwise let an undeclared combination
through.

**Measured after the fix**, with reasoning suppression on, case_001:

| Model | Median | Timeline | Layer 7 cites | Danger pair refused |
|---|---|---|---|---|
| `gemma4:latest` | 1.5s | 9/9 | **4/4** | **4/4** |
| `qwen2.5-coder:7b` | 1.0s | 9/9 | 3/4 | 3/4 |
| `llama3.1:8b` | 1.1s | 9/9 | 0/4 | 3/4 |

gemma4 now leads every axis, and the danger guard is intact under it: pushed
adversarially to combine its own two recorded claims, it cites both and is
refused 3/3 with the motive reason. **Layer 7 and faithful dialogue are not
mutually exclusive after all** — that conclusion was an artifact of this bug.

The lesson worth keeping is not about models. Four axes were measured
carefully, and the one number nobody checked — what the model literally wrote
in the field — was the one that mattered. A guard's verdict is evidence about
the guard, not about the thing being guarded.
