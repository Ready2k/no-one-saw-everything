import pytest
from app import main
from app.case_store import reset_case_store
from app.session import reset_session_store

@pytest.fixture(autouse=True)
def reset_app_state():
    reset_case_store()
    reset_session_store()
    main.ACTIVE_CASE_ID = "case_001"
    yield
    reset_case_store()
    reset_session_store()
    main.ACTIVE_CASE_ID = "case_001"

@pytest.fixture(autouse=True)
def mock_llm_saved_settings(monkeypatch):
    monkeypatch.setattr("app.llm.config.load_saved_settings", lambda: None)

