"""A bare pronoun follow-up ("when did you last see them?") previously
always defaulted to the victim, even right after the player named a
different suspect by name in the same conversation — the harness's own
last_seen_follow_up question hit this on 49 of 78 total findings. Fixing it
required two things: classify_question needs the asking suspect's own
conversation history (via agent_id), and that history has to actually be
recorded — a canned fallback previously never touched the transcript at all.

The same conversation-aware disambiguation also covers a leading question
like "you two didn't get along, did you?" — an implicit dual-subject
reference with no explicit name/pronoun at all, which previously fell all
the way through to the small-talk "general_relationships" catch-all.
"""

from app.case_store import get_case
from app.free_text_api import handle_free_text
from app.models import FreeTextAskRequest
from app.question_classifier import classify_question
from app.session import Session


def test_bare_pronoun_defaults_to_victim_with_no_prior_context():
    case = get_case("case_001")
    sess = Session("test_pronoun_no_context")
    intent = classify_question("When did you last see them?", case, sess, agent_id="agent_clara")
    assert intent is not None
    assert intent.intent == "last_seen_victim"


def test_bare_pronoun_does_not_default_to_victim_after_naming_someone_else():
    case = get_case("case_001")
    sess = Session("test_pronoun_with_context")
    agent_id = "agent_clara"

    # Player asks about a named non-victim suspect first.
    handle_free_text(FreeTextAskRequest(agent_id=agent_id, question="When did you last see Ben?"), case, sess)

    intent = classify_question(
        "That wasn't the question — when did you last see them?", case, sess, agent_id=agent_id
    )
    assert intent is None or intent.intent != "last_seen_victim"


def test_explicit_victim_reference_still_wins_regardless_of_prior_context():
    case = get_case("case_001")
    sess = Session("test_pronoun_explicit_still_wins")
    agent_id = "agent_clara"

    handle_free_text(FreeTextAskRequest(agent_id=agent_id, question="When did you last see Ben?"), case, sess)

    # Naming the victim explicitly must still resolve to last_seen_victim
    # even though a different agent was the most recent subject.
    intent = classify_question("When did you last see the victim?", case, sess, agent_id=agent_id)
    assert intent is not None
    assert intent.intent == "last_seen_victim"


def test_leading_dual_subject_question_defaults_to_victim_with_no_prior_context():
    case = get_case("case_001")
    sess = Session("test_leading_no_context")
    intent = classify_question(
        "You two didn't exactly get along, did you?", case, sess, agent_id="agent_clara"
    )
    assert intent is not None
    assert intent.intent == "relationship"


def test_leading_dual_subject_question_does_not_default_after_naming_someone_else():
    case = get_case("case_001")
    sess = Session("test_leading_with_context")
    agent_id = "agent_clara"

    handle_free_text(FreeTextAskRequest(agent_id=agent_id, question="When did you last see Ben?"), case, sess)

    intent = classify_question(
        "You two didn't exactly get along, did you?", case, sess, agent_id=agent_id
    )
    assert intent is None or intent.intent != "relationship"


def test_canned_fallback_now_gets_recorded_to_transcript():
    case = get_case("case_001")
    sess = Session("test_fallback_transcript")
    agent_id = "agent_clara"

    before = len(sess.transcript_for(agent_id).messages)
    handle_free_text(
        FreeTextAskRequest(agent_id=agent_id, question="What is the meaning of life?"), case, sess
    )
    after = sess.transcript_for(agent_id).messages
    assert len(after) == before + 2
    assert after[-2].speaker == "player"
    assert after[-1].speaker == "agent"
