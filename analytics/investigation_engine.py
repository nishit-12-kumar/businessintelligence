"""Central Investigation Orchestrator.

Orchestrates the complete business problem investigation pipeline:
Authorization -> KPI Calc -> Anomaly Check -> Driver Breakdown ->
Evidence (Supporting/Contradicting) -> Confidence -> Impact -> Recommendation -> LLM Narration.
"""
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import time
import os
import duckdb

from security.authorization import authorize, ROLES
from analytics.kpi_engine import calculate_kpi, get_date_periods
from analytics.anomaly_detection import check_sparse_history, get_alert_severity
from analytics.driver_analysis import analyze_drivers
from analytics.impact_calculator import calculate_impact_score
from analytics.recommendation_engine import generate_recommendations
from retrieval.retriever import get_all_evidence, get_contradicting_evidence, calculate_evidence_coverage
from llm.narrative import generate_narrative
from monitoring.telemetry import TelemetryTracker, get_source_freshness, get_stale_source_freshness

@dataclass
class InvestigationResult:
    kpi: Dict[str, Any]
    anomaly: Dict[str, Any]
    drivers: List[Dict[str, Any]]
    evidence: Dict[str, Any]
    confidence: Dict[str, Any]
    impact: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    persona: str
    decision_trace: List[str]
    warnings: List[str]
    is_demo: bool
    what_change_mind: List[str]
    narrative: Optional[Dict[str, Any]] = None

    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def run_investigation(conn: duckdb.DuckDBPyConnection,
                      kpi_name: str,
                      region: str,
                      product: str,
                      user_role: str,
                      simulate_stale: bool = False,
                      is_demo: bool = False,
                      telemetry: TelemetryTracker = None) -> Dict[str, Any]:
    """Runs the complete end-to-end investigation pipeline.
    
    This function is the single source of truth for all business and analytical
    metrics, consumed directly by the UI, LLM, and recommendation engine.
    """
    trace = []
    warnings = []
    
    # 1. DEMO MODE (Deterministic offline-safe flow)
    if is_demo and region == "South" and product == "XPhone Pro" and kpi_name == "revenue":
        trace.append("🎬 Running in Deterministic Demo Mode (Offline-Safe)")
        trace.append("🔐 Security validation: Executive role -> Access GRANTED (sales.csv query pre-approved)")
        trace.append("📈 Anomaly Check: Revenue dropped 12.4% vs previous period (Threshold: 5.0% -> CRITICAL)")
        trace.append("📐 Driver Decomposition: Pricing (-6.2%), Delivery issues (-3.8%), Marketing cuts (-2.4%)")
        trace.append("🔍 Evidence matching: Retrieved 1 competitor price drop, 15 logistics delay support tickets")
        trace.append("🛡️ Contradiction detection: None. All signals align.")
        trace.append("🎯 Confidence logic: 82% (High Data Freshness, strong keyword alignment)")
        trace.append("💰 Impact Calculation: Exposure ₹18.4L/month. Recovery ₹8.0L-₹12.0L/month.")
        trace.append("📋 Actions generated: Pricing review, Logistics SLA escalation, Campaign reinstation")
        trace.append("🟣 AI Synthesis: Narration tone adapted for C-Level Executive (Offline template fallback)")
        
        kpi_info = {
            'kpi_name': 'revenue',
            'definition': 'Total sales revenue',
            'formula': 'SUM(units * price)',
            'current_value': 4200000.0,
            'previous_value': 4800000.0,
            'change_pct': -12.4,
            'threshold': 5,
            'is_significant': True,
            'region': 'South',
            'product': 'XPhone Pro',
            'authorized': True
        }
        anomaly_info = {
            'is_significant': True,
            'sparse_history': False,
            'severity': 'critical',
            'days_of_history': 58,
            'warning': None
        }
        drivers_info = [
            {'driver_name': 'Competitor pricing pressure', 'contribution_pct': 50.0, 'direction': 'negative'},
            {'driver_name': 'Delivery issues', 'contribution_pct': 31.0, 'direction': 'negative'},
            {'driver_name': 'Marketing reduction', 'contribution_pct': 19.0, 'direction': 'negative'}
        ]
        evidence_info = {
            'competitor': [{
                'source': 'Competitor Events', 'date': '2026-08-20', 'region': 'South', 'product': 'XPhone Pro',
                'detail': 'TechRival reduces XPhone Pro equivalent price from ₹50,000 to ₹45,000 in South region',
                'relevance_score': 0.95, 'why_relevant': 'Direct competitor equivalent price decrease matching query'
            }],
            'support': [{
                'source': 'Support Tickets', 'date': '2026-08-24', 'region': 'South', 'product': 'XPhone Pro',
                'detail': '[HIGH] Warehouse bottleneck: delivery delay of 5 days reported in South.',
                'ticket_id': 'TCK-1002', 'issue_type': 'delivery_delay', 'relevance_score': 0.85,
                'why_relevant': 'Explicit shipping bottleneck complaint matching driver'
            }],
            'marketing': [{
                'source': 'Marketing Data', 'date': '2026-08-24', 'region': 'South', 'product': 'XPhone Pro',
                'detail': 'Spend cut by 35% (from ₹500,000 to ₹325,000), click acquisition rates dropped.',
                'relevance_score': 1.0, 'why_relevant': 'Direct campaign spend change record'
            }],
            'contradicting': [],
            'coverage': {'score': 78, 'checklist': [
                {'driver': 'Competitor pricing pressure', 'source': 'Competitor pricing events', 'available': True},
                {'driver': 'Delivery issues', 'source': 'Support delay complaint tickets', 'available': True},
                {'driver': 'Marketing reduction', 'source': 'Weekly campaign spend logs', 'available': True},
                {'driver': 'Delivery issues', 'source': 'Direct client feedback transcripts', 'available': False}
            ]}
        }
        confidence_info = {
            'score': 82,
            'level': 'HIGH',
            'reason': "Confidence is high due to strong alignment across marketing spend, competitor pricing, and support tickets",
            'breakdown': {
                'data_quality': 95, 'historical_coverage': 95, 'driver_agreement': 78,
                'evidence_relevance': 84, 'attribution_certainty': 78
            }
        }
        impact_info = {
            'impact_score': 82.0,
            'impact_category': 'HIGH',
            'exposure_monthly': 1840000.0,
            'recovery_min': 800000.0,
            'recovery_max': 1200000.0,
            'exposure_type': 'Calculated Exposure',
            'observed_monetary_change': 600000.0
        }
        recs = [
            {
                'action': "Review and adjust XPhone Pro pricing model in South region to match TechRival",
                'reason': "Competitor pricing pressure accounted for 50.0% of the revenue drop.",
                'supporting_evidence': "Observed competitor price drop from ₹50,000 to ₹45,000 on Aug 20.",
                'expected_impact': "Potential recovery: ₹400,000–₹600,000/month",
                'confidence': "82%", 'priority': "HIGH", 'risk_caveat': "Matching competitor price margins will degrade short-term profitability.",
                'driver': 'Competitor pricing pressure'
            },
            {
                'action': "Re-negotiate logistics partner SLA for the South region to resolve systemic bottlenecks",
                'reason': "Logistics issues contributed 31.0% of the decline, causing customer cancellations.",
                'supporting_evidence': "Support spike of delivery complaints, sample: TCK-1002.",
                'expected_impact': "Potential recovery: ₹248,000–₹372,000/month",
                'confidence': "82%", 'priority': "HIGH", 'risk_caveat': "Contract revisions require 30-day legal review.",
                'driver': 'Delivery issues'
            }
        ]
        
        narrative_txt = (
            "## C-Suite Executive Briefing — South Region Revenue Decline\n\n"
            "South region **Revenue fell by 12.4%** (₹4.20M vs ₹4.80M) in the investigated period. "
            "Our deterministic driver analysis isolates **Competitor Pricing Pressure** (50% contribution) and "
            "**Delivery Bottlenecks** (31% contribution) as the primary causes.\n\n"
            "**Key Findings:**\n"
            "- TechRival matched prices at ₹45,000 in the South region on Aug 20, driving immediate ASP degradation.\n"
            "- Spike of 15 high-severity shipping backlog tickets logged in Bengaluru logistics hubs.\n\n"
            "**Recommended Action:** Immediately authorize local pricing match matches and initiate logistics SLA audits. "
            "Total monthly exposure is ₹18.4L, with a potential recovery of ₹8L–₹12L/month. System confidence score is **82% (HIGH)**."
        )
        
        narrative_response = {
            'narrative': narrative_txt,
            'persona': 'executive',
            'llm_used': False,
            'model': 'demo-cached',
            'abstention': False
        }
        
        what_change = [
            "Competitor pricing returns to baseline levels",
            "Warehouse deliveries recover without pricing adjustments",
            "Logistics backlogs explain a higher percentage of the drop",
            "New customer logs contradict the competitor price match hypothesis"
        ]
        
        return InvestigationResult(
            kpi=kpi_info, anomaly=anomaly_info, drivers=drivers_info,
            evidence=evidence_info, confidence=confidence_info, impact=impact_info,
            recommendations=recs, persona='executive', decision_trace=trace,
            warnings=warnings, is_demo=True, what_change_mind=what_change,
            narrative=narrative_response
        ).to_dict()

    # 2. RUN REAL PIPELINE
    if telemetry:
        telemetry.start()
        
    trace.append("🟢 Running Real-Time Analytical Pipeline")
    
    # 2.1 Security Access Interception
    trace.append("🔐 Enforcing Role-Based Access Control check prior to database access")
    is_auth, auth_msg, authed_regions = authorize(user_role, [region], kpi_name)
    
    if not is_auth:
        trace.append("🛑 Access Denied: User role is restricted from viewing the requested region")
        if telemetry:
            telemetry.record_step("Security Interceptor - Blocked")
            telemetry.end()
        return {
            'error': auth_msg,
            'decision_trace': trace,
            'is_demo': False
        }
    trace.append("✓ Access Approved. Constructing DuckDB query filter on authorized regions.")
    
    # 2.2 Calculate KPI values (Observed & Calculated)
    kpi_result = calculate_kpi(conn, kpi_name, authed_regions, region=region, product=product)
    trace.append(f"📊 Calculated KPI values: current = ₹{kpi_result['current_value']:,.2f}, previous = ₹{kpi_result['previous_value']:,.2f}")
    if telemetry:
        telemetry.record_step("Calculate KPI values")
        
    # 2.3 Anomaly Checks
    severity = get_alert_severity(kpi_result['change_pct'], kpi_result['threshold'])
    anomaly_info = {
        'is_significant': kpi_result['is_significant'],
        'sparse_history': False,
        'severity': severity,
        'days_of_history': 58,
        'warning': None
    }
    trace.append(f"✓ Anomaly detection evaluated: significance = {kpi_result['is_significant']} (severity: {severity})")
    
    # 2.4 Sparse History Check (Abstention UX)
    sparse_check = check_sparse_history(conn, product)
    if sparse_check['is_sparse']:
        trace.append("⚠️ Product has sparse baseline history (< 14 days). Halting analysis to avoid hallucination.")
        anomaly_info['sparse_history'] = True
        anomaly_info['days_of_history'] = sparse_check['days_available']
        anomaly_info['warning'] = sparse_check['warning']
        
        # Return abstention state immediately
        if telemetry:
            telemetry.record_step("Sparse history check - Stopped")
            telemetry.end()
            
        return InvestigationResult(
            kpi=kpi_result, anomaly=anomaly_info, drivers=[],
            evidence={'competitor': [], 'support': [], 'marketing': [], 'contradicting': [], 'coverage': {'score': 0, 'checklist': []}},
            confidence={'score': 20, 'level': 'LOW', 'reason': 'Insufficient baseline', 'breakdown': {}},
            impact={'impact_score': 0, 'impact_category': 'LOW', 'exposure_monthly': 0, 'recovery_min': 0, 'recovery_max': 0, 'exposure_type': 'Observed', 'observed_monetary_change': 0},
            recommendations=[{
                'action': "Continue monitoring & collect additional data",
                'reason': "Attribution halted: product has insufficient historical days.",
                'supporting_evidence': f"Observation logs: {product} has only {sparse_check['days_available']} days of history.",
                'priority': 'LOW', 'confidence': '20%', 'expected_impact': '₹0', 'risk_caveat': 'Attributing changes on shallow history is statistically invalid.',
                'driver': 'All'
            }],
            persona='executive' if ROLES[user_role]['level'] == 'executive' else 'regional_manager',
            decision_trace=trace, warnings=["Sparse historical baseline data."], is_demo=False,
            what_change_mind=["Collect more daily sales data to establish baseline (>14 days)"]
        ).to_dict()
        
    # 2.5 Driver Analysis (Calculated)
    driver_result = analyze_drivers(conn, kpi_name, region, product, authed_regions)
    driver_summary = ", ".join([f"{d['driver_name']} ({d['contribution_pct']}%)" for d in driver_result['drivers']])
    trace.append(f"📐 Decomposed drivers: {driver_summary}")
    if telemetry:
        telemetry.record_step("Decompose Drivers")
        
    # 2.6 Fetch Evidence (Observed)
    evidence = get_all_evidence(conn, region, product)
    trace.append("🔍 Matching supporting logs via semantic TF-IDF matcher")
    
    # 2.7 Contradiction Detection (Inferred/Calculated)
    contradictions = get_contradicting_evidence(conn, region, product)
    evidence['contradicting'] = contradictions
    if contradictions:
        trace.append(f"⚠️ Flagged contradicting evidence in campaigns/tickets: {len(contradictions)} conflict logs found")
    else:
        trace.append("✓ Contradiction check: None. All observations support the driver breakdown.")
        
    # 2.8 Coverage Score
    coverage = calculate_evidence_coverage(driver_result['drivers'], evidence)
    evidence['coverage'] = coverage
    trace.append(f"✓ Evidence coverage evaluated: {coverage['score']}% of required data channels are present")
    if telemetry:
        telemetry.record_step("Semantic Evidence Match & Contradictions")
        
    # 2.9 Confidence Calculation (Calculated)
    conf = driver_result['confidence']
    
    # Apply stale data penalties based on telemetry freshness
    freshness = get_stale_source_freshness() if simulate_stale else get_source_freshness()
    
    stale_penalties = 0
    if freshness['marketing']['is_stale']:
        stale_penalties += 15
        warnings.append("Stale marketing source data degraded overall confidence.")
    if freshness['competitor']['is_stale']:
        stale_penalties += 15
        warnings.append("Stale competitor pricing data degraded overall confidence.")
        
    # Apply contradiction penalties
    if contradictions:
        stale_penalties += 20
        warnings.append("Contradicting campaign CTR/sentiment logs degraded overall confidence.")
        
    conf['score'] = max(10, conf['score'] - stale_penalties)
    if conf['score'] >= 80:
        conf['level'] = 'HIGH'
    elif conf['score'] >= 55:
        conf['level'] = 'MEDIUM'
    else:
        conf['level'] = 'LOW'
        
    # Update reasoning
    if stale_penalties > 0:
        conf['reason'] = f"Confidence score reduced to {conf['score']}% due to: " + ", ".join(warnings)
    trace.append(f"🎯 Calculated confidence score: {conf['score']}% ({conf['level']})")
    
    # 2.10 Impact exposure (Calculated/Estimated)
    impact_info = calculate_impact_score(
        kpi_name, kpi_result['change_pct'], 
        kpi_result['current_value'], kpi_result['previous_value'],
        float(conf['score'])
    )
    trace.append(f"💰 Modeled business exposure: ₹{impact_info['exposure_monthly']:,.0f}/month")
    
    # 2.11 Recommendations (Guardrailed)
    persona = 'executive' if ROLES[user_role]['level'] == 'executive' else 'regional_manager'
    recs = generate_recommendations(
        driver_result['drivers'], evidence, impact_info, conf, 
        region, product, persona=persona
    )
    trace.append(f"📋 Generated {len(recs)} guardrailed action recommendations")
    if telemetry:
        telemetry.record_step("Generate Business Actions")
        
    # 2.12 Persona Narrative Synthesis (AI Narrative)
    narrative_response = generate_narrative(
        kpi_result, driver_result, recs, evidence,
        persona=persona, telemetry=telemetry
    )
    trace.append("🟣 Narrative tone synthesized for target role (narration only)")
    if telemetry:
        telemetry.record_step("LLM Tone Synthesis")
        telemetry.end()
        
    # 2.13 What would change my mind list
    what_change = []
    if kpi_name == 'revenue' and region == 'South':
        what_change = [
            "Competitor pricing matches our standard base rate of ₹50,000",
            "Support delay complaints reduce below baseline rates (< 2 per week)",
            "Marketing spend is restored to original ₹500,000 weekly budget",
            "Fulfillment SLA statistics contradict the delivery bottleneck logs"
        ]
    else:
        what_change = [
            f"The analyzed trend for {kpi_name} stabilizes in subsequent periods",
            "Observed data quality indicators refresh below stale thresholds",
            "Additional evidence contradicts the primary drivers"
        ]
        
    return InvestigationResult(
        kpi=kpi_result, anomaly=anomaly_info, drivers=driver_result['drivers'],
        evidence=evidence, confidence=conf, impact=impact_info,
        recommendations=recs, persona=persona, decision_trace=trace,
        warnings=warnings, is_demo=False, what_change_mind=what_change,
        narrative=narrative_response
    ).to_dict()
