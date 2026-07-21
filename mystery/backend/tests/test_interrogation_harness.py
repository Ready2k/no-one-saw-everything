from app.interrogation_harness import detective_question_bank, run_interrogation_harness
from app.case_store import get_case


def test_question_bank_includes_the_reported_routing_regressions():
    case = get_case("case_005")
    questions = detective_question_bank(case, "agent_col")
    by_id = {question.id: question for question in questions}
    assert by_id["greeting_contains_grief"].disallowed_intents == ("greeting",)
    assert by_id["last_seen_named_person"].disallowed_intents == ("last_seen_victim",)
    assert by_id["relationship_with_victim"].required_clue_agent_id == "agent_clara"


def test_question_bank_has_both_good_cop_and_bad_cop_questions():
    case = get_case("case_005")
    questions = detective_question_bank(case, "agent_col")
    styles = {question.style for question in questions}
    assert "good_cop" in styles
    assert "bad_cop" in styles
    assert "neutral" in styles


def test_bad_cop_pressure_questions_must_not_be_softened_into_small_talk():
    case = get_case("case_005")
    by_id = {q.id: q for q in detective_question_bank(case, "agent_col")}
    for question_id in ("bad_cop_alibi_pressure", "bad_cop_motive_press", "bad_cop_one_word_motive"):
        question = by_id[question_id]
        assert question.style == "bad_cop"
        assert "greeting" in question.disallowed_intents
        assert question.reject_generic is True


def test_bad_cop_alibi_pressure_is_grounded_in_the_case_murder_window():
    case = get_case("case_005")
    by_id = {q.id: q for q in detective_question_bank(case, "agent_col")}
    start, end = case.case.murder_window
    assert start in by_id["bad_cop_alibi_pressure"].question
    assert end in by_id["bad_cop_alibi_pressure"].question


def test_object_pronoun_follow_up_must_not_reroute_to_the_victim():
    case = get_case("case_005")
    by_id = {q.id: q for q in detective_question_bank(case, "agent_col")}
    assert by_id["object_pronoun_follow_up"].disallowed_intents == ("last_seen_victim",)


def test_harness_runs_in_memory_and_returns_a_complete_report():
    report = run_interrogation_harness(["case_005"])
    assert report["mode"] == {"live_dialogue": False, "llm_critic": False}
    assert report["questions_asked"] > 0
    assert all(item["case_id"] == "case_005" for item in report["results"])
    assert all("findings" in item and "answer" in item for item in report["results"])
