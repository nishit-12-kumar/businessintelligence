"""BusinessIntelligence.ai — Streamlit Application.

Decision Intelligence product for detecting, investigating, and acting on business anomalies.
All analytics are computed by the Investigation Orchestrator. The UI is purely presentational.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ssl_patch

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from analytics.kpi_engine import create_connection, calculate_all_kpis, load_kpi_definitions
from analytics.investigation_engine import run_investigation
from analytics.anomaly_detection import detect_anomalies
from analytics.impact_calculator import calculate_impact_score
from analytics.feedback_loop import load_feedback_metrics, save_feedback
from analytics.simulator import run_what_if_simulation
from security.authorization import get_allowed_regions, ROLES
from monitoring.telemetry import TelemetryTracker, get_source_freshness, get_stale_source_freshness
from semantic.validator import validate_semantic_contract
from llm.narrative import get_llm_vs_non_llm_breakdown

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BusinessIntelligence.ai",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* Evidence cards — dark-mode safe */
    .evidence-card {
        background: rgba(13, 110, 253, 0.10);
        border-left: 4px solid #4dabf7;
        padding: 10px 14px;
        border-radius: 4px;
        margin-bottom: 8px;
        font-size: 13px;
        color: inherit;
    }
    .evidence-card.contradict {
        border-left-color: #f03e3e;
        background: rgba(240, 62, 62, 0.10);
    }
    /* Data-type tags */
    .tag {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 700;
        margin-right: 4px;
    }
    .tag-observed   { background:#2d6a4f; color:#d8f3dc; }
    .tag-calc       { background:#1e3a8a; color:#bfdbfe; }
    .tag-inferred   { background:#854d0e; color:#fef9c3; }
    .tag-ai         { background:#6b21a8; color:#f3e8ff; }
    .tag-simulated  { background:#7c3aed; color:#ede9fe; }
    .tag-recommended{ background:#155e75; color:#cffafe; }
    /* Business Pulse cards */
    .pulse-card {
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 10px;
        color: #f1f3f5;
    }
    .pulse-critical { background:rgba(220,53,69,0.18); border-left:4px solid #f03e3e; }
    .pulse-warn     { background:rgba(255,152,0,0.18); border-left:4px solid #ff9800; }
    .pulse-monitor  { background:rgba(21,101,192,0.18); border-left:4px solid #4dabf7; }
    .pulse-healthy  { background:rgba(46,125,50,0.18); border-left:4px solid #51cf66; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def tag(label, kind):
    kinds = {
        'observed': 'observed', 'calc': 'calc', 'inferred': 'inferred',
        'ai': 'ai', 'simulated': 'simulated', 'recommended': 'recommended'
    }
    cls = kinds.get(kind, 'calc')
    icons = {
        'observed': '🟢', 'calc': '🔵', 'inferred': '🟡', 
        'ai': '🟣', 'simulated': '🟠', 'recommended': '🔵'
    }
    return f'<span class="tag tag-{cls}">{icons.get(kind,"")} {label}</span>'

def fmt_inr(v):
    if abs(v) >= 1e7:
        return f"₹{v/1e7:.2f} Cr"
    elif abs(v) >= 1e5:
        return f"₹{v/1e5:.1f} L"
    else:
        return f"₹{v:,.0f}"

# ── Session state ─────────────────────────────────────────────────────────────
if 'investigation' not in st.session_state:
    st.session_state.investigation = None

# ── DB Connection ─────────────────────────────────────────────────────────────
def get_db_conn():
    return create_connection()

conn = get_db_conn()

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
st.sidebar.title("🔐 Role & Settings")
role_labels = {
    "executive": "👔 C-Level Executive (All Regions)",
    "regional_manager_south": "📍 Regional Manager — South",
    "regional_manager_north": "📍 Regional Manager — North",
    "analyst": "🔍 Data Analyst (All, Read-only)"
}
selected_role = st.sidebar.selectbox(
    "Authenticated Role",
    list(role_labels.keys()),
    format_func=lambda r: role_labels.get(r, r)
)
allowed_regions = get_allowed_regions(selected_role)
st.sidebar.caption(f"✅ Authorized regions: **{', '.join(allowed_regions)}**")

st.sidebar.divider()
st.sidebar.subheader("🔎 Investigation Controls")

kpi_opts = {"revenue": "💰 Revenue", "orders": "📦 Orders", "asp": "🏷️ Avg Selling Price", "conversion_rate": "🎯 Conversion Rate"}
selected_kpi = st.sidebar.selectbox("KPI to Investigate", list(kpi_opts.keys()), format_func=lambda k: kpi_opts[k])

region_opts = ["South", "North", "East", "West"]
selected_region = st.sidebar.selectbox("Region", region_opts)

product_opts = ["XPhone Pro", "TabMax", "NovaWatch", "All Products"]
selected_product_raw = st.sidebar.selectbox("Product", product_opts)
selected_product = None if selected_product_raw == "All Products" else selected_product_raw

st.sidebar.divider()
st.sidebar.subheader("⚙️ Mode")
demo_mode = st.sidebar.toggle("🎬 Demo Mode (Offline-Safe)", value=True)
simulate_stale = st.sidebar.toggle("🕐 Simulate Stale Marketing Data", value=False)

run_btn = st.sidebar.button("🔍 Run Investigation", type="primary", use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
# 🧠 BusinessIntelligence.ai
### *From dashboards to decisions.*
""")
st.caption("Detect → Prioritize → Investigate → Evidence → Confidence → Recommend → Act → Learn")
st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════════════════
tab_pulse, tab_investigate, tab_security, tab_lineage, tab_outcomes = st.tabs([
    "📊 Business Pulse",
    "🔬 Investigation",
    "🔐 Security Check",
    "📐 Data Lineage",
    "📈 Outcomes & Feedback"
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: BUSINESS PULSE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_pulse:
    st.subheader("📊 Business Pulse — What should I care about right now?")
    
    freshness = get_stale_source_freshness() if simulate_stale else get_source_freshness()
    
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    kpi_cols = [col_kpi1, col_kpi2, col_kpi3, col_kpi4]
    all_kpis = calculate_all_kpis(conn, allowed_regions)
    
    for i, kpi_data in enumerate(all_kpis):
        kpi_name = kpi_data['kpi_name']
        with kpi_cols[i % 4]:
            chg = kpi_data['change_pct']
            arrow = "🔺" if chg > 0 else "🔻"
            color = "normal" if abs(chg) <= kpi_data['threshold'] else ("inverse" if chg < 0 else "normal")
            delta_color = "normal" if chg >= 0 else "inverse"
            
            if kpi_name in ['revenue', 'asp']:
                val_str = fmt_inr(kpi_data['current_value'])
            elif kpi_name == 'conversion_rate':
                val_str = f"{kpi_data['current_value']*100:.2f}%"
            else:
                val_str = f"{kpi_data['current_value']:,.0f}"
                
            st.metric(
                label=kpi_data['definition'],
                value=val_str,
                delta=f"{chg:+.1f}%",
                delta_color=delta_color
            )

    st.divider()
    
    # Priority alerts
    alerts = detect_anomalies(conn, allowed_regions)
    
    col_attn, col_healthy = st.columns(2)
    
    with col_attn:
        st.markdown("#### 🔴 Requires Attention")
        critical_alerts = [a for a in alerts if a.get('is_significant') and a.get('change_pct', 0) < 0]
        
        if not critical_alerts:
            st.success("✅ No critical anomalies detected.")
        else:
            for alert in critical_alerts:
                chg = alert['change_pct']
                impact = calculate_impact_score(alert['kpi_name'], chg, alert['current_value'], alert['previous_value'], 80.0)
                cat = impact['impact_category']
                pulse_cls = "pulse-critical" if cat == "HIGH" else "pulse-warn"
                
                # Suggest next step based on severity
                if cat == "HIGH":
                    next_step = "🔍 Investigate immediately"
                    urgency_emoji = "🔴"
                else:
                    next_step = "🟠 Investigate when available"
                    urgency_emoji = "🟠"
                    
                st.markdown(f"""
<div class="pulse-card {pulse_cls}">
  {urgency_emoji} <strong>{alert['kpi_name'].upper()}</strong> &nbsp;
  {tag('Observed', 'observed')} {tag('Calculated', 'calc')} <br>
  Movement: <strong>{chg:+.1f}%</strong> &nbsp;|&nbsp; Impact: <strong>{cat}</strong><br>
  Exposure: <em>{fmt_inr(impact['exposure_monthly'])}/month</em><br>
  Confidence: <em>~80%</em> &nbsp;|&nbsp; Region: <em>{alert.get('region','All')}</em><br>
  <small>Next step: {next_step}</small>
</div>
""", unsafe_allow_html=True)

    with col_healthy:
        st.markdown("#### 🟢 Performing Well")
        healthy_alerts = [a for a in alerts if not a.get('is_significant')]
        if not healthy_alerts:
            st.info("All KPIs show movement above threshold.")
        for alert in healthy_alerts:
            st.markdown(f"""
<div class="pulse-card pulse-healthy">
  🟢 <strong>{alert['kpi_name'].upper()}</strong> &nbsp; {tag('Observed','observed')} <br>
  Change: <strong>{alert['change_pct']:+.1f}%</strong> — Within threshold ({alert['threshold']}%)
</div>
""", unsafe_allow_html=True)

    st.divider()
    st.subheader("📡 Data Source Freshness")
    
    source_cols = st.columns(len(freshness))
    for i, (src, meta) in enumerate(freshness.items()):
        with source_cols[i]:
            status_icon = "🔴" if meta['is_stale'] else "🟢"
            label = f"{status_icon} {src.capitalize()}"
            conf_penalty = "−15% confidence" if meta['is_stale'] else "No confidence penalty"
            st.metric(label=label, value=meta.get('display_age', meta.get('display', 'Unknown')),
                      delta=conf_penalty, delta_color="inverse" if meta['is_stale'] else "off")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2: INVESTIGATION
# ═══════════════════════════════════════════════════════════════════════════════
with tab_investigate:
    # Run investigation on button click
    if run_btn:
        with st.spinner(f"🔬 Running {kpi_opts[selected_kpi]} investigation for {selected_region}…"):
            telemetry = TelemetryTracker()
            result = run_investigation(
                conn, selected_kpi, selected_region, selected_product,
                selected_role, simulate_stale=simulate_stale,
                is_demo=demo_mode, telemetry=telemetry
            )
            st.session_state.investigation = result
            st.session_state.telemetry = telemetry
            
    inv = st.session_state.get('investigation')
    
    if inv is None:
        st.info("👈 Configure the investigation controls in the sidebar and click **Run Investigation**.")
        st.markdown("""
---
**How to use this product:**
```
WHAT?         →  Business Pulse shows metric movement
WHY?          →  Driver breakdown via variance decomposition
EVIDENCE?     →  Semantic match from support, marketing, competitor logs
HOW CONFIDENT →  5-pillar confidence score with stale/contradiction penalties
WHAT TO DO?   →  Guardrailed, prioritised action recommendations
WHAT HAPPENED →  Outcome Feedback tab tracks decision outcomes
```
""")
    elif 'error' in inv:
        # Security block
        st.error(f"🛑 **ACCESS DENIED**")
        st.markdown(f"```\n{inv['error']}\n```")
        st.markdown("**Database query: NOT EXECUTED**")
        if inv.get('decision_trace'):
            with st.expander("Decision Trace"):
                for step in inv['decision_trace']:
                    st.text(step)
    else:
        kpi_info = inv['kpi']
        anomaly = inv['anomaly']
        drivers = inv['drivers']
        evidence = inv['evidence']
        conf = inv['confidence']
        impact = inv['impact']
        recs = inv['recommendations']
        is_demo = inv.get('is_demo', False)
        
        if is_demo:
            st.info("🎬 **Demo Mode Active** — Results are deterministic and offline-safe.")
            
        # ── Abstention UX ──
        if anomaly.get('sparse_history'):
            st.warning(f"""
⚠️ **INSUFFICIENT EVIDENCE — Attribution Halted**

**{selected_product}** has only **{anomaly['days_of_history']} days** of historical data.  
The system requires at least **14 days** to perform reliable driver attribution.

> *Generating explanations on sparse data is statistically invalid. The system will not guess.*
""")
            st.info("**What would enable analysis:** Collect more daily sales data (>14 days)")
            st.stop()
            
        # ── WHAT? – KPI Movement ──
        st.subheader(f"WHAT? — {kpi_info.get('definition','KPI')} Movement")
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
        chg_pct = kpi_info['change_pct']
        
        with kpi_col1:
            st.metric("Current Period", fmt_inr(kpi_info['current_value']) if selected_kpi in ['revenue','asp'] else f"{kpi_info['current_value']:,.2f}")
        with kpi_col2:
            st.metric("Previous Period", fmt_inr(kpi_info['previous_value']) if selected_kpi in ['revenue','asp'] else f"{kpi_info['previous_value']:,.2f}")
        with kpi_col3:
            st.metric("Change %", f"{chg_pct:+.1f}%", delta_color="normal" if chg_pct >= 0 else "inverse")
        with kpi_col4:
            sig_label = "⚠️ SIGNIFICANT" if anomaly['is_significant'] else "✅ NORMAL"
            st.metric("Anomaly Status", sig_label)
            
        st.markdown(f"{tag('Observed data from sales.csv', 'observed')} {tag('Calculated period comparison', 'calc')}", unsafe_allow_html=True)
        
        st.divider()
        
        # ── WHY? – Driver Tree ──
        st.subheader("WHY? — Driver Contribution Breakdown")
        st.markdown(f"{tag('Calculated via variance decomposition (Price × Volume)', 'calc')}", unsafe_allow_html=True)
        
        if drivers:
            driver_data = pd.DataFrame(drivers)
            driver_data['color'] = driver_data['direction'].map({'negative': '#dc3545', 'positive': '#28a745'})
            
            fig_drivers = px.bar(
                driver_data, x='contribution_pct', y='driver_name',
                orientation='h',
                color='direction',
                color_discrete_map={'negative': '#dc3545', 'positive': '#28a745'},
                title=f"Driver Contribution to {kpi_info.get('definition','KPI')} Change",
                labels={'contribution_pct': 'Contribution (%)', 'driver_name': 'Driver'}
            )
            fig_drivers.update_layout(showlegend=True, height=300, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig_drivers, use_container_width=True)
            
            # ASCII tree for judge clarity
            tree_lines = [f"  {'KPI':^30} ({chg_pct:+.1f}%)", "       │"]
            for i, d in enumerate(drivers):
                connector = "└──" if i == len(drivers) - 1 else "├──"
                direction_icon = "↓" if d['direction'] == 'negative' else "↑"
                tree_lines.append(f"       {connector} {d['driver_name']}: {direction_icon}{d['contribution_pct']:.1f}%")
            with st.expander("📊 Driver Tree (ASCII)"):
                st.code("\n".join(tree_lines))
        else:
            st.info("No drivers computed — insufficient data.")
            
        st.divider()
        
        # ── EVIDENCE? ──
        st.subheader("EVIDENCE? — Supporting & Contradicting Observations")
        
        ev_tab1, ev_tab2 = st.tabs(["✅ Supporting Evidence", "⚠️ Contradicting Evidence"])
        
        with ev_tab1:
            SKIP = {'coverage', 'contradicting'}
            any_ev = False
            for src_key, ev_list in evidence.items():
                if src_key in SKIP or not isinstance(ev_list, list) or not ev_list:
                    continue
                any_ev = True
                st.markdown(f"**{src_key.capitalize()} Records** {tag('Observed','observed')}")
                for ev in ev_list[:4]:
                    score = ev.get('relevance_score', 0)
                    score_bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
                    st.markdown(f"""
<div class="evidence-card">
  📅 {ev['date']} &nbsp;|&nbsp; {ev.get('region','')} &nbsp;|&nbsp; Relevance: <code>{score:.2f}</code> [{score_bar}]<br>
  <em>{ev['detail']}</em><br>
  <small>Why relevant: {ev.get('why_relevant','')}</small>
</div>
""", unsafe_allow_html=True)
                    
            # Evidence coverage
            coverage = evidence.get('coverage', {})
            cov_score = coverage.get('score', 0)
            st.markdown(f"**Evidence Coverage: {cov_score}%** {tag('Calculated','calc')}")
            
            prog_color = "normal" if cov_score >= 70 else ("off" if cov_score >= 50 else "inverse")
            st.progress(cov_score / 100)
            
            checklist = coverage.get('checklist', [])
            if checklist:
                with st.expander("Coverage Checklist"):
                    for item in checklist:
                        status = "✅" if item['available'] else "❌"
                        st.markdown(f"{status} **{item['driver']}** — {item['source']}")
                        
            if not any_ev:
                st.info("No supporting evidence found.")
                
        with ev_tab2:
            contradictions = evidence.get('contradicting', [])
            if not contradictions:
                st.success("✅ **No contradictions detected.** All signals consistently support the driver breakdown.")
            else:
                st.warning(f"⚠️ **{len(contradictions)} contradicting signals detected** — Confidence score penalised accordingly.")
                for c in contradictions:
                    st.markdown(f"""
<div class="evidence-card contradict">
  📅 {c.get('date','')} &nbsp;|&nbsp; Source: {c.get('source','')}<br>
  <em>{c['detail']}</em><br>
  <small>Why contradictory: {c.get('why_contradictory','')}</small>
</div>
""", unsafe_allow_html=True)
                    
        st.divider()
        
        # ── HOW CONFIDENT? ──
        st.subheader("HOW CONFIDENT? — System Confidence Score")
        st.markdown(f"{tag('Calculated from data quality, coverage, driver agreement, evidence, attribution','calc')}", unsafe_allow_html=True)
        
        conf_score = conf['score']
        conf_level = conf['level']
        conf_color = "#28a745" if conf_score >= 80 else ("#ff9800" if conf_score >= 55 else "#dc3545")
        
        col_gauge, col_breakdown = st.columns([1, 2])
        with col_gauge:
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=conf_score,
                title={'text': f"Confidence ({conf_level})", 'font': {'size': 14}},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': conf_color},
                    'steps': [
                        {'range': [0, 50], 'color': '#fff5f5'},
                        {'range': [50, 75], 'color': '#fff8e1'},
                        {'range': [75, 100], 'color': '#f0fff4'}
                    ],
                    'threshold': {'line': {'color': 'black', 'width': 2}, 'value': 75}
                }
            ))
            fig_gauge.update_layout(height=220, margin=dict(l=20, r=20, t=30, b=0))
            st.plotly_chart(fig_gauge, use_container_width=True)
            
        with col_breakdown:
            breakdown = conf.get('breakdown', {})
            if breakdown:
                bd_df = pd.DataFrame([
                    {'Pillar': k.replace('_',' ').title(), 'Score': v}
                    for k, v in breakdown.items()
                ])
                st.dataframe(bd_df, use_container_width=True, hide_index=True)
            st.caption(f"**Reasoning:** {conf.get('reason','')}")
            if inv.get('warnings'):
                for w in inv['warnings']:
                    st.warning(f"⚠️ {w}")
                    
        st.divider()
        
        # ── WHAT TO DO? – Recommendations ──
        st.subheader("WHAT SHOULD I DO? — Recommended Actions")
        st.markdown(f"{tag('Recommended actions','recommended')} — Generated by deterministic rule engine. LLM adds tone only.", unsafe_allow_html=True)
        
        for i, rec in enumerate(recs, 1):
            priority_icon = {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟡"}.get(rec['priority'], "⚪")
            with st.expander(f"{priority_icon} Action {i}: {rec['action'][:80]}…", expanded=(i == 1)):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Action:** {rec['action']}")
                    st.markdown(f"**Reason:** {tag('Inferred','inferred')} {rec['reason']}", unsafe_allow_html=True)
                    st.markdown(f"**Driver:** {rec['driver']}")
                with c2:
                    st.markdown(f"**Priority:** {priority_icon} {rec['priority']}")
                    st.markdown(f"**Confidence:** {rec['confidence']}")
                    st.markdown(f"**Expected Impact:** {tag('Estimated','simulated')} {rec['expected_impact']}", unsafe_allow_html=True)
                    st.markdown(f"**Risk / Caveat:** ⚠️ {rec.get('risk_caveat','N/A')}")
                    
                ev_key = rec.get('driver','').lower()
                st.markdown(f"**Supporting Evidence:** {tag('Observed','observed')} {rec['supporting_evidence']}", unsafe_allow_html=True)
                
                fb_col1, fb_col2 = st.columns(2)
                with fb_col1:
                    if st.button(f"✅ Accept", key=f"accept_{i}"):
                        save_feedback(f"{selected_kpi} ({selected_region})", rec['action'], "thumbs_up", "accepted")
                        st.success("Recorded: Accepted")
                with fb_col2:
                    if st.button(f"❌ Reject", key=f"reject_{i}"):
                        save_feedback(f"{selected_kpi} ({selected_region})", rec['action'], "thumbs_down", "rejected")
                        st.error("Recorded: Rejected")
                        
        st.divider()
        
        # ── WHAT WOULD CHANGE MY MIND? ──
        st.subheader("🤔 What Would Change This Conclusion?")
        st.markdown(f"{tag('Inferred from current evidence limits','inferred')}", unsafe_allow_html=True)
        what_change = inv.get('what_change_mind', [])
        if what_change:
            for item in what_change:
                st.markdown(f"- {item}")
        else:
            st.info("No specific reversal conditions identified.")
            
        st.divider()
        
        # ── AI NARRATIVE ──
        st.subheader("🟣 AI Narrative (Role-Adapted)")
        st.markdown(f"{tag('AI Narration — Gemini', 'ai')} — *Tone adapted per role. Analytics NOT computed by LLM.*", unsafe_allow_html=True)
        
        narrative_obj = inv.get('narrative')
        if narrative_obj and isinstance(narrative_obj, dict):
            llm_result = narrative_obj
        else:
            from llm.narrative import generate_narrative
            llm_result = generate_narrative(
                kpi_info, {'drivers': drivers, 'confidence': conf}, recs, evidence,
                persona=inv.get('persona', 'executive')
            )
        st.markdown(llm_result.get('narrative', 'Narrative unavailable.'))
        
        # LLM transparency section
        with st.expander("🔍 AI Generation Transparency"):
            llm_info = get_llm_vs_non_llm_breakdown()
            st.markdown(f"""
**LLM Used:** {llm_result.get('model', 'Gemini 2.0 Flash')}  
**LLM Purpose:** Narrative synthesis and role-specific explanation  
**LLM Input:** KPI results, driver calculations, evidence, confidence score, persona

**The LLM did NOT calculate:**
- ✅ KPI values (DuckDB SQL)
- ✅ Driver contributions (Variance decomposition)
- ✅ Confidence score (5-pillar weighted formula)
- ✅ Business impact exposure (Impact calculator)
- ✅ Access permissions (RBAC authorization module)
- ✅ Recommendations (Rule-based guardrail engine)
""")

        st.divider()
        
        # ── DECISION TRACE ──
        with st.expander("📋 Full Decision Trace — Why did the system reach this conclusion?"):
            st.markdown(f"{tag('System Trace','calc')}", unsafe_allow_html=True)
            for step in inv.get('decision_trace', []):
                st.markdown(f"`{step}`")
                
        # ── WHAT-IF SIMULATOR ──
        st.divider()
        st.subheader("🟡 What-If Scenario Simulator")
        st.markdown(f"{tag('Simulated Scenario — not causal inference', 'simulated')} — Estimated recovery only.", unsafe_allow_html=True)
        
        if drivers:
            sim_driver = st.selectbox("Adjust driver", [d['driver_name'] for d in drivers], key="sim_driver_sel")
            sel_driver_obj = next((d for d in drivers if d['driver_name'] == sim_driver), None)
            
            if sel_driver_obj:
                orig_impact = -sel_driver_obj['contribution_pct'] * (abs(chg_pct) / 100.0) * 10  # rough scale
                proposed_impact = st.slider(
                    f"Proposed {sim_driver} improvement (%)", 
                    min_value=float(orig_impact), max_value=0.0, value=float(orig_impact / 2),
                    step=0.5, key="what_if_slider"
                )
                
                sim_res = run_what_if_simulation(
                    selected_kpi, selected_region, selected_product or 'All',
                    sim_driver, orig_impact, proposed_impact,
                    kpi_info['current_value']
                )
                
                col_s1, col_s2, col_s3 = st.columns(3)
                with col_s1:
                    st.metric("Estimated KPI Recovery", f"+{sim_res['estimated_kpi_recovery_pct']:.1f}%")
                with col_s2:
                    st.metric("Estimated Monthly Recovery", fmt_inr(sim_res['estimated_recovery_monthly']))
                with col_s3:
                    st.metric("Simulation Confidence", sim_res['confidence'])
                    
                st.caption(f"🟡 {sim_res['label']} — {sim_res['model_description']}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3: SECURITY CHECK
# ═══════════════════════════════════════════════════════════════════════════════
with tab_security:
    st.subheader("🔐 Role-Based Access Control (RBAC)")
    st.markdown("Authorization is enforced **before** the database query is constructed — not post-filtering.")
    
    sec_col1, sec_col2 = st.columns(2)
    
    with sec_col1:
        st.markdown("**Your Role**")
        role_info = ROLES.get(selected_role, {})
        st.json({
            "role": selected_role,
            "level": role_info.get('level', '?'),
            "authorized_regions": allowed_regions,
            "accessible_kpis": role_info.get('kpis', [])
        })
        
    with sec_col2:
        st.markdown("**Live Authorization Test**")
        test_region = st.selectbox("Test access to region", ["North", "South", "East", "West"], key="sec_test_region")
        test_kpi = st.selectbox("For KPI", list(kpi_opts.keys()), format_func=lambda k: kpi_opts[k], key="sec_test_kpi")
        
        if st.button("🔐 Test Authorization", type="primary"):
            from security.authorization import authorize
            is_auth, msg, authed = authorize(selected_role, [test_region], test_kpi)
            if is_auth:
                st.success(f"✅ **ACCESS GRANTED** — Regions authorized: {authed}")
                st.caption("DuckDB query will be constructed with region filter.")
            else:
                st.error(f"🛑 **ACCESS DENIED**")
                st.code(msg)
                st.markdown("**Database query: NOT EXECUTED**")
                
    st.divider()
    st.subheader("RBAC Policy Map")
    policy_data = []
    for role_key, rinfo in ROLES.items():
        policy_data.append({
            'Role': role_key,
            'Level': rinfo.get('level','?'),
            'Regions': ', '.join(rinfo.get('regions', [])),
            'KPIs': ', '.join(rinfo.get('kpis', []))
        })
    st.dataframe(pd.DataFrame(policy_data), use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4: DATA LINEAGE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_lineage:
    st.subheader("📐 Semantic Contract & Data Lineage")
    
    valid, errors = validate_semantic_contract()
    if valid:
        st.success("✅ Semantic contract validation passed — All KPI definitions, drivers, and access policies are consistent.")
    else:
        for e in errors:
            st.error(f"❌ {e}")
            
    kpi_defs = load_kpi_definitions()
    freshness_data = get_stale_source_freshness() if simulate_stale else get_source_freshness()
    
    for kpi_name, kpi_def in kpi_defs.items():
        with st.expander(f"📌 {kpi_name.upper()} — {kpi_def.get('definition','')}"):
            c1, c2 = st.columns(2)
            with c1:
                src = kpi_def.get('source', '?')
                if isinstance(src, list):
                    src_str = " + ".join([f"`{s}.csv`" for s in src])
                    is_stale = any(freshness_data.get(s, {}).get('is_stale', False) for s in src)
                    freshness_str = ", ".join([f"{s}: {freshness_data.get(s, {}).get('display_age', freshness_data.get(s, {}).get('display', 'Unknown'))}" for s in src])
                else:
                    src_str = f"`{src}.csv`"
                    src_freshness = freshness_data.get(src, {})
                    is_stale = src_freshness.get('is_stale', False)
                    freshness_str = src_freshness.get('display_age', src_freshness.get('display', 'Unknown'))
                
                st.markdown(f"""
| Field | Value |
|---|---|
| **Definition** | {kpi_def.get('definition','')} |
| **Formula** | `{kpi_def.get('formula','')}` |
| **Source** | {src_str} |
| **Threshold** | {kpi_def.get('threshold',0)}% |
| **Freshness** | {"🔴 " if is_stale else "🟢 "}{freshness_str} |
""")
            with c2:
                drivers = kpi_def.get('drivers', [])
                st.markdown("**Drivers:**")
                for d in drivers:
                    st.markdown(f"- `{d['name']}` — {d['description']} *(from {d['data_source']}.csv)*")
                    
                access = kpi_def.get('access', {})
                st.markdown("**Access Policy:**")
                for role, scope in access.items():
                    st.markdown(f"- **{role}**: {scope}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5: OUTCOMES & FEEDBACK
# ═══════════════════════════════════════════════════════════════════════════════
with tab_outcomes:
    st.subheader("📈 Outcome Feedback Dashboard")
    st.caption("Tracks accepted/rejected recommendations. Labelled **Outcome Feedback** — not online learning.")
    
    metrics = load_feedback_metrics()
    
    if not metrics or metrics.get('total_recommendations', 0) == 0:
        st.info("No outcome feedback recorded yet. Accept or reject a recommendation in the Investigation tab.")
    else:
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Recommendations Issued", metrics.get('total_recommendations', 0))
        with m2:
            st.metric("Accepted", metrics.get('accepted', 0))
        with m3:
            st.metric("Rejected", metrics.get('rejected', 0))
        with m4:
            acc_rate = metrics.get('acceptance_rate', 0)
            st.metric("Acceptance Rate", f"{acc_rate:.0f}%")
            
        st.divider()
        
        recent = metrics.get('recent_feedback', [])
        if recent:
            st.subheader("Recent Feedback Log")
            fb_df = pd.DataFrame(recent)
            st.dataframe(fb_df, use_container_width=True, hide_index=True)
            
    st.divider()
    st.subheader("🔬 Performance Telemetry")
    tel = st.session_state.get('telemetry')
    if tel:
        summary = tel.get_summary()
        t1, t2, t3 = st.columns(3)
        with t1:
            st.metric("Total Latency", f"{summary.get('total_ms',0):.0f} ms")
        with t2:
            st.metric("LLM Calls", summary.get('llm_calls', 0))
        with t3:
            st.metric("Steps", summary.get('step_count', 0))
            
        steps_df = pd.DataFrame(summary.get('steps', []))
        if not steps_df.empty:
            st.dataframe(steps_df, use_container_width=True, hide_index=True)
    else:
        st.info("Run an investigation to see performance metrics.")
