"""Layer 6 tension detector (persona_chat_lab/ENGINE_SPEC.md §8), ported onto
the real claim/testimony machinery: a detective citing the exact times of two
of a suspect's OWN already-heard claims, at two different places, gets an
in-character acknowledgment of the gap between them — arithmetic on facts the
player already earned, not new information. It must defer to `find_conflict`
(the more serious, existing machinery behind the formal Challenge flow) for
anything that's a genuine impossibility rather than mere tight timing.

case_001's authored content has no naturally-occurring "true but suspiciously
tight" claim pair for any suspect (the only real cross-location pair with
`about_agent_id` set — Priya's stockroom/alley claims — is a genuine planted
lie, correctly caught by find_conflict, not tension: see
test_alibi_span_survives_through_the_real_interview_api in
test_testimony.py). So the "fires" case here injects two claims directly,
same as test_testimony.py's own `_claim()` helper does for find_conflict; the
"correctly does not fire" case uses real, authored case_001 data.
"""

from app.free_text_api import handle_free_text
from app.main import case_data, session
from app.models import Claim, FreeTextAskRequest


def _inject_self_claim(sess, claim_id, time_ref, loc, agent_id, text):
    claim = Claim(
        claim_id=claim_id,
        speaker_agent_id=agent_id,
        claim_text=text,
        time_reference=time_ref,
        location_reference_id=loc,
        about_agent_id=agent_id,
        asserts_presence=True,
    )
    sess.record_claim(claim)
    return claim


def test_tension_fires_for_a_genuine_but_not_impossible_gap(reset_app_state):
    case = case_data()
    sess = session()
    _inject_self_claim(
        sess, "claim_test_square", "07:05", "loc_village_square", "agent_owen",
        "Owen says he argued with Marcus at the square at 07:05.",
    )
    _inject_self_claim(
        sess, "claim_test_yard", "07:15", "loc_owen_house", "agent_owen",
        "Owen says he was back in his yard by 07:15.",
    )

    resp = handle_free_text(
        FreeTextAskRequest(
            agent_id="agent_owen",
            question="You argued with him at 07:05. By 07:15 you were in your yard. That's a tight ten minutes, isn't it?",
        ),
        case,
        sess,
    )

    assert resp.answer is not None, "a genuine tension pair must not fall through to a plain deflection"
    det = resp.answer["deterministic_answer_text"]
    assert "argued with marcus at the square at 07:05" in det.lower()
    assert "back in his yard by 07:15" in det.lower()
    assert "10-minute gap" in det.lower()

    # Recorded like every other exchange, so it survives transcript review.
    transcript = sess.transcript_for("agent_owen").messages
    assert transcript[-1].deterministic_text == det


def test_tension_defers_to_a_genuine_contradiction(reset_app_state):
    """The one real cross-location, about_agent_id-tagged claim pair in
    case_001 (Priya's false stockroom alibi vs. her confessed alley
    presence) is an actual impossibility, not mere tight timing — the
    tension detector must not soften it into a casual acknowledgment."""
    case = case_data()
    sess = session()

    handle_free_text(
        FreeTextAskRequest(agent_id="agent_ben", question="What were you doing around 07:47?"),
        case, sess,
    )  # unlocks Priya's rear-alley rule prerequisite
    handle_free_text(
        FreeTextAskRequest(agent_id="agent_priya", question="Where were you during the murder window?"),
        case, sess,
    )
    handle_free_text(
        FreeTextAskRequest(agent_id="agent_priya", question="Tell me about the rear alley."),
        case, sess,
    )

    resp = handle_free_text(
        FreeTextAskRequest(
            agent_id="agent_priya",
            question="You were in the stockroom at 07:00, but in the alley at 07:47 — explain that.",
        ),
        case, sess,
    )

    # Must NOT be answered as soft "tension" — the answer_type marker this
    # detector sets is "tension"; a genuine conflict must take some other
    # path (normal classification / open-ended / fallback), never this one.
    if resp.answer is not None:
        assert resp.answer.get("answer_type") != "tension"
