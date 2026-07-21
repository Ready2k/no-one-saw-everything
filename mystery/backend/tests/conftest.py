import pytest
from app import main
from app.case_store import get_case, reset_case_store, set_active_start_time
from app.session import reset_session_store


def _restore_golden_case():
    reset_case_store()
    reset_session_store()
    main.ACTIVE_CASE_ID = "case_001"
    # Tests that activate generated cases also shift the global time-wrap
    # base; restore it alongside the active case id.
    set_active_start_time(get_case("case_001").case.sim_start_time)
    # The rate limiters are process-lifetime singletons (deliberately — they
    # protect a running server across many requests); reset them per test or
    # a test late in the suite inherits quota already spent by earlier ones.
    main._llm_rate_limiter.reset()
    main._generate_rate_limiter.reset()


@pytest.fixture(autouse=True)
def reset_app_state():
    _restore_golden_case()
    yield
    _restore_golden_case()

@pytest.fixture(autouse=True)
def mock_llm_saved_settings(monkeypatch):
    monkeypatch.setattr("app.llm.config.load_saved_settings", lambda: None)


@pytest.fixture(autouse=True)
def no_generated_case_persistence(monkeypatch):
    """Keep test-generated cases in memory only — don't litter app/data/."""
    monkeypatch.setattr("app.case_store.save_case_to_disk", lambda case: None)

