# No One Saw Everything — Final Showrunner Review
### Synthesis pass 2 — full re-review across all six cases
*Supersedes the post-remediation synthesis of 14 Jul. That pass reported the structural repairs (leaks, third acts, validator gating). This pass re-runs the full six-specialist review against the current build, folds in the interrogation-experience layer added since, and names the one systemic defect that survived remediation.*

---

## EXECUTIVE SUMMARY

The pack entered the previous cycle with one shippable case and five that could not ship. It now has
**six cases that pass `validate_case()` with zero errors, each with a confession, an aftermath, and
a fair path to the killer** — and a re-review that confirms the repairs held. Two cases (001, 005)
carry zero validator warnings; the rest carry only minor advisory warnings.

Three things are now true that were not true at the last synthesis:

1. **The interrogation actually plays the way the title promises.** Since the last pass, the game
   gained *testimony-as-evidence* — one villager's placed statement can now be used to break
   another's alibi — plus a live *composure meter*, *session persistence*, and a *confrontation
   builder*. "No one saw everything" is now a mechanic, not just a tagline.

2. **Every case has a third act that lands.** I re-read all six confessions and all forty-plus
   epilogues in the current data. They are not filler. Case 004's "He laughed," case 006's "I was not
   anything," case 003's refusal to be sorry, and case 001's "Like I was arithmetic" are, line for
   line, the strongest writing in the project.

3. **The re-review found one recurring defect the remediation pass missed.** Three cases contain a
   suspect the player can *question* but cannot *investigate*: they have no rewind presence at all.
   Dr Haig (003), Priya (004), and Elias + Nadia (006) are named in interviews and epilogues but
   appear in no timeline events, so a player who suspects them and goes looking on the map finds
   nothing. The validator flags each as an "empty-rewind suspect." This is the pack's top remaining
   fix, and it is the same shape in three places, which means it belongs in the generator, not just
   the cases.

**Verdict: six shippable cases, two of them Excellent. Recommend release, with the empty-rewind
suspects flagged as the first post-launch patch.**

---

## THE PACK, RE-SCORED

| Case | Title | Pass-1 | Now | Decision |
|---|---|---|---|---|
| 001 | The Storage Room Murder | 8.0 | **8.5** | **Excellent** — release |
| 005 | The Rear Alley Fire | 3.0 (Reject) | **8.8** | **Excellent** — release |
| 002 | The Locked Bookshop | 5.0 | **8.0** | **Good** — release |
| 004 | The Fountain at Midnight | 3.5 | **8.0** | **Good/Excellent** — release |
| 003 | The Clinic After Hours | 6.5 | **7.5** | **Good** — release |
| 006 | The Bell Estate | 5.5 | **7.5** | **Good** — release |

The two biggest movers remain **004 (+4.5)** and **005 (+5.8)** — both were strong material trapped
in broken containers (004 leaked its solution on the Suspects screen; 005 was a one-suspect
formality with the killer's traits listed as "capable of violence"). Case 005, rebuilt around a
letter the killer burned that would have saved him, is now arguably the pack's emotional peak.

---

## WHAT HELD (verified this pass, in the current data)

- **No leaks.** A scan of every `routine_summary` for motive/identity/alibi language returns
  nothing; all three cases that once printed their solution on the roster (004, 005, 006) are clean,
  guarded by `validator.py` check 14 and `test_routine_summary_no_leak.py`.
- **Third acts everywhere.** Every killer has a reachable `contradiction_locked` confession
  (case 005 has four); every `solution.epilogues` is populated.
- **The confession-shadowing bug stays fixed.** `challenge._find_rule` still ranks by specificity
  and severity, so bringing more evidence cannot yield a weaker response
  (`test_challenge_rule_specificity.py`).
- **Objective content fixes are in place:** case 001's "last week/tomorrow/this morning" deadline is
  now coherent; case 002's misleading invoice clue is re-pointed; case 004's inverted debt is
  corrected; case 006's "always known" contradiction is gone.
- **Test status:** 279 of 281 backend tests pass. The two failures
  (`test_portraits.py::test_project_agent_round_trips_portrait_art`,
  `test_dev_map_editor.py::test_tile_art_variants_listing`) are **not** case-logic failures — they
  are stale assertions against in-progress portrait/town-art infrastructure in the working tree
  (`PortraitState` gained a `deceased` field; a B2 tile was reorganised). They should be updated by
  whoever owns that art work; they do not gate the mystery content.

*(This pass also closed two residual time-of-day artifacts in case 003 — Nadia opening "for the
early shift" and Clara "opening the cafe" at 17:30 in a 16:00–18:00 case — that the last pass marked
done but had not fully cleared.)*

---

## THE ONE THING THE REMEDIATION PASS MISSED

**Empty-rewind suspects.** The last synthesis reported that cases 003 and 006 had "gained" red
herrings (Dr Haig, Nadia) and that case 004 had a false-alibi provider (Priya). All true on paper.
But the re-review drove the question the last pass did not: *can the player actually investigate
them?* The answer is no — none of these four appear in their case's `events.json`, so:

| Case | Suspect | Role the case gives them | What the player finds on the map |
|---|---|---|---|
| 003 | Dr Haig | Second medical suspect; signs off Nadia's dispensing | Nothing — no events |
| 004 | Priya | Provides Ben's false alibi | Nothing — no events |
| 006 | Elias | "Remembered a Bell girl" — key to the twist | One passing mention, no placed presence |
| 006 | Nadia | Named the poison unprompted | Nothing — no events |

A suspect you can question but cannot place is a dead end dressed as a lead. This is the single most
common note across the individual re-reviews (the Detective, the First-Time Player, and the Village
Simulator all raised it independently in three separate cases), and because it recurs identically it
is a **pipeline** issue: the generator and templates should guarantee every named suspect has at
least one placed rewind event. Fixing it lifts 003, 004, and 006 by roughly a point each.

---

## THE EXPERIENCE LAYER (new since last synthesis)

The last pass was about content. This build also improved the *play*:

- **Testimony-as-evidence** (`testimony.py`) — a claim can now carry `about_agent_id` and
  `asserts_presence`, so Ben's sighting can break Clara's fountain alibi as a *witness statement*,
  not merely as a physical clue. The detector is deliberately conservative (bilocation within a tight
  tolerance, denials over a wider window) because "a detector that cries wolf is worse than none."
  This is the mechanic the title has always promised, finally wired to the board.
- **Composure meter** — a live emotional read on the suspect that drains under pressure and
  distinguishes "holding a contradiction" from "caught in one." Gives spectators a visible tell.
- **Session persistence** — investigations now survive leaving and returning, per case.
- **Confrontation builder** — the player assembles the evidence bundle for a challenge deliberately
  rather than firing single clues.

None of these are case-specific; all of them raise every case's interrogation floor, which is why the
Player proxy's scores rose across the board even in cases whose *puzzles* were unchanged.

---

## QUALITY DASHBOARD — PACK LEVEL

| Category | Pack score | Note |
|---|---|---|
| Logical Fairness | 8/10 | All six pass the validator; empty-rewind suspects are the one soft spot. |
| Narrative Structure | 8/10 | Every case now has a real third act. |
| Character Depth | 8/10 | Killers are individuated; a few functional witnesses remain. |
| Dialogue | 9/10 | The confessions are the project's peak. |
| World Building | 8/10 | Distinct registers — morning cafe, night fountain, after-hours clinic. |
| Village Realism | 8/10 | Background NPCs are de-templated and opinionated. |
| Player Agency | 8/10 | Testimony + confrontation builder give real leverage; off-map suspects cost a point. |
| Fair Play | 8/10 | Discoverable and sufficient; means legs thin in 002/004. |
| Replayability | 5/10 | The pack's structural ceiling — solved is solved. |
| Entertainment | 8/10 | Two Excellents, four solid Goods. |
| Originality | 8/10 | The institutional motive (003) and the hidden sibling (006) lead. |
| Emotional Impact | 9/10 | 001, 004, 005, 006 all land a genuine gut-punch. |
| Spectator/Streaming | 8/10 | Confessions clip; composure meter gives chat a tell. |
| Production Readiness | 8/10 | Shippable; empty-rewind fix is the priority patch. |
| **Overall Pack Quality** | **8/10** | From one shippable case to six, two of them Excellent. |

---

## WHAT I DID NOT CHANGE (open decisions and accepted debt)

1. **Cross-case continuity.** The six cases reuse a repertory cast in mutually exclusive stories
   (Marcus dies in 001 and 006; Elias is victim in 003 and detective-adjacent elsewhere). Per your
   direction, this is an **anthology** — order-independent, continuity deliberately not enforced. Not
   a defect under that reading; noted as your standing decision.
2. **Empty-rewind suspects (003/004/006).** Named above as the top remaining fix; left for a patch
   because none of the three cases is *unfair* without it (the real killer is fully clued) — it costs
   a lead, not a solution.
3. **Case 006's wide murder window.** Retained by design: a slow-acting foxglove poisoning's
   meaningful window is access to the cocoa (Ruth's key + 18:30 visit), not a time-of-death minute.
   Narrowing it would be false precision.
4. **Thin means legs in 002 and 004.** Both `conc_method` legs rest on one or two clues (validator
   advisory). A polish item, not a blocker.
5. **Ben/Priya's small secret in case 001** — still not a proportionate reason to obstruct a murder
   inquiry. The one soft spot in the flagship.

---

## IMPROVEMENT ROADMAP — PACK LEVEL

| Priority | Change | Cases | Impact |
|---|---|---|---|
| **P1** | Give every named suspect ≥1 placed rewind event (fix in generator + templates too) | 003, 004, 006 | High — closes the top systemic gap |
| **P1** | Corroborate thin means legs with one more clue each | 002, 004 | Medium |
| P2 | Update the two stale art-infra tests | (engine) | Low — restores green suite |
| P2 | Raise the Ben/Priya stake | 001 | Low |
| P2 | Second red herrings / early murder-nudges | 003, 006 | Medium |

---

## EXECUTIVE DECISION

### **Good, with two Excellents — release.**

**Would I fund this?** Yes. It was worth funding a cycle ago; it is worth shipping now.

**Would I release it today?** Yes — every case is complete, fair, and validator-clean, which was true
of one of six two cycles ago.

**Would I delay it?** No. Ship, then patch the empty-rewind suspects and update the two art-infra
tests.

**Three highest-ROI improvements before or just after launch:** (1) give every suspect a place on the
timeline — one fix, three cases, and it belongs in the generator; (2) corroborate the thin means legs
in 002 and 004; (3) restore the fully green test suite by updating the stale portrait/tile assertions.

**Would players remember this?**

Yes — and for the same reason across the pack. Every one of these cases now has the moment where a
person finally says the true thing out loud, and the moment after where the village has to live with
it. A nurse who watched a man swallow his pills in a sunny square and thought the village owed her.
A postwoman thanked at a door for thirty-one years by the wrong name. A man who killed for a laugh he
couldn't take back, and pleaded guilty rather than explain it. The mechanics were always competent;
what the pack was missing was a reason to care who did it — and, now, a way to prove it using nothing
but what one neighbour saw of another. That is the difference between a puzzle and a mystery, and all
six cases are on the far side of it.
