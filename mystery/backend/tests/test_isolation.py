def test_isolation_regression_part1():
    from app import main
    from app.generator import generate_case
    from app.case_store import register_case
    
    # Generate and ACTIVATE a case
    new_case, _, _, _ = generate_case("blackmail", "standard", seed=123, mode="deterministic")
    register_case(new_case)
    main.ACTIVE_CASE_ID = new_case.case.case_id
    
    assert main.ACTIVE_CASE_ID != "case_001"

def test_isolation_regression_part2():
    from app import main
    # This should be reset back to case_001 by the autouse fixture
    assert main.ACTIVE_CASE_ID == "case_001"
