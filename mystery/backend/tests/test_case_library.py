import tempfile
import shutil
from pathlib import Path
import importlib
import pytest

# Create isolated temp data directory
TEST_DATA_DIR = Path(tempfile.mkdtemp())

import app.case_store as cs

@pytest.fixture(autouse=True)
def restore_persistence(monkeypatch):
    importlib.reload(cs)
    monkeypatch.setattr(cs, "DATA_DIR", TEST_DATA_DIR)

from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.case_store import reset_case_store

client = TestClient(fastapi_app)

def setup_module(module):
    reset_case_store()

def teardown_module(module):
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)

def test_generated_cases_saved_and_activated_and_deleted():
    # 1. Generate a case (deterministic)
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic"
    })
    assert r.status_code == 200
    data = r.json()
    case_id = data["case_id"]
    
    # Verify metadata and quality score exist in generation_metadata
    assert data["generation_metadata"] is not None
    assert "quality_report" in data["generation_metadata"]
    assert "created_at" in data["generation_metadata"]

    # 2. Get list of generated cases
    r_list = client.get("/api/generated_cases")
    assert r_list.status_code == 200
    list_data = r_list.json()
    assert len(list_data) >= 1
    
    # Find our generated case in the library
    saved_case = next((c for c in list_data if c["case_id"] == case_id), None)
    assert saved_case is not None
    assert saved_case["case_type"] == "blackmail"
    assert saved_case["mode"] == "deterministic"
    assert saved_case["seed"] == 42
    assert saved_case["quality_score"] is not None
    assert saved_case["created_at"] is not None
    
    # 3. Fetch single case payload
    r_single = client.get(f"/api/generated_cases/{case_id}")
    assert r_single.status_code == 200
    single_data = r_single.json()
    assert single_data["case"]["case_id"] == case_id

    # 4. Activate the saved case
    r_act = client.post(f"/api/generated_cases/{case_id}/activate")
    assert r_act.status_code == 200
    assert r_act.json()["status"] == "success"
    assert r_act.json()["active_session_id"] == case_id

    # Verify activated_at is updated in the list
    r_list2 = client.get("/api/generated_cases")
    saved_case2 = next((c for c in r_list2.json() if c["case_id"] == case_id), None)
    assert saved_case2["activated_at"] is not None

    # 5. Delete the saved case
    r_del = client.delete(f"/api/generated_cases/{case_id}")
    assert r_del.status_code == 200
    assert r_del.json()["status"] == "deleted"

    # Verify removed from library
    r_list3 = client.get("/api/generated_cases")
    assert not any(c["case_id"] == case_id for c in r_list3.json())

def test_regenerate_from_same_recipe():
    # 1. Generate case
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 99,
        "mode": "deterministic"
    })
    assert r.status_code == 200
    data = r.json()
    case_id = data["case_id"]

    # 2. Regenerate
    r_regen = client.post(f"/api/generated_cases/{case_id}/regenerate")
    assert r_regen.status_code == 200
    regen_data = r_regen.json()
    assert regen_data["case_id"] != case_id
    assert regen_data["case_type"] == "blackmail"
    assert regen_data["generation_metadata"]["seed"] != 99
    
    # Cleanup
    client.delete(f"/api/generated_cases/{case_id}")
    client.delete(f"/api/generated_cases/{regen_data['case_id']}")

def test_sorting_and_filtering():
    # Generate case 1: standard tone
    r1 = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 101,
        "mode": "deterministic"
    })
    assert r1.status_code == 200
    cid1 = r1.json()["case_id"]

    from app.case_store import load_case_from_disk, save_case_to_disk
    
    case1 = load_case_from_disk(cid1)
    case1.metadata["tone"] = "standard"
    case1.metadata["fallback_used"] = False
    case1.metadata["quality_report"]["overall_score"] = 3.5
    save_case_to_disk(case1)

    # Generate case 2
    r2 = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 102,
        "mode": "deterministic"
    })
    assert r2.status_code == 200
    cid2 = r2.json()["case_id"]
    
    case2 = load_case_from_disk(cid2)
    case2.metadata["tone"] = "dark_noir"
    case2.metadata["fallback_used"] = True
    case2.metadata["quality_report"]["overall_score"] = 4.8
    save_case_to_disk(case2)

    # 1. Filter by tone=dark_noir
    r_filter = client.get("/api/generated_cases?tone=dark_noir")
    assert r_filter.status_code == 200
    results = r_filter.json()
    assert len(results) >= 1
    assert all(r["tone"] == "dark_noir" for r in results)

    # 2. Filter by fallback_used=true
    r_filter_fb = client.get("/api/generated_cases?fallback_used=true")
    assert r_filter_fb.status_code == 200
    results_fb = r_filter_fb.json()
    assert len(results_fb) >= 1
    assert all(r["fallback_used"] is True for r in results_fb)

    # 3. Sort by quality score (highest first)
    r_sort = client.get("/api/generated_cases?sort_by=quality_score")
    assert r_sort.status_code == 200
    sorted_results = r_sort.json()
    scores = [r["quality_score"] for r in sorted_results if r["quality_score"] is not None]
    assert scores == sorted(scores, reverse=True)

    # Cleanup
    client.delete(f"/api/generated_cases/{cid1}")
    client.delete(f"/api/generated_cases/{cid2}")

def test_load_case_with_missing_metadata():
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 201,
        "mode": "deterministic"
    })
    assert r.status_code == 200
    case_id = r.json()["case_id"]

    metadata_file = TEST_DATA_DIR / case_id / "metadata.json"
    if metadata_file.exists():
        metadata_file.unlink()

    from app.case_store import load_case_from_disk
    case_data = load_case_from_disk(case_id)
    assert case_data.metadata is not None
    assert case_data.metadata["load_status"] == "missing_metadata"
    assert case_data.metadata["mode"] == "deterministic"

    client.delete(f"/api/generated_cases/{case_id}")

def test_load_case_with_corrupted_metadata():
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 202,
        "mode": "deterministic"
    })
    assert r.status_code == 200
    case_id = r.json()["case_id"]

    metadata_file = TEST_DATA_DIR / case_id / "metadata.json"
    metadata_file.write_text("invalid json content {{{{")

    from app.case_store import load_case_from_disk
    case_data = load_case_from_disk(case_id)
    assert case_data.metadata is not None
    assert case_data.metadata["load_status"] == "corrupted_metadata"
    assert case_data.metadata["mode"] == "deterministic"

    client.delete(f"/api/generated_cases/{case_id}")

def test_list_cases_when_one_case_folder_is_corrupted():
    r1 = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 203,
        "mode": "deterministic"
    })
    assert r1.status_code == 200
    case_id1 = r1.json()["case_id"]

    r2 = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 204,
        "mode": "deterministic"
    })
    assert r2.status_code == 200
    case_id2 = r2.json()["case_id"]

    (TEST_DATA_DIR / case_id2 / "case.json").write_text("corrupted content")

    r_list = client.get("/api/generated_cases")
    assert r_list.status_code == 200
    list_data = r_list.json()
    assert len(list_data) >= 2

    c1 = next((c for c in list_data if c["case_id"] == case_id1), None)
    c2 = next((c for c in list_data if c["case_id"] == case_id2), None)
    assert c1 is not None
    assert c1["load_status"] == "ok"
    assert c2 is not None
    assert c2["load_status"] == "missing_case_data"
    assert c2["title"] == "Corrupted Case"

    client.delete(f"/api/generated_cases/{case_id1}")
    client.delete(f"/api/generated_cases/{case_id2}")

def test_deleting_nonexistent_generated_case():
    r = client.delete("/api/generated_cases/nonexistent_case_12345")
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"

def test_activating_missing_generated_case():
    r = client.post("/api/generated_cases/nonexistent_case_12345/activate")
    assert r.status_code == 404

def test_regenerating_from_case_with_missing_recipe_metadata():
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 205,
        "mode": "deterministic"
    })
    assert r.status_code == 200
    case_id = r.json()["case_id"]

    metadata_file = TEST_DATA_DIR / case_id / "metadata.json"
    if metadata_file.exists():
        metadata_file.unlink()

    # Clear registry memory cache to force load from disk
    reset_case_store()

    r_regen = client.post(f"/api/generated_cases/{case_id}/regenerate")
    assert r_regen.status_code == 400
    assert "Recipe metadata is missing or invalid" in r_regen.json()["detail"]

    client.delete(f"/api/generated_cases/{case_id}")

def test_normalizing_old_metadata_into_current_schema():
    from app.case_store import normalize_case_metadata
    old_meta = {
        "seed": 555,
        "tone": "dark_noir",
    }
    normalized = normalize_case_metadata(old_meta)
    assert normalized["metadata_version"] == 1
    assert normalized["mode"] == "deterministic"
    assert normalized["seed"] == 555
    assert normalized["tone"] == "dark_noir"
    assert normalized["best_of_n_used"] is False
    assert normalized["candidate_count"] == 1
