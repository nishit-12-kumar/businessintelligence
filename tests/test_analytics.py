import pytest
import os
import sys
import duckdb

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ssl_patch

from analytics.kpi_engine import create_connection, calculate_kpi, calculate_all_kpis
from analytics.anomaly_detection import detect_anomalies, check_sparse_history
from analytics.driver_analysis import analyze_revenue_drivers
from security.authorization import authorize, get_allowed_regions

@pytest.fixture(scope="module")
def db_conn():
    return create_connection()

def test_kpi_calculations(db_conn):
    # Executive can see all regions
    allowed = get_allowed_regions("executive")
    
    # Calculate revenue
    rev = calculate_kpi(db_conn, "revenue", allowed)
    assert rev['authorized'] == True
    assert rev['current_value'] > 0
    assert rev['previous_value'] > 0
    
    # Calculate orders
    ord_val = calculate_kpi(db_conn, "orders", allowed)
    assert ord_val['authorized'] == True
    assert ord_val['current_value'] > 0
    
    # Calculate asp
    asp = calculate_kpi(db_conn, "asp", allowed)
    assert asp['authorized'] == True
    assert asp['current_value'] > 0
    
    # Calculate conversion_rate
    cr = calculate_kpi(db_conn, "conversion_rate", allowed)
    assert cr['authorized'] == True
    # conversion rate should be a small fraction or percentage
    assert 0 <= cr['current_value'] <= 1

def test_role_based_security(db_conn):
    # Test Regional Manager (South Only)
    rm_allowed = get_allowed_regions("regional_manager_south")
    assert rm_allowed == ["South"]
    
    # Access South - Allowed
    is_auth, msg, authed = authorize("regional_manager_south", ["South"], "revenue")
    assert is_auth == True
    assert authed == ["South"]
    
    # Access North - Denied
    is_auth, msg, authed = authorize("regional_manager_south", ["North"], "revenue")
    assert is_auth == False
    assert "Access denied" in msg
    assert len(authed) == 0

def test_driver_analysis(db_conn):
    allowed = get_allowed_regions("executive")
    
    # Run driver analysis for South region revenue drop
    driver_res = analyze_revenue_drivers(db_conn, "South", "XPhone Pro", allowed)
    
    assert driver_res['abstention'] == False
    assert len(driver_res['drivers']) > 0
    
    # Check that at least some key drivers are present
    driver_names = [d['driver_name'] for d in driver_res['drivers']]
    assert any("Competitor" in name or "Price" in name for name in driver_names)

def test_sparse_history(db_conn):
    # NovaWatch should trigger sparse history as it starts on 2026-08-16
    sparse_res = check_sparse_history(db_conn, "NovaWatch")
    assert sparse_res['is_sparse'] == True
    assert "Sparse history" in sparse_res['warning']
    
    # XPhone Pro should NOT trigger sparse history (58 days of history)
    not_sparse_res = check_sparse_history(db_conn, "XPhone Pro")
    assert not_sparse_res['is_sparse'] == False

def test_semantic_contract_validation():
    from semantic.validator import validate_semantic_contract
    valid, errors = validate_semantic_contract()
    assert valid == True
    assert len(errors) == 0

def test_impact_score_calculation():
    from analytics.impact_calculator import calculate_impact_score
    # Test High confidence, high change revenue drop impact
    res = calculate_impact_score("revenue", -12.4, 4200000.0, 4800000.0, 87.0)
    assert res['impact_score'] > 0
    assert res['impact_category'] in ["HIGH", "MEDIUM", "LOW"]
    assert res['exposure_monthly'] > 0
    assert res['recovery_min'] > 0
    assert res['recovery_max'] > 0

def test_recommendation_generation(db_conn):
    from analytics.recommendation_engine import generate_recommendations
    from analytics.impact_calculator import calculate_impact_score
    from retrieval.retriever import get_all_evidence
    
    allowed = get_allowed_regions("executive")
    driver_res = analyze_revenue_drivers(db_conn, "South", "XPhone Pro", allowed)
    evidence = get_all_evidence(db_conn, "South", "XPhone Pro")
    impact_res = calculate_impact_score("revenue", -12.4, 4200000.0, 4800000.0, 87.0)
    
    actions = generate_recommendations(driver_res['drivers'], evidence, impact_res, driver_res['confidence'], "South", "XPhone Pro")
    assert len(actions) > 0
    for act in actions:
        assert 'action' in act
        assert 'reason' in act
        assert 'supporting_evidence' in act
        assert 'expected_impact' in act
        assert 'confidence' in act
        assert 'priority' in act

def test_investigation_orchestrator(db_conn):
    from analytics.investigation_engine import run_investigation
    # Run regular pipeline for South Revenue Drop
    res = run_investigation(db_conn, "revenue", "South", "XPhone Pro", "executive")
    
    assert res['is_demo'] == False
    assert 'kpi' in res
    assert 'anomaly' in res
    assert 'drivers' in res
    assert 'evidence' in res
    assert 'confidence' in res
    assert 'impact' in res
    assert 'recommendations' in res
    assert len(res['decision_trace']) > 0

def test_demo_mode(db_conn):
    from analytics.investigation_engine import run_investigation
    res = run_investigation(db_conn, "revenue", "South", "XPhone Pro", "executive", is_demo=True)
    
    assert res['is_demo'] == True
    assert res['kpi']['change_pct'] == -12.4
    assert res['confidence']['score'] == 82
    assert len(res['recommendations']) > 0

def test_contradiction_detection(db_conn):
    from retrieval.retriever import get_contradicting_evidence
    contradictions = get_contradicting_evidence(db_conn, "South", "XPhone Pro")
    # In South XPhone Pro, we might not have customer sentiment saying "on time",
    # but we check if campaign CTR rose. In South marketing, all campaigns dropped CTR.
    # So contractions should be empty or contain CTR checks.
    assert isinstance(contradictions, list)

def test_evidence_coverage(db_conn):
    from retrieval.retriever import calculate_evidence_coverage, get_all_evidence
    allowed = get_allowed_regions("executive")
    driver_res = analyze_revenue_drivers(db_conn, "South", "XPhone Pro", allowed)
    evidence = get_all_evidence(db_conn, "South", "XPhone Pro")
    
    coverage = calculate_evidence_coverage(driver_res['drivers'], evidence)
    assert 'score' in coverage
    assert 'checklist' in coverage
    assert coverage['score'] > 0

def test_recommendation_guardrails(db_conn):
    from analytics.recommendation_engine import generate_recommendations
    from analytics.impact_calculator import calculate_impact_score
    from retrieval.retriever import get_all_evidence
    
    allowed = get_allowed_regions("executive")
    driver_res = analyze_revenue_drivers(db_conn, "South", "XPhone Pro", allowed)
    evidence = get_all_evidence(db_conn, "South", "XPhone Pro")
    impact_res = calculate_impact_score("revenue", -12.4, 4200000.0, 4800000.0, 87.0)
    
    # Test LOW confidence (<50%) guardrail
    low_confidence_info = {
        'score': 35, 'level': 'LOW', 'reason': 'Test low confidence', 'breakdown': {}
    }
    actions = generate_recommendations(
        driver_res['drivers'], evidence, impact_res, low_confidence_info, 
        "South", "XPhone Pro", persona="executive"
    )
    assert len(actions) == 1
    assert "Continue monitoring" in actions[0]['action']
    assert actions[0]['priority'] == "LOW"
    
    # Test MEDIUM confidence (50-75%) guardrail
    med_confidence_info = {
        'score': 65, 'level': 'MEDIUM', 'reason': 'Test med confidence', 'breakdown': {}
    }
    actions_med = generate_recommendations(
        driver_res['drivers'], evidence, impact_res, med_confidence_info, 
        "South", "XPhone Pro", persona="executive"
    )
    assert len(actions_med) > 0
    assert any("Audit" in act['action'] or "Conduct" in act['action'] for act in actions_med)

def test_additional_roles_authorization():
    from security.authorization import authorize, get_allowed_regions
    # Regional manager north
    north_regions = get_allowed_regions("regional_manager_north")
    assert north_regions == ["North"]
    is_auth, msg, authed = authorize("regional_manager_north", ["North"], "revenue")
    assert is_auth == True
    assert authed == ["North"]

    # Analyst role
    analyst_regions = get_allowed_regions("analyst")
    assert "South" in analyst_regions and "North" in analyst_regions

def test_telemetry_get_summary():
    from monitoring.telemetry import TelemetryTracker
    tel = TelemetryTracker()
    tel.start()
    tel.record_step("Test Step")
    tel.end()
    summary = tel.get_summary()
    assert 'total_ms' in summary
    assert 'step_count' in summary
    assert summary['step_count'] == 1

def test_feedback_loop_metrics():
    from analytics.feedback_loop import load_feedback_metrics, save_feedback
    save_feedback("Test KPI", "Test action", "thumbs_up", "accepted")
    metrics = load_feedback_metrics()
    assert 'total_recommendations' in metrics
    assert 'accepted' in metrics
    assert 'rejected' in metrics
    assert 'acceptance_rate' in metrics
    assert 'recent_feedback' in metrics

def test_kpi_sources_list_handling():
    from analytics.kpi_engine import load_kpi_definitions
    from monitoring.telemetry import get_source_freshness
    kpi_defs = load_kpi_definitions()
    freshness = get_source_freshness()
    for name, kdef in kpi_defs.items():
        src = kdef.get('source', '?')
        if isinstance(src, list):
            for s in src:
                assert s in freshness
        else:
            assert src in freshness


