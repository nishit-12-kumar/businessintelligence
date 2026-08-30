import pytest
import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = str(Path(__file__).resolve().parents[1])
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='test-secret-key')
    with app.test_client() as test_client:
        yield test_client


def test_health_endpoint(client):
    """Test health check API."""
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json['status'] == 'ok'
    assert 'service' in r.json


def test_all_pages_load(client):
    """Test that all 5 web presentation views render successfully."""
    pages = [
        ('/', b'Business Pulse'),
        ('/investigation', b'Investigation Workspace'),
        ('/security', b'Role-Based Access Control'),
        ('/lineage', b'Semantic Contract'),
        ('/outcomes', b'Decision Outcomes')
    ]
    for path, expected_text in pages:
        r = client.get(path)
        assert r.status_code == 200, f"Failed loading page: {path}"
        assert b'BusinessIntelligence.ai' in r.data
        assert expected_text in r.data


def test_auth_login_logout(client):
    """Test login role selector and logout redirect."""
    # GET /login
    r_get = client.get('/login')
    assert r_get.status_code == 200
    assert b'Select User Role' in r_get.data

    # POST /login — form submit (non-JSON)
    r_post = client.post('/login', data={'role': 'regional_manager_south'}, follow_redirects=True)
    assert r_post.status_code == 200
    assert b'Regional Manager' in r_post.data

    # GET /logout
    r_logout = client.get('/logout', follow_redirects=True)
    assert r_logout.status_code == 200
    assert b'Select User Role' in r_logout.data


# ── Regression: Bug #1 — login operator-precedence fix ──────────────────────

def test_login_form_sets_correct_role_for_all_roles(client):
    """Regression for Bug #1: HTML form POST must set session['role'] to
    whatever role was submitted, NOT silently hard-code 'executive'.

    Before the fix, the expression::

        selected_role = request.form.get('role') or request.json.get('role') if request.is_json else 'executive'

    evaluated as:

        selected_role = (... or ...) if request.is_json else 'executive'

    so a normal HTML form POST (is_json=False) always produced 'executive'.
    """
    from security.authorization import ROLES
    for role_key in ROLES:
        with client.session_transaction() as sess:
            sess.clear()
        r = client.post('/login', data={'role': role_key})
        # Should redirect (302) or reach dashboard (200 after redirect)
        assert r.status_code in (200, 302), f"Unexpected status for role {role_key}"
        with client.session_transaction() as sess:
            assert sess.get('role') == role_key, (
                f"Bug #1 regression: session role '{sess.get('role')}' != '{role_key}' "
                f"after form POST (was always hard-coded to 'executive' before fix)"
            )


# ── Regression: Bug #2 — debug default ──────────────────────────────────────

def test_debug_mode_defaults_off():
    """Regression for Bug #2: FLASK_DEBUG env var must default to '0'."""
    import os
    import importlib
    original = os.environ.pop('FLASK_DEBUG', None)
    try:
        import run_app  # noqa: F401 — we just verify the source
        import inspect
        source = inspect.getsource(run_app)
        assert "os.environ.get('FLASK_DEBUG', '0')" in source, (
            "Bug #2 regression: FLASK_DEBUG default must be '0', not '1'"
        )
    finally:
        if original is not None:
            os.environ['FLASK_DEBUG'] = original


# ── Regression: Bug #3 — no literal secret key ──────────────────────────────

def test_config_secret_key_not_hardcoded_literal():
    """Regression for Bug #3: Config.SECRET_KEY must never be the known
    fallback literal 'change-me-in-production'."""
    from config import Config
    assert Config.SECRET_KEY != 'change-me-in-production', (
        "Bug #3 regression: SECRET_KEY must not be the well-known fallback literal"
    )
    assert len(Config.SECRET_KEY) >= 32, "SECRET_KEY is too short — must be at least 32 chars"


# ── Regression: Bug #4 — anomaly URL pipe scheme ────────────────────────────

def test_anomaly_detail_pipe_url_xphone_pro(client):
    """Regression for Bug #4: product name 'XPhone Pro' (with space) must
    resolve correctly through the pipe-separated URL scheme.
    URL: /anomaly/revenue|South|XPhone%20Pro
    """
    with client.session_transaction() as sess:
        sess['role'] = 'executive'
    r = client.get('/anomaly/revenue|South|XPhone%20Pro')
    assert r.status_code == 200
    assert b'Variance Decomposition' in r.data


def test_anomaly_detail_underscore_product_name(client):
    """Regression for Bug #4: product names with underscores must not confuse
    the route parser. Using the pipe separator, 'Pro_Max' remains intact.
    """
    with client.session_transaction() as sess:
        sess['role'] = 'executive'
    # This should not 404 (the underscore is in the product segment, not the separator)
    r = client.get('/anomaly/revenue|South|XPhone_Pro_Max')
    # Investigation may return empty/error result, but route itself must not crash
    assert r.status_code in (200, 404)  # 404 if product not found, but NOT 500


def test_anomaly_detail_malformed_id_returns_404(client):
    """Regression for Bug #4: a malformed anomaly_id with no pipe separator
    must return HTTP 404, not a silently-wrong 200.
    """
    with client.session_transaction() as sess:
        sess['role'] = 'executive'
    r = client.get('/anomaly/revenue_South_XPhone_Pro_this_is_old_format')
    assert r.status_code == 404, (
        "Bug #4 regression: malformed anomaly ID (underscore-only, no pipes) "
        "must return 404, not a silently wrong 200"
    )


# ── Regression: Bug #5 — no google-generativeai FutureWarning ───────────────

def test_no_deprecated_generativeai_import():
    """Regression for Bug #5: google.generativeai (deprecated) must not be
    imported by narrative.py or retriever.py — both must use google.genai.
    """
    import importlib
    import sys

    for mod_name in ('retrieval.retriever', 'llm.narrative'):
        # Remove cached module to force re-import
        for key in list(sys.modules):
            if key.startswith(mod_name.split('.')[0]):
                pass  # we just want the source check below

    # Source-level check: deprecated import must not appear
    import inspect
    import retrieval.retriever as retriever_mod
    import llm.narrative as narrative_mod

    retriever_src = inspect.getsource(retriever_mod)
    narrative_src = inspect.getsource(narrative_mod)

    assert 'import google.generativeai' not in retriever_src, (
        "Bug #5 regression: retriever.py must not import deprecated google.generativeai"
    )
    assert 'import google.generativeai' not in narrative_src, (
        "Bug #5 regression: narrative.py must not import deprecated google.generativeai"
    )


# ── Improvement #6 — db_type allow-list ─────────────────────────────────────

def test_external_db_disallows_unknown_type(client):
    """Improvement #6: /api/external-db/test must reject unsupported db_type values."""
    r = client.post('/api/external-db/test', json={
        'db_type': 'redis',
        'connection_string': 'localhost:6379'
    })
    assert r.status_code == 400
    assert 'Unsupported db_type' in r.json.get('message', '')


# ── Improvement #8 — RBAC gap: /api/kpis must not expose cross-region data ──

def test_api_kpis_respects_role_rbac(client):
    """Improvement #8: /api/kpis?role=regional_manager_south must only return
    data for allowed regions (South), never North/East/West.
    """
    r = client.get('/api/kpis?role=regional_manager_south')
    assert r.status_code == 200
    assert r.json['status'] == 'ok'
    allowed = r.json.get('allowed_regions', [])
    assert 'South' in allowed
    assert 'North' not in allowed, (
        "RBAC gap: regional_manager_south must not have North in allowed_regions"
    )



def test_dashboard_routes(client):
    """Test executive and regional dashboard routes."""
    # Executive dashboard
    with client.session_transaction() as sess:
        sess['role'] = 'executive'
    r_exec = client.get('/dashboard')
    assert r_exec.status_code == 200
    assert b'Executive Decision' in r_exec.data

    # Regional Manager dashboard
    with client.session_transaction() as sess:
        sess['role'] = 'regional_manager_south'
    r_reg = client.get('/dashboard')
    assert r_reg.status_code == 200
    assert b'Regional Access' in r_reg.data


def test_anomaly_detail_route(client):
    """Test anomaly detail page route using the new pipe-separated URL scheme (Bug #4 fix)."""
    with client.session_transaction() as sess:
        sess['role'] = 'executive'
    # New format: /anomaly/<kpi>|<region>|<product_url_encoded>
    r = client.get('/anomaly/revenue|South|XPhone%20Pro')
    assert r.status_code == 200
    assert b'Variance Decomposition' in r.data


def test_report_pdf_routes(client):
    """Test PDF report routes."""
    r1 = client.get('/report/pdf')
    assert r1.status_code == 200
    assert r1.content_type == 'application/pdf'

    r2 = client.get('/api/report/investigation')
    assert r2.status_code == 200
    assert r2.content_type == 'application/pdf'


def test_pulse_api(client):
    """Test /api/pulse returns live calculations across all 5 KPIs."""
    r = client.get('/api/pulse')
    assert r.status_code == 200
    data = r.json
    assert 'pulse' in data
    assert 'alerts' in data
    assert 'freshness' in data
    assert len(data['pulse']) == 5
    kpi_names = [p['kpi_name'] for p in data['pulse']]
    assert 'revenue' in kpi_names
    assert 'orders' in kpi_names
    assert 'asp' in kpi_names
    assert 'conversion_rate' in kpi_names
    assert 'inventory_stockout_rate' in kpi_names


def test_api_kpis_and_anomalies(client):
    """Test /api/kpis and /api/anomalies endpoints."""
    r_kpis = client.get('/api/kpis?role=executive')
    assert r_kpis.status_code == 200
    assert 'kpis' in r_kpis.json
    assert len(r_kpis.json['kpis']) == 5

    r_anom = client.get('/api/anomalies?role=executive')
    assert r_anom.status_code == 200
    assert 'anomalies' in r_anom.json


def test_investigation_api_executive(client):
    """Test running full investigation pipeline for South Revenue with statistical hypothesis and KG."""
    payload = {
        'role': 'executive',
        'kpi': 'revenue',
        'region': 'South',
        'product': 'XPhone Pro',
        'demo': False,
        'stale': False
    }
    r = client.post('/api/investigation', json=payload)
    assert r.status_code == 200
    data = r.json
    assert data['status'] == 'ok'
    res = data['result']
    assert 'kpi' in res
    assert 'drivers' in res
    assert len(res['drivers']) > 0
    assert 'confidence' in res
    assert 'score' in res['confidence']
    assert 'recommendations' in res
    assert len(res['recommendations']) > 0
    assert 'external_pricing' in res
    assert 'narrative' in res
    assert 'decision_trace' in res

    # Verify structured action schema keys in recommendations
    first_rec = res['recommendations'][0]
    assert 'driver' in first_rec
    assert 'action' in first_rec
    assert 'expected_impact' in first_rec
    assert 'owner' in first_rec
    assert 'confidence' in first_rec


def test_investigation_sparse_history_abstention(client):
    """Test that NovaWatch (<14 days of data) triggers explicit abstention."""
    payload = {
        'role': 'executive',
        'kpi': 'revenue',
        'region': 'South',
        'product': 'NovaWatch',
        'demo': False,
        'stale': False
    }
    r = client.post('/api/investigation', json=payload)
    assert r.status_code == 200
    res = r.json['result']
    assert res['anomaly']['sparse_history'] is True
    assert res['confidence']['level'] == 'LOW'


def test_investigation_security_denial(client):
    """Test that Regional Manager South is denied from querying North region."""
    payload = {
        'role': 'regional_manager_south',
        'kpi': 'revenue',
        'region': 'North',
        'product': 'XPhone Pro',
        'demo': False
    }
    r = client.post('/api/investigation', json=payload)
    assert r.status_code == 200
    res = r.json['result']
    assert 'error' in res
    assert 'Access denied' in res['error']


def test_security_authorization_test_api(client):
    """Test live authorization test API for granted, denied, and ops_lead scenarios."""
    # Granted: Regional Manager South -> South
    r_grant = client.post('/api/security/test', json={
        'role': 'regional_manager_south',
        'region': 'South',
        'kpi': 'revenue'
    })
    assert r_grant.status_code == 200
    assert r_grant.json['authorized'] is True
    assert 'South' in r_grant.json['authorized_regions']

    # Denied: Regional Manager South -> North
    r_deny = client.post('/api/security/test', json={
        'role': 'regional_manager_south',
        'region': 'North',
        'kpi': 'revenue'
    })
    assert r_deny.status_code == 200
    assert r_deny.json['authorized'] is False

    # Granted: Operations Lead -> Inventory Stockout Rate
    r_ops = client.post('/api/security/test', json={
        'role': 'ops_lead',
        'region': 'South',
        'kpi': 'inventory_stockout_rate'
    })
    assert r_ops.status_code == 200
    assert r_ops.json['authorized'] is True


def test_preferences_session_api(client):
    """Test session state preference synchronization."""
    r_set = client.post('/api/preferences', json={
        'role': 'regional_manager_north',
        'region': 'North',
        'stale': True
    })
    assert r_set.status_code == 200
    assert r_set.json['state']['role'] == 'regional_manager_north'
    assert r_set.json['state']['stale'] is True

    r_get = client.get('/api/preferences')
    assert r_get.status_code == 200
    assert r_get.json['state']['role'] == 'regional_manager_north'


def test_lineage_api(client):
    """Test semantic contract validation and lineage retrieval."""
    r = client.get('/api/lineage')
    assert r.status_code == 200
    data = r.json
    assert data['valid'] is True
    assert 'definitions' in data
    assert 'revenue' in data['definitions']
    assert 'inventory_stockout_rate' in data['definitions']
    assert 'formula' in data['definitions']['revenue']


def test_feedback_and_outcomes_api(client):
    """Test submitting recommendation feedback and loading outcomes."""
    fb_payload = {
        'context': 'revenue (South)',
        'action': 'Restore marketing spend for XPhone Pro',
        'feedback': 'thumbs_up',
        'status': 'accepted'
    }
    r_fb = client.post('/api/feedback', json=fb_payload)
    assert r_fb.status_code == 200
    assert r_fb.json['status'] == 'recorded'

    r_out = client.get('/api/outcomes')
    assert r_out.status_code == 200
    assert 'total_recommendations' in r_out.json or 'recommendations_issued' in r_out.json


def test_simulation_api(client):
    """Test what-if scenario simulation endpoint (/api/simulation and /api/simulate)."""
    sim_payload = {
        'kpi': 'revenue',
        'region': 'South',
        'product': 'XPhone Pro',
        'driver': 'Volume',
        'improvement': 3.0,
        'current_value': 4200000.0,
        'original_impact': -6.2
    }
    r1 = client.post('/api/simulation', json=sim_payload)
    assert r1.status_code == 200
    assert 'estimated_kpi_recovery_pct' in r1.json
    assert r1.json['estimated_kpi_recovery_pct'] > 0

    r2 = client.post('/api/simulate', json=sim_payload)
    assert r2.status_code == 200
    assert 'estimated_kpi_recovery_pct' in r2.json


def test_external_pricing_api(client):
    """Test external competitor pricing REST API endpoint."""
    r = client.get('/api/pricing/XPhone%20Pro')
    assert r.status_code == 200
    data = r.json
    assert data['status'] == 'ok'
    assert 'data' in data
    assert 'competitor_price' in data['data']
    assert 'discount_pct' in data['data']


def test_external_db_test_api(client):
    """Test external database connector connection tester."""
    r = client.post('/api/external-db/test', json={
        'db_type': 'duckdb',
        'connection_string': 'data/inventory.csv'
    })
    assert r.status_code == 200
    assert r.json['status'] == 'SUCCESS'


def test_external_db_ingest_api(client):
    """Test external database connector ingestion endpoint."""
    r = client.post('/api/external-db/ingest', json={
        'target_table': 'inventory',
        'db_type': 'duckdb',
        'connection_string': 'data/inventory.csv',
        'query': 'SELECT * FROM inventory'
    })
    assert r.status_code == 200
    assert r.json['status'] == 'SUCCESS'
    assert 'row_count' in r.json
