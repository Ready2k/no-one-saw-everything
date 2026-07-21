from app.models import CaseData
from app.session import Session

def get_tutorial_hints(session: Session, case: CaseData) -> list[str]:
    """Returns safe tutorial hints based on the player's progress."""
    if getattr(session, 'tutorial_enabled', False) is False:
        return []

    hints = []
    
    # 1. Onboarding / Discovery
    if not session.discovered_clue_ids:
        hints.append("Try inspecting a location or rewinding the timeline to discover clues.")
    
    # 2. Interviews
    if not session.transcripts and session.discovered_clue_ids:
        hints.append("You have found some evidence. Try interviewing a suspect to see what they know.")
        
    # 3. Contradictions & Challenges
    has_disputed_alibi = any(c.player_known_status == "disputed" for c in session.claims.values())
    if has_disputed_alibi and not session.challenges:
        hints.append("You have a disputed claim! Use the 'Challenge' button in an interview to confront a suspect with evidence.")
        
    # 4. Markers
    if len(session.notes) > 0 and not getattr(session, 'case_board_markers', {}):
        hints.append("Use the case board to pin notes to your theory, or mark suspects as red herrings.")
        
    # 5. Accusation
    method_conclusions = [c for c in case.conclusions if c.type == "method"]
    found_method = False
    if method_conclusions:
        method_clue_ids = {clue_id for conc in method_conclusions for clue_id in conc.supported_by_clue_ids}
        if any(clue_id in session.discovered_clue_ids for clue_id in method_clue_ids):
            found_method = True
            
    if found_method and session.challenges and len(session.discovered_clue_ids) > 5:
        if session.accusation is None:
            hints.append("When you are ready, you can submit your final accusation.")
            
    return hints
