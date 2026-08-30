"""Flask routes and blueprints for BusinessIntelligence.ai.

Serves both:
1. The Superlist-inspired presentation layer (`/`, `/investigation`, `/security`, `/lineage`, `/outcomes`)
2. Role-based Dashboard and Auth routes (`/login`, `/logout`, `/dashboard`, `/anomaly/<path:anomaly_id>`, `/report/pdf`)
3. Complete REST API endpoints (`/api/kpis`, `/api/anomalies`, `/api/pulse`, `/api/investigation`, `/api/simulate`, `/api/pricing/<product>`, `/api/external-db/test`, `/api/external-db/ingest`, `/api/report/investigation`)

Anomaly ID format: `<kpi>|<region>|<product_url_encoded>`
Example: `revenue|South|XPhone%20Pro`
"""
from __future__ import annotations
import os
import logging
import urllib.parse
from flask import Blueprint, jsonify, render_template, request, session, redirect, url_for, send_file, abort
from services.bi_backend import (
    build_context, get_roles, get_pulse, run_investigation, feedback,
    test_authorization, simulate, lineage, outcomes,
    fetch_pricing_benchmark, test_external_db, ingest_external_db,
    generate_pdf_report_file
)
from security.authorization import authorize, get_allowed_regions, ROLES
from analytics.kpi_engine import create_connection, calculate_all_kpis, calculate_kpi
from analytics.anomaly_detection import detect_anomalies

logger = logging.getLogger(__name__)

# Improvement #6: allow-list for external DB types to prevent client-supplied injection
_ALLOWED_DB_TYPES = frozenset({'sqlite', 'duckdb', 'postgresql', 'mysql', 'snowflake'})

bp = Blueprint('main', __name__)
CTX = build_context()

PAGES = {
    'overview': 'Business Pulse',
    'investigate': 'Investigation',
    'security': 'Security',
    'lineage': 'Data lineage',
    'outcomes': 'Outcomes & Feedback',
    'dashboard': 'Dashboard',
    'anomaly_detail': 'Anomaly Investigation'
}


def _state() -> dict:
    """Retrieve or initialize the active session preferences."""
    return {
        'role': session.get('role', 'executive'),
        'region': session.get('region', 'South'),
        'kpi': session.get('kpi', 'revenue'),
        'product': session.get('product', 'All Products'),
        'demo': session.get('demo', True),
        'stale': session.get('stale', False),
    }


def _render_page(view: str, title: str, **kwargs):
    """Render the base template with active page view, state, and extra kwargs."""
    state = _state()
    roles = get_roles(CTX)
    return render_template(
        'base.html',
        view=view,
        title=title,
        roles=roles,
        state=state,
        backend_demo=CTX.demo,
        **kwargs
    )


def _json_error(message: str, status: int = 400):
    return jsonify({'status': 'error', 'message': message}), status


# ── Auth Blueprint Routes ───────────────────────────────────────────────────

@bp.route('/login', methods=['GET', 'POST'])
def login():
    roles = get_roles(CTX)
    if request.method == 'POST':
        # Bug #1 fix: avoid Python precedence trap — check is_json first,
        # then read from the appropriate source explicitly.
        if request.is_json:
            selected_role = (request.get_json(silent=True) or {}).get('role', 'executive')
        else:
            selected_role = request.form.get('role', 'executive')

        if selected_role in ROLES:
            session['role'] = selected_role
            # Set default region for regional managers
            allowed = get_allowed_regions(selected_role)
            if allowed and allowed[0] != 'All':
                session['region'] = allowed[0]
            if request.is_json:
                return jsonify({'status': 'ok', 'role': selected_role})
            return redirect(url_for('main.dashboard'))
    return render_template('login.html', roles=roles, active_role=session.get('role', 'executive'))


@bp.get('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))


# ── Dashboard & Anomaly Detail Routes ───────────────────────────────────────

@bp.get('/dashboard')
def dashboard():
    state = _state()
    role = state['role']
    allowed_regions = get_allowed_regions(role)
    is_auth, msg, authed = authorize(role, allowed_regions, 'revenue')
    
    if not is_auth:
        return render_template('access_denied.html', error_message=msg), 403

    conn = create_connection()
    try:
        raw_kpis = calculate_all_kpis(conn, authed)
        anomalies = detect_anomalies(conn, authed)
        
        pulse_kpis = []
        for k in raw_kpis:
            chg = k.get('change_pct', 0.0)
            kname = k.get('kpi_name', 'revenue')
            curr_val = k.get('current_value', 0.0)
            
            if kname in ('revenue', 'asp'):
                val_str = f"₹{curr_val/1e7:.2f} Cr" if curr_val >= 1e7 else (f"₹{curr_val/1e5:.1f} L" if curr_val >= 1e5 else f"₹{curr_val:,.0f}")
            elif kname in ('conversion_rate', 'inventory_stockout_rate'):
                val_str = f"{curr_val*100:.2f}%" if kname == 'conversion_rate' else f"{curr_val:.2f}%"
            else:
                val_str = f"{curr_val:,.0f}"
                
            pulse_kpis.append({
                'kpi_name': kname,
                'definition': k.get('definition', kname),
                'value': val_str,
                'change': chg,
                'threshold': k.get('threshold', 5.0)
            })
            
        role_info = ROLES.get(role, {})
        is_exec = role_info.get('level') in ('executive', 'admin') or role == 'analyst'
        
        if is_exec:
            dashboard_html = render_template('executive_dashboard.html', kpis=pulse_kpis, anomalies=anomalies, role_info=role_info, allowed_regions=authed)
        else:
            dashboard_html = render_template('regional_dashboard.html', kpis=pulse_kpis, anomalies=anomalies, role_info=role_info, allowed_regions=authed)
            
        return _render_page('dashboard', 'Executive Dashboard' if is_exec else 'Regional Dashboard', dashboard_content=dashboard_html)
    finally:
        conn.close()


@bp.get('/anomaly/<path:anomaly_id>')
def anomaly_detail(anomaly_id: str):
    """View deep-dive root cause investigation for a specific anomaly ID.

    Format (pipe-separated, URL-encoded product): <kpi>|<region>|<product>
    Example: /anomaly/revenue|South|XPhone%20Pro

    Using '|' as separator avoids ambiguity with product names that contain
    underscores or spaces. Flask will URL-decode the path before it reaches here.
    """
    state = _state()
    role = state['role']

    # Bug #4 fix: split on pipe to handle product names with underscores / spaces
    parts = anomaly_id.split('|', 2)
    if len(parts) < 2:
        # Malformed ID — return 404 instead of silently ignoring
        logger.warning("Malformed anomaly_id received: %r", anomaly_id)
        abort(404)

    kpi_name = parts[0].strip()
    region = parts[1].strip()
    raw_product = parts[2].strip() if len(parts) > 2 else 'All'
    product = urllib.parse.unquote(raw_product)
    if product in ('All', ''):
        product = 'All Products'

    is_auth, msg, authed = authorize(role, [region], kpi_name)
    if not is_auth:
        return render_template('access_denied.html', error_message=msg), 403

    payload = {
        'role': role,
        'kpi': kpi_name,
        'region': region,
        'product': None if product == 'All Products' else product,
        'demo': state['demo'],
        'stale': state['stale']
    }

    result, telemetry = run_investigation(CTX, payload)
    detail_html = render_template(
        'anomaly_detail.html',
        kpi_name=kpi_name,
        region=region,
        product=product,
        kpi_info=result.get('kpi', {}),
        anomaly=result.get('anomaly', {}),
        drivers=result.get('drivers', []),
        confidence=result.get('confidence', {}),
        recommendations=result.get('recommendations', [])
    )
    return _render_page('anomaly_detail', f"Anomaly: {kpi_name.upper()} ({region})", dashboard_content=detail_html)


@bp.get('/report/pdf')
def download_pdf():
    """Download technical investigation report in PDF."""
    return api_download_report()


# ── Superlist Core Page Views ───────────────────────────────────────────────

@bp.get('/')
def index():
    return _render_page('overview', 'Business Pulse')


@bp.get('/investigation')
def investigation_page():
    return _render_page('investigate', 'Investigation Workspace')


@bp.get('/security')
def security_page():
    return _render_page('security', 'Security & Access')


@bp.get('/lineage')
def lineage_page():
    return _render_page('lineage', 'Data Lineage & Semantics')


@bp.get('/outcomes')
def outcomes_page():
    return _render_page('outcomes', 'Outcomes & Telemetry')


@bp.get('/health')
def health():
    return jsonify({
        'status': 'ok',
        'service': 'BusinessIntelligence.ai',
        'backend_demo': CTX.demo
    })


# ── REST API Endpoints ──────────────────────────────────────────────────────

@bp.get('/api/kpis')
def api_kpis():
    state = _state()
    role = request.args.get('role') or state['role']
    allowed_regions = get_allowed_regions(role)
    conn = create_connection()
    try:
        raw_kpis = calculate_all_kpis(conn, allowed_regions)
        return jsonify({'status': 'ok', 'kpis': raw_kpis, 'role': role, 'allowed_regions': allowed_regions})
    finally:
        conn.close()


@bp.get('/api/anomalies')
def api_anomalies():
    state = _state()
    role = request.args.get('role') or state['role']
    allowed_regions = get_allowed_regions(role)
    conn = create_connection()
    try:
        anomalies = detect_anomalies(conn, allowed_regions)
        return jsonify({'status': 'ok', 'anomalies': anomalies, 'role': role, 'allowed_regions': allowed_regions})
    finally:
        conn.close()


@bp.get('/api/preferences')
def get_preferences():
    return jsonify({'status': 'ok', 'state': _state()})


@bp.post('/api/preferences')
def set_preferences():
    data = request.get_json(silent=True) or {}
    for key in ('role', 'region', 'kpi', 'product', 'demo', 'stale'):
        if key in data:
            session[key] = data[key]
    return jsonify({'status': 'ok', 'state': _state()})


@bp.get('/api/pulse')
def api_pulse():
    state = _state()
    role = request.args.get('role') or state['role']
    stale = request.args.get('stale', '').lower() == 'true' if 'stale' in request.args else state['stale']
    data = get_pulse(CTX, role=role, stale=stale)
    return jsonify(data)


@bp.post('/api/investigation')
def api_investigation():
    payload = request.get_json(silent=True) or {}
    
    # Synchronize session state from payload
    for key in ('role', 'region', 'kpi', 'product', 'demo', 'stale'):
        if key in payload:
            session[key] = payload[key]
            
    merged = {**_state(), **payload}
    result, telemetry = run_investigation(CTX, merged)
    
    tel_summary = telemetry.get_summary() if telemetry and hasattr(telemetry, 'get_summary') else {}
    session['telemetry'] = tel_summary
    
    return jsonify({
        'status': 'ok',
        'result': result,
        'telemetry': tel_summary
    })


@bp.post('/api/feedback')
def api_feedback():
    payload = request.get_json(silent=True) or {}
    if not payload.get('action'):
        return _json_error('Action field is required for recording feedback')
    res = feedback(CTX, payload)
    return jsonify(res)


@bp.post('/api/security/test')
def api_security():
    data = request.get_json(silent=True) or {}
    role = data.get('role') or _state()['role']
    region = data.get('region', 'South')
    kpi = data.get('kpi', 'revenue')
    res = test_authorization(CTX, role=role, region=region, kpi=kpi)
    return jsonify(res)


@bp.get('/api/lineage')
def api_lineage():
    stale = request.args.get('stale', '').lower() == 'true' if 'stale' in request.args else _state()['stale']
    return jsonify(lineage(CTX, stale=stale))


@bp.get('/api/outcomes')
def api_outcomes():
    data = outcomes(CTX)
    data['telemetry'] = session.get('telemetry', data.get('telemetry', {}))
    return jsonify(data)


@bp.post('/api/simulate')
@bp.post('/api/simulation')
def api_simulation():
    payload = request.get_json(silent=True) or {}
    res = simulate(CTX, payload)
    return jsonify(res)


# ── Pricing, External DB, PDF Report ────────────────────────────────────────

@bp.get('/api/pricing/<product>')
def api_pricing(product: str):
    """Fetch external competitor benchmark data for a product."""
    data = fetch_pricing_benchmark(product)
    return jsonify({'status': 'ok', 'product': product, 'data': data})


@bp.post('/api/external-db/test')
def api_external_db_test():
    """Test connection to external database engine."""
    payload = request.get_json(silent=True) or {}
    db_type = payload.get('db_type', 'sqlite')
    # Improvement #6: validate db_type against explicit allow-list
    if db_type not in _ALLOWED_DB_TYPES:
        return _json_error(f"Unsupported db_type '{db_type}'. Allowed: {sorted(_ALLOWED_DB_TYPES)}", 400)
    conn_str = payload.get('connection_string', 'data/inventory.csv')
    res = test_external_db(db_type, conn_str)
    return jsonify(res)


@bp.post('/api/external-db/ingest')
def api_external_db_ingest():
    """Ingest query data from external DB into DuckDB analytical memory."""
    payload = request.get_json(silent=True) or {}
    target_table = payload.get('target_table', 'inventory')
    db_type = payload.get('db_type', 'sqlite')
    # Improvement #6: validate db_type against explicit allow-list
    if db_type not in _ALLOWED_DB_TYPES:
        return _json_error(f"Unsupported db_type '{db_type}'. Allowed: {sorted(_ALLOWED_DB_TYPES)}", 400)
    conn_str = payload.get('connection_string', 'data/inventory.csv')
    query = payload.get('query', f'SELECT * FROM {target_table}')
    res = ingest_external_db(target_table, db_type, conn_str, query)
    return jsonify(res)


@bp.get('/api/report/investigation')
def api_download_report():
    """Generate and download the comprehensive PDF investigation report."""
    try:
        pdf_path = generate_pdf_report_file()
        if os.path.exists(pdf_path):
            return send_file(
                pdf_path,
                as_attachment=True,
                download_name="BusinessIntelligence_AI_Detailed_Report.pdf",
                mimetype="application/pdf"
            )
        return _json_error("PDF file generation failed.", 500)
    except Exception as e:
        return _json_error(f"Error generating PDF report: {str(e)}", 500)
