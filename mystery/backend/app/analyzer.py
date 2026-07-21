"""Analyzes the player's session against the case truth to provide player-safe readiness hints."""

from __future__ import annotations

from .models import CaseData
from .session import Session


def analyze_session(session: Session, case: CaseData) -> list[str]:
    """
    Returns a list of player-safe readiness hints based on the current session state.
    It uses the locked truth to know what categories of evidence exist, but never
    leaks the truth directly.
    """
    hints = []

    # 1. Disputed alibis
    disputed_alibis = [
        c for c in session.claims.values()
        if c.claim_type == "alibi" and c.player_known_status == "disputed"
    ]
    if disputed_alibis:
        hints.append("You have a disputed alibi.")

    # 2. Method evidence
    # Find all clues that support the method conclusion
    method_conclusions = [c for c in case.conclusions if c.type == "method"]
    found_method = False
    if method_conclusions:
        method_clue_ids = {clue_id for conc in method_conclusions for clue_id in conc.supported_by_clue_ids}
        if any(clue_id in session.discovered_clue_ids for clue_id in method_clue_ids):
            found_method = True
            hints.append("You have found possible method evidence.")

    # 3. Motive and Opportunity
    motive_conclusions = [c for c in case.conclusions if c.type == "motive"]
    opportunity_conclusions = [c for c in case.conclusions if c.type == "opportunity"]
    
    motive_clue_ids = {clue_id for conc in motive_conclusions for clue_id in conc.supported_by_clue_ids}
    opportunity_clue_ids = {clue_id for conc in opportunity_conclusions for clue_id in conc.supported_by_clue_ids}

    found_motive = any(clue_id in session.discovered_clue_ids for clue_id in motive_clue_ids)
    found_opportunity = any(clue_id in session.discovered_clue_ids for clue_id in opportunity_clue_ids)

    if found_motive and not found_opportunity:
        hints.append("You have motive evidence, but it is not yet tied to opportunity.")
    elif found_opportunity and not found_motive:
        hints.append("You have established opportunity, but lack a clear motive.")
    elif found_motive and found_opportunity:
        hints.append("You have gathered both motive and opportunity evidence.")

    # 4. Red Herrings Unexplained
    # A red herring is explained if the player has discovered evidence for its innocence anchor.
    red_herrings = [c for c in case.conclusions if c.type == "red_herring"]
    anchors = {c.target_agent_id: c for c in case.conclusions if c.type == "innocence_anchor"}
    
    unexplained_count = 0
    for rh in red_herrings:
        agent = rh.target_agent_id
        anchor = anchors.get(agent)
        if anchor:
            # Has the player discovered any clue supporting this anchor?
            found_anchor = any(clue_id in session.discovered_clue_ids for clue_id in anchor.supported_by_clue_ids)
            if not found_anchor:
                unexplained_count += 1
                
    if unexplained_count == 1:
        hints.append("One red herring remains unexplained.")
    elif unexplained_count > 1:
        hints.append(f"Multiple ({unexplained_count}) red herrings remain unexplained.")

    # 5. Accusation readiness: every solution-critical conclusion has at least
    # one discovered supporting clue and no red herring is left unexplained.
    # This is the in-fiction "you now hold enough" signal — it reads the shape
    # of the case file, never the truth itself.
    required = [c for c in case.conclusions if c.required_for_solution]
    if (
        required
        and unexplained_count == 0
        and all(
            any(cid in session.discovered_clue_ids for cid in conc.supported_by_clue_ids)
            for conc in required
        )
    ):
        hints.append(
            "Your case file now covers motive, means, and opportunity, and every "
            "suspicious lead has an explanation. When you believe your own notes, "
            "make the accusation."
        )

    return hints
