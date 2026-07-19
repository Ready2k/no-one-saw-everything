"""Every case must have a third act that reads correctly at the API.

Played to accusation via the API for all seven shipped cases, on both paths:

- WIN: naming the killer must never read as a loss (score floors at 45, verdict
  is a right-killer band), and the reveal must actually contain the third act —
  explanation, true timeline, and non-empty epilogues (five of six cases once
  shipped with a blank reveal screen).
- LOSS: the verdict must read as a wrong accusation, and — critically — the
  reveal must NOT hand over the truth: no killer id, no true timeline, no
  epilogues. A failed accusation is not a free solution.
"""

import pytest
from fastapi.testclient import TestClient

from app.case_store import get_case
from app.main import app

client = TestClient(app)

CASE_IDS = ["case_001", "case_002", "case_003", "case_004", "case_005", "case_006", "case_007"]

WIN_VERDICTS = {
    "Case closed — a clean solve.",
    "Right killer, but your reasoning had gaps.",
    "Partly there, but you missed major pieces.",
    "The right name, but you cannot yet show your working.",
}
LOSS_VERDICTS = {
    "Wrong suspect, though you found some real threads.",
    "An accusation the evidence doesn't support.",
}


def _activate(case_id: str):
    r = client.post("/api/cases/activate", json={"case_id": case_id, "restart": True})
    assert r.status_code == 200, r.text


def _innocent_suspect(case) -> str:
    return next(
        a.agent_id
        for a in case.agents
        if not a.is_victim and not a.is_background and a.agent_id != case.solution.killer_id
    )


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_win_path_reveal_reads_correctly(case_id):
    case = get_case(case_id)
    _activate(case_id)

    r = client.post("/api/accuse", json={"accused_agent_id": case.solution.killer_id})
    assert r.status_code == 200, r.text
    result = r.json()

    assert result["killer_correct"] is True
    assert result["score"] >= 45, "a correct accusation must floor at 45"
    assert result["verdict"] in WIN_VERDICTS, f"win verdict reads wrong: {result['verdict']}"
    assert result["detective_rating"] in {"S", "A", "B", "C", "D"}

    reveal = client.get("/api/reveal")
    assert reveal.status_code == 200
    body = reveal.json()
    assert body["explanation"].strip(), f"{case_id}: empty explanation on the win path"
    assert body["true_timeline"], f"{case_id}: empty true timeline on the win path"
    assert body["epilogues"], f"{case_id}: no epilogue cards — the reveal screen ends blank"
    assert body["true_killer_id"] == case.solution.killer_id
    # Every epilogue names a real character and says something.
    for card in body["epilogues"]:
        assert card["agent_name"].strip() and card["text"].strip()


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_loss_path_reads_as_loss_and_leaks_nothing(case_id):
    case = get_case(case_id)
    _activate(case_id)

    accused = _innocent_suspect(case)
    r = client.post("/api/accuse", json={"accused_agent_id": accused})
    assert r.status_code == 200, r.text
    result = r.json()

    assert result["killer_correct"] is False
    assert result["score"] <= 49, "a wrong accusation must never outscore a right one"
    assert result["verdict"] in LOSS_VERDICTS, f"loss verdict reads wrong: {result['verdict']}"

    reveal = client.get("/api/reveal").json()
    # The truth stays sealed on a loss.
    assert reveal["true_killer_id"] == ""
    assert reveal["true_killer_name"] == ""
    assert reveal["true_timeline"] == []
    assert reveal["epilogues"] == []
    assert reveal["red_herring_explanations"] == []
    killer_name = next(
        a.full_name for a in case.agents if a.agent_id == case.solution.killer_id
    )
    # The loss explanation must not name the killer.
    assert killer_name not in reveal["explanation"]
