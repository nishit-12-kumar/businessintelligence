"""Backend service adapter for BusinessIntelligence.ai.

Bridges the Flask presentation and API layer with the latest decision intelligence backend:
- DuckDB KPI calculation engine (including Inventory Stockout Rate)
- Anomaly & sparse-history detector
- Variance decomposition & driver analysis
- Statistical Hypothesis Testing & Empirical Correlation Engine
- Business Knowledge Graph Ontology Traversal (Wikidata API curation)
- External Competitor & E-Commerce Pricing REST API
- External Database Connector (SQLite, DuckDB, PostgreSQL, MySQL, Snowflake)
- ReportLab Technical PDF Report Generator
- Evidence retriever (TF-IDF & Embeddings, Contradictions, Coverage)
- Hybrid Confidence Engine (45% Stat, 20% KG, 35% AI) & Sanity Check
- Financial impact & business exposure calculator
- Guardrailed recommendation engine with Structured Action Schema
- What-if scenario simulator
- Pre-query RBAC authorization enforcement (7 role tiers including ops_lead)
- Semantic contract validator & data lineage
- Outcome feedback & runtime telemetry tracker with LLM Economics
- Role-adapted LLM narrative generator
"""
from __future__ import annotations
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Apply SSL patch for Windows certificate store compatibility
try:
    import ssl_patch
except ImportError:
    pass

from analytics.kpi_engine import (
    create_connection, calculate_kpi, calculate_all_kpis,
    load_kpi_definitions, get_date_periods
)
from analytics.anomaly_detection import detect_anomalies, check_sparse_history, get_alert_severity
from analytics.driver_analysis import analyze_drivers, analyze_revenue_drivers
from analytics.statistical_confidence import run_hypothesis_test, evaluate_driver_hypothesis
from semantic.knowledge_graph import knowledge_graph, BusinessKnowledgeGraph
from data.external_db_connector import ExternalDBConnector
from retrieval.external_pricing_api import fetch_external_competitor_pricing
from analytics.impact_calculator import calculate_impact_score
from analytics.investigation_engine import run_investigation as orchestrate_investigation
from analytics.recommendation_engine import generate_recommendations
from analytics.simulator import run_what_if_simulation
from analytics.feedback_loop import load_feedback_metrics, save_feedback
from security.authorization import authorize, get_allowed_regions, ROLES, get_available_roles
from monitoring.telemetry import (
    TelemetryTracker, get_source_freshness, get_stale_source_freshness
)
from semantic.validator import validate_semantic_contract
from retrieval.retriever import get_all_evidence, get_contradicting_evidence, calculate_evidence_coverage
from llm.narrative import generate_narrative, get_llm_vs_non_llm_breakdown

try:
    from generate_pdf_report import create_pdf
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


@dataclass
class BackendContext:
    demo: bool
    roles: Dict[str, Any]


def build_context() -> BackendContext:
    """Initialize backend context with registered roles."""
    return BackendContext(demo=False, roles=ROLES)


def get_roles(ctx: BackendContext) -> Dict[str, Any]:
    """Return all available RBAC roles and metadata (including ops_lead and analyst)."""
    roles_dict = {}
    for role_id, info in ROLES.items():
        scope_str = ", ".join(info.get("regions", []))
        level_str = info.get("level", "standard").capitalize()
        roles_dict[role_id] = {
            "label": info.get("display_name", role_id),
            "level": level_str,
            "scope": f"{scope_str} ({level_str})",
            "regions": info.get("regions", []),
            "description": info.get("description", ""),
            "kpis": ["revenue", "orders", "asp", "conversion_rate", "inventory_stockout_rate"]
        }
    return roles_dict


def get_pulse(ctx: BackendContext, role: str, stale: bool = False) -> Dict[str, Any]:
    """Calculate the Business Pulse dashboard metrics, alerts, and data freshness across all 5 KPIs."""
    allowed_regions = get_allowed_regions(role)
    conn = create_connection()
    
    try:
        raw_kpis = calculate_all_kpis(conn, allowed_regions)
        freshness = get_stale_source_freshness() if stale else get_source_freshness()
        raw_alerts = detect_anomalies(conn, allowed_regions)
        
        pulse = []
        for kpi in raw_kpis:
            chg = kpi.get("change_pct", 0.0)
            threshold = kpi.get("threshold", 5.0)
            status = "critical" if chg < -threshold else ("watch" if abs(chg) >= threshold else "healthy")
            
            # Format value based on KPI type
            curr_val = kpi.get("current_value", 0.0)
            kpi_name = kpi.get("kpi_name", "revenue")
            if kpi_name in ("revenue", "asp"):
                if curr_val >= 1e7:
                    val_str = f"₹{curr_val / 1e7:.2f} Cr"
                elif curr_val >= 1e5:
                    val_str = f"₹{curr_val / 1e5:.1f} L"
                else:
                    val_str = f"₹{curr_val:,.0f}"
            elif kpi_name == "conversion_rate":
                # kpi_engine returns a raw decimal ratio (e.g. 0.031 = 3.1%)
                val_str = f"{curr_val * 100:.2f}%"
            elif kpi_name == "inventory_stockout_rate":
                # kpi_engine SQL already multiplies by 100 (SUM(stockout_events)*100/COUNT)
                val_str = f"{curr_val:.2f}%"
            else:
                val_str = f"{curr_val:,.0f}"
                
            pulse.append({
                "name": kpi_name.upper() if len(kpi_name) <= 3 else kpi_name.replace("_", " ").title(),
                "kpi_name": kpi_name,
                "definition": kpi.get("definition", kpi_name),
                "formula": kpi.get("formula", ""),
                "value": val_str,
                "current_value": curr_val,
                "previous_value": kpi.get("previous_value", 0.0),
                "change": chg,
                "threshold": threshold,
                "is_significant": kpi.get("is_significant", False),
                "status": status,
                "meta": f"vs prior 7d (threshold {threshold}%)"
            })
            
        alerts = []
        healthy = []
        for a in raw_alerts:
            chg = a.get("change_pct", 0.0)
            is_sig = a.get("is_significant", False)
            kname = a.get("kpi_name", "revenue")
            reg = a.get("region", "All")
            prod = a.get("product", "All")
            
            if is_sig and chg < 0:
                impact = calculate_impact_score(
                    kname, chg, a.get("current_value", 0.0), a.get("previous_value", 0.0), 80.0
                )
                cat = impact.get("impact_category", "HIGH")
                exp = impact.get("exposure_monthly", 0.0)
                if exp >= 1e7:
                    exp_str = f"₹{exp / 1e7:.2f} Cr / month"
                elif exp >= 1e5:
                    exp_str = f"₹{exp / 1e5:.1f} L / month"
                else:
                    exp_str = f"₹{exp:,.0f} / month"
                    
                alerts.append({
                    "severity": "critical" if cat == "HIGH" else "watch",
                    "kpi": kname.upper() if len(kname) <= 3 else kname.replace("_", " ").title(),
                    "kpi_name": kname,
                    "region": reg,
                    "product": prod,
                    "change": chg,
                    "impact": cat,
                    "exposure": exp_str,
                    "exposure_raw": exp,
                    "confidence": "80%",
                    "next": "Investigate immediately" if cat == "HIGH" else "Investigate when available",
                    "sparse_history": a.get("sparse_history", False),
                    "days_of_history": a.get("days_of_history", 0)
                })
            elif not is_sig:
                healthy.append({
                    "kpi": kname.upper() if len(kname) <= 3 else kname.replace("_", " ").title(),
                    "kpi_name": kname,
                    "region": reg,
                    "product": prod,
                    "change": chg,
                    "threshold": a.get("threshold", 5.0)
                })
                
        return {
            "pulse": pulse,
            "alerts": alerts[:8],
            "healthy": healthy[:6],
            "freshness": freshness,
            "demo": False,
            "role": role,
            "allowed_regions": allowed_regions
        }
    finally:
        conn.close()


def run_investigation(ctx: BackendContext, payload: dict) -> Tuple[Dict[str, Any], Optional[TelemetryTracker]]:
    """Run complete decision intelligence pipeline through the orchestrator.
    
    Includes Statistical Hypothesis Testing, Knowledge Graph weightage,
    external competitor pricing benchmark, and structured action schemas.
    """
    role = payload.get("role", "executive")
    kpi = payload.get("kpi", "revenue")
    region = payload.get("region", "South")
    product_raw = payload.get("product", "All Products")
    product = None if product_raw in ("All Products", "All", "", None) else product_raw
    stale = bool(payload.get("stale", False))
    demo = bool(payload.get("demo", False))
    
    telemetry = TelemetryTracker()
    conn = create_connection()
    
    try:
        result = orchestrate_investigation(
            conn=conn,
            kpi_name=kpi,
            region=region,
            product=product,
            user_role=role,
            simulate_stale=stale,
            is_demo=demo,
            telemetry=telemetry
        )
        
        # Attach external competitor pricing benchmark
        pricing_bench = fetch_external_competitor_pricing(product or "XPhone Pro")
        result["external_pricing"] = pricing_bench
        
        return result, telemetry
    finally:
        conn.close()


def fetch_pricing_benchmark(product_name: str) -> Dict[str, Any]:
    """Fetch external competitor pricing benchmark."""
    return fetch_external_competitor_pricing(product_name or "XPhone Pro")


def test_external_db(db_type: str, connection_string: str) -> Dict[str, Any]:
    """Test connection to external database engine."""
    return ExternalDBConnector.test_connection(db_type, connection_string)


def ingest_external_db(target_table: str, db_type: str, connection_string: str, query: str) -> Dict[str, Any]:
    """Ingest remote database query into DuckDB analytical memory."""
    conn = create_connection()
    try:
        res = ExternalDBConnector.import_external_data(
            main_conn=conn,
            target_table=target_table,
            db_type=db_type,
            connection_string=connection_string,
            query=query
        )
        return res
    finally:
        conn.close()


def generate_pdf_report_file() -> str:
    """Generate technical PDF report and return absolute file path."""
    if not PDF_AVAILABLE:
        raise RuntimeError("ReportLab is not installed.")
    return create_pdf()


def test_authorization(ctx: BackendContext, role: str, region: str, kpi: str) -> Dict[str, Any]:
    """Test RBAC access rules before query construction."""
    is_auth, message, allowed = authorize(role, [region], kpi)
    return {
        "authorized": is_auth,
        "message": message,
        "authorized_regions": allowed,
        "tested_role": role,
        "tested_region": region,
        "tested_kpi": kpi
    }


def simulate(ctx: BackendContext, payload: dict) -> Dict[str, Any]:
    """Run What-If scenario simulation."""
    kpi = payload.get("kpi", "revenue")
    region = payload.get("region", "South")
    product = payload.get("product") or "All Products"
    driver = payload.get("driver", "Volume")
    original_impact = float(payload.get("original_impact", -6.2))
    
    if "improvement" in payload:
        improvement = float(payload["improvement"])
        proposed_impact = min(0.0, original_impact + improvement)
    else:
        proposed_impact = float(payload.get("proposed_impact", original_impact / 2.0))
        
    current_value = float(payload.get("current_value", 4200000.0))
    
    sim_res = run_what_if_simulation(
        kpi_name=kpi,
        region=region,
        product=product,
        driver_name=driver,
        original_driver_impact=original_impact,
        proposed_driver_impact=proposed_impact,
        kpi_current_val=current_value
    )
    return sim_res


def lineage(ctx: BackendContext, stale: bool = False) -> Dict[str, Any]:
    """Return semantic contract validation, all 5 KPI definitions, and freshness."""
    valid, errors = validate_semantic_contract()
    defs = load_kpi_definitions()
    freshness = get_stale_source_freshness() if stale else get_source_freshness()
    return {
        "valid": valid,
        "errors": errors,
        "definitions": defs,
        "freshness": freshness,
        "demo": False
    }


def outcomes(ctx: BackendContext) -> Dict[str, Any]:
    """Return feedback metrics, decision history, and telemetry economics."""
    metrics = load_feedback_metrics()
    return metrics


def feedback(ctx: BackendContext, payload: dict) -> Dict[str, Any]:
    """Record recommendation feedback and update metrics."""
    insight = payload.get("context") or payload.get("insight") or "Investigation decision"
    action = payload.get("action", "")
    rating = payload.get("feedback") or payload.get("rating") or "thumbs_up"
    actioned = payload.get("status") or payload.get("actioned") or "accepted"
    outcome = payload.get("outcome", "pending")
    
    save_feedback(insight, action, rating, actioned, outcome)
    updated_metrics = load_feedback_metrics()
    return {
        "status": "recorded",
        "metrics": updated_metrics
    }
