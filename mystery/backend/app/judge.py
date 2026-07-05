"""Accusation judge (Phase 6).

Deterministic scoring of the player's final accusation against the locked
case file and clue graph. No LLM: free-text motive/method/opportunity answers
are graded by concept-keyword matching defined in the case's solution config.

The truth reveal is assembled here and is the ONLY place hidden truth is
exposed to the player — and only after an accusation has been submitted.
"""

from __future__ import annotations

from .models import (
    AccusationRequest,
    AccusationResult,
    CaseData,
    RedHerringExplanation,
    SolutionCriterion,
    TimelineEntry,
    EpilogueCard,
)
from .session import Session
from .case_store import minutes


def _criterion_correct(criterion: SolutionCriterion, answer: str) -> bool:
    text = answer.lower()
    matched_groups = 0
    for group in criterion.concept_groups:
        if any(syn.lower() in text for syn in group):
            matched_groups += 1
    return matched_groups >= criterion.min_groups


def _evidence_score(
    case: CaseData, session: Session, valid_clue_ids: set[str]
) -> float:
    """Fraction of the solution-critical conclusions that the player's cited,
    discovered evidence actually supports."""
    required = [c for c in case.conclusions if c.required_for_solution]
    if not required:
        return 0.0
    covered = 0
    for conc in required:
        if set(conc.supported_by_clue_ids) & valid_clue_ids:
            covered += 1
    return covered / len(required)


def _verdict_band(score: int) -> str:
    if score >= 90:
        return "Case closed — a clean solve."
    if score >= 70:
        return "Right killer, but your reasoning had gaps."
    if score >= 50:
        return "Partly there, but you missed major pieces."
    if score >= 20:
        return "Wrong suspect, though you found some real threads."
    return "An accusation the evidence doesn't support."


def _detective_rating(score: int) -> str:
    if score >= 95: return "S"
    if score >= 85: return "A"
    if score >= 70: return "B"
    if score >= 50: return "C"
    if score >= 30: return "D"
    return "F"


def _true_timeline(case: CaseData) -> list[TimelineEntry]:
    loc_name = {l.location_id: l.name for l in case.locations}
    entries = [
        TimelineEntry(
            time=e.time,
            description=e.truth_description,
            location_name=loc_name.get(e.location_id, e.location_id),
        )
        for e in case.events
    ]
    entries.sort(key=lambda e: minutes(e.time))
    return entries


def _red_herring_explanations(case: CaseData) -> list[RedHerringExplanation]:
    name = {a.agent_id: a.full_name for a in case.agents}
    anchors = {
        c.target_agent_id: c.summary
        for c in case.conclusions
        if c.type == "innocence_anchor"
    }
    out = []
    for conc in case.conclusions:
        if conc.type != "red_herring" or not conc.target_agent_id:
            continue
        out.append(
            RedHerringExplanation(
                agent_id=conc.target_agent_id,
                agent_name=name.get(conc.target_agent_id, conc.target_agent_id),
                looked_suspicious_because=conc.summary,
                actually_innocent_because=anchors.get(
                    conc.target_agent_id, "No proof ever connected them to the murder."
                ),
            )
        )
    return out


def _epilogue_cards(case: CaseData) -> list[EpilogueCard]:
    if not case.solution.epilogues:
        return []
    
    name = {a.agent_id: a.full_name for a in case.agents}
    out = []
    for agent_id, text in case.solution.epilogues.items():
        if not text.strip():
            continue
        out.append(
            EpilogueCard(
                agent_id=agent_id,
                agent_name=name.get(agent_id, agent_id),
                text=text.strip(),
            )
        )
    return out


def judge_accusation(
    case: CaseData, session: Session, req: AccusationRequest
) -> AccusationResult:
    sol = case.solution
    clue_by_id = {c.clue_id: c for c in case.clues}

    # Split cited evidence into valid (discovered) and invalid (not discovered).
    valid_clue_ids: set[str] = set()
    player_evidence_used: list[str] = []
    false_assumptions: list[str] = []
    for clue_id in req.supporting_clue_ids:
        if clue_id not in clue_by_id:
            false_assumptions.append(f"Cited unknown evidence '{clue_id}'.")
        elif clue_id not in session.discovered_clue_ids:
            false_assumptions.append(
                f"Cited evidence you never discovered: {clue_by_id[clue_id].title}."
            )
        else:
            valid_clue_ids.add(clue_id)
            player_evidence_used.append(clue_by_id[clue_id].title)

    killer_correct = req.accused_agent_id == sol.killer_id
    motive_correct = _criterion_correct(sol.motive, req.motive_answer)
    method_correct = _criterion_correct(sol.method, req.method_answer)
    opportunity_correct = _criterion_correct(sol.opportunity, req.opportunity_answer)
    evidence_score = _evidence_score(case, session, valid_clue_ids)

    invalid_penalty = min(12, 4 * len(false_assumptions))

    if killer_correct:
        score = 45
        score += 12 if motive_correct else 0
        score += 8 if method_correct else 0
        score += 12 if opportunity_correct else 0
        score += round(evidence_score * 23)
    else:
        mechanics = motive_correct + method_correct + opportunity_correct
        score = round(evidence_score * 20) + mechanics * 5
        score = min(score, 49)
        false_assumptions.insert(
            0,
            f"You named {_name(case, req.accused_agent_id)}, but the evidence points elsewhere.",
        )

    score = max(0, min(100, score - invalid_penalty))

    # Key-clue reasoning gaps and discovery gaps.
    key_ids = sol.key_clue_ids
    missed_key_clues = [
        clue_by_id[k].title for k in key_ids if k in clue_by_id and k not in valid_clue_ids
    ]
    key_clues_found = [
        clue_by_id[k].title
        for k in key_ids
        if k in clue_by_id and k in session.discovered_clue_ids
    ]
    key_clues_missed = [
        clue_by_id[k].title
        for k in key_ids
        if k in clue_by_id and k not in session.discovered_clue_ids
    ]

    if killer_correct:
        explanation = sol.explanation
    else:
        explanation = (
            f"Incorrect. You accused {_name(case, req.accused_agent_id)}, "
            f"but the evidence points elsewhere. Your theories on motive, method, and opportunity have been evaluated."
        )

    result = AccusationResult(
        accusation_id="accuse_001",
        case_id=case.case.case_id,
        accused_agent_id=req.accused_agent_id,
        accused_name=_name(case, req.accused_agent_id),
        score=score,
        killer_correct=killer_correct,
        motive_correct=motive_correct,
        method_correct=method_correct,
        opportunity_correct=opportunity_correct,
        evidence_score=round(evidence_score, 2),
        missed_key_clues=missed_key_clues,
        false_assumptions=false_assumptions,
        explanation=explanation,
        verdict=_verdict_band(score),
        true_killer_id=sol.killer_id if killer_correct else "",
        true_killer_name=_name(case, sol.killer_id) if killer_correct else "",
        true_motive=sol.motive.canonical if killer_correct else "",
        true_method=sol.method.canonical if killer_correct else "",
        true_timeline=_true_timeline(case) if killer_correct else [],
        key_clues_found=key_clues_found,
        key_clues_missed=key_clues_missed,
        red_herring_explanations=_red_herring_explanations(case) if killer_correct else [],
        epilogues=_epilogue_cards(case) if killer_correct else [],
        player_evidence_used=player_evidence_used,
        detective_rating=_detective_rating(score),
    )
    session.accusation = result
    return result


def _name(case: CaseData, agent_id: str) -> str:
    return next((a.full_name for a in case.agents if a.agent_id == agent_id), agent_id)
