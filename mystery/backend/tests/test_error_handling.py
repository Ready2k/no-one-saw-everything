"""No endpoint may 500 on bad player input.

Every route is fired at with the kind of garbage a real client can produce —
unknown ids, malformed times, traversal attempts, out-of-scope targets — and
must answer with a 4xx whose detail reads like the game world (or at worst a
validation error), never a stack trace.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

BAD = "zzz_does_not_exist"

CASES = [
    # (method, path, json_body, expected_status_range)
    ("GET", "/api/events?time_from=bogus", None, (400, 400)),
    ("GET", "/api/events?time_to=25:9x", None, (400, 400)),
    ("GET", f"/api/events?agent_id={BAD}", None, (200, 200)),  # empty list, not an error
    ("GET", "/api/map/replay?start=breakfast", None, (400, 400)),
    ("GET", "/api/map/replay?mode=cheat", None, (400, 400)),
    ("POST", f"/api/events/{BAD}/pin", None, (404, 404)),
    ("POST", "/api/inspect", {"location_id": BAD}, (404, 404)),
    ("POST", "/api/inspect", {"location_id": ""}, (400, 400)),
    ("POST", "/api/discover_clue", {"clue_id": BAD}, (404, 404)),
    # Prerequisite-gated clue with prereqs undiscovered: refused, diegetically.
    ("POST", "/api/discover_clue", {"clue_id": "clue_till_weight_found"}, (409, 409)),
    ("GET", "/api/examine_body/agent_clara", None, (400, 400)),
    ("GET", f"/api/examine_body/{BAD}", None, (400, 404)),
    ("POST", "/api/interview/ask", {"agent_id": BAD, "question_type": "alibi"}, (404, 404)),
    (
        "POST",
        "/api/interview/ask",
        {"agent_id": "agent_clara", "question_type": "timeline", "time_reference": "breakfast"},
        (400, 400),
    ),
    ("POST", "/api/interview/free-text", {"agent_id": BAD, "question": "hello"}, (404, 404)),
    # Background NPCs are not part of the investigation, in free text either.
    ("POST", "/api/interview/free-text", {"agent_id": "agent_rosa", "question": "hello"}, (400, 400)),
    ("POST", "/api/interview/observe", {"agent_id": BAD}, (404, 404)),
    ("GET", f"/api/interview/{BAD}", None, (404, 404)),
    ("GET", f"/api/interview/{BAD}/observations", None, (404, 404)),
    (
        "POST",
        "/api/challenge",
        {"target_agent_id": BAD, "challenged_claim_id": BAD, "evidence_clue_ids": [BAD]},
        (400, 404),
    ),
    ("POST", "/api/suspicion", {"agent_id": BAD, "level": "prime_suspect"}, (404, 404)),
    ("POST", "/api/suspicion", {"agent_id": "agent_rosa", "level": "prime_suspect"}, (400, 400)),
    # The victim cannot be a suspect.
    ("POST", "/api/suspicion", {"agent_id": "agent_marcus", "level": "prime_suspect"}, (400, 400)),
    ("POST", "/api/session/markers", {"element_id": "", "marker": "important", "action": "add"}, (400, 400)),
    ("POST", "/api/session/markers", {"element_id": "x" * 500, "marker": "important", "action": "add"}, (400, 400)),
    ("PATCH", f"/api/notes/{BAD}", {"title": "x"}, (404, 404)),
    ("DELETE", f"/api/notes/{BAD}", None, (404, 404)),
    ("POST", "/api/accuse", {"accused_agent_id": BAD}, (400, 400)),
    ("POST", "/api/accuse", {"accused_agent_id": "agent_rosa"}, (400, 400)),
    ("POST", "/api/cases/activate", {"case_id": "../evil"}, (404, 404)),
    ("POST", "/api/cases/activate", {"case_id": BAD}, (404, 404)),
    ("POST", "/api/cases/generate", {"case_type": "no_such_theme"}, (400, 400)),
    ("POST", "/api/cases/generate", {"case_type": "../../etc"}, (400, 400)),
    ("GET", f"/api/generated_cases/{BAD}", None, (404, 404)),
    ("DELETE", f"/api/generated_cases/{BAD}", None, (400, 400)),
    ("POST", f"/api/generated_cases/{BAD}/activate", None, (404, 404)),
    ("POST", f"/api/generated_cases/{BAD}/regenerate", None, (404, 404)),
    ("DELETE", f"/api/session/investigations/{BAD}", None, (404, 404)),
]


@pytest.mark.parametrize(
    "method,path,body,expected", CASES, ids=[f"{c[0]} {c[1][:60]}" for c in CASES]
)
def test_bad_input_never_500s(method, path, body, expected):
    r = client.request(method, path, json=body)
    lo, hi = expected
    assert lo <= r.status_code <= hi, (
        f"{method} {path} -> {r.status_code}, expected {lo}..{hi}: {r.text[:300]}"
    )


def test_every_4xx_detail_is_presentable():
    """Details shown to the player must be strings, not stack traces or objects."""
    for method, path, body, (lo, hi) in CASES:
        r = client.request(method, path, json=body)
        if 400 <= r.status_code < 500:
            detail = r.json().get("detail")
            assert detail, f"{method} {path}: 4xx with no detail"
            text = detail if isinstance(detail, str) else str(detail)
            assert "Traceback" not in text and "Exception" not in text
