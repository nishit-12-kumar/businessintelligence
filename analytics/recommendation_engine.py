"""Recommendation & Actions Engine with Guardrails.

Generates structured, guardrailed business recommendations based on the 
deterministic driver, evidence, and confidence scores.
"""
from typing import List, Dict, Any
from semantic.knowledge_graph import knowledge_graph

def generate_recommendations(drivers: List[Dict], 
                             evidence: Dict[str, List[Dict]], 
                             impact_info: Dict[str, Any],
                             confidence_info: Dict[str, Any],
                             region: str, 
                             product: str = None,
                             persona: str = 'executive') -> List[Dict[str, Any]]:
    """Generate structured, prioritized business actions with confidence guardrails.
    
    Confidence-based behavior:
    - Confidence < 50%: "Continue monitoring / collect more data" (Abstain from high-risk changes)
    - Confidence 50-75%: "Investigate further" actions (Audit, run pilot tests)
    - Confidence > 75%: "Recommended action" (Clear, high-priority changes)
    
    Every recommendation contains:
        Action, Reason, Supporting Evidence, Priority, Confidence, Expected Impact, Risk / Caveat
        
    Args:
        drivers: List of driver contributions
        evidence: Evidence items mapped by source
        impact_info: Business exposure calculations
        confidence_info: Confidence engine results dict
        region: Affected region
        product: Affected product
        persona: 'executive' or 'regional_manager'
        
    Returns:
        List of recommendation dictionaries
    """
    confidence_score = confidence_info.get('score', 50)
    rec_min = impact_info.get('recovery_min', 0.0)
    rec_max = impact_info.get('recovery_max', 0.0)
    
    recommendations = []
    
    # GUARDRAIL 1: Confidence < 50% (No strong recommendations)
    if confidence_score < 50:
        recommendations.append({
            'action': "Continue monitoring & collect additional data",
            'reason': f"Confidence is extremely low ({confidence_score}%) due to stale records or missing channels.",
            'supporting_evidence': "Gaps identified in data lineage; telemetry flagged missing/stale sources.",
            'priority': "LOW",
            'confidence': f"{confidence_score}%",
            'expected_impact': "₹0 (Risk avoidance)",
            'risk_caveat': "High risk of error if strategic changes are made based on incomplete information.",
            'driver': "All"
        })
        return recommendations
        
    # GUARDRAIL 2: Confidence 50 - 75% (Investigate further / Pilot tests)
    elif confidence_score <= 75:
        # Generate medium-risk advisory actions
        for driver in drivers:
            name = driver['driver_name'].lower()
            contrib = driver['contribution_pct']
            
            if 'competitor' in name or 'price' in name:
                recommendations.append({
                    'action': f"Conduct competitive audit & run limited pilot promotions for {product or 'products'}",
                    'reason': f"Price changes explain {contrib}% of the anomaly, but confidence is moderate ({confidence_score}%).",
                    'supporting_evidence': "Competitor data contains records but is approaching stale thresholds.",
                    'priority': "MEDIUM",
                    'confidence': f"{confidence_score}%",
                    'expected_impact': f"Potential recovery: ₹{rec_min * 0.5:,.0f}–₹{rec_max * 0.5:,.0f}/month (Advisory)",
                    'risk_caveat': "Pricing changes should be localized to prevent margin deterioration.",
                    'driver': driver['driver_name']
                })
            elif 'delivery' in name or 'support' in name:
                recommendations.append({
                    'action': f"Audit logistics transit logs for {region} & run pilot routing modifications",
                    'reason': f"Logistics issues explain {contrib}% of the anomaly, but metrics require additional validation.",
                    'supporting_evidence': "Support tickets exist but do not match overall warehouse SLA backlogs.",
                    'priority': "MEDIUM",
                    'confidence': f"{confidence_score}%",
                    'expected_impact': f"Potential recovery: ₹{rec_min * 0.5:,.0f}–₹{rec_max * 0.5:,.0f}/month",
                    'risk_caveat': "Ensure logistics modifications don't disrupt active shipments.",
                    'driver': driver['driver_name']
                })
            elif 'marketing' in name:
                recommendations.append({
                    'action': f"Audit campaign CTR performance & review budget allocations",
                    'reason': f"Marketing spend cuts explain {contrib}% of the drop, but other channels show stable CTR.",
                    'supporting_evidence': "Marketing rows contain some missing weeks; data completeness is sub-optimal.",
                    'priority': "MEDIUM",
                    'confidence': f"{confidence_score}%",
                    'expected_impact': f"Potential recovery: ₹{rec_min * 0.5:,.0f}–₹{rec_max * 0.5:,.0f}/month",
                    'risk_caveat': "Wait for complete weekly marketing aggregation before scaling campaign spend.",
                    'driver': driver['driver_name']
                })
                
        if not recommendations:
            recommendations.append({
                'action': "Run operational audit on data capture systems",
                'reason': f"Attribution certainty is moderate ({confidence_score}%). We need to verify underlying telemetry.",
                'supporting_evidence': "Residual unexplained factors exist in analytics engine.",
                'priority': "MEDIUM",
                'confidence': f"{confidence_score}%",
                'expected_impact': "Indirect performance savings",
                'risk_caveat': "Low risk. Focuses on data capture completeness.",
                'driver': "Other"
            })
            
        return recommendations

    # GUARDRAIL 3: Confidence > 75% (Action recommendation - Full strength)
    else:
        for driver in drivers:
            name = driver['driver_name'].lower()
            contrib = driver['contribution_pct']
            
            # Scale recovery based on contribution
            driver_rec_min = round(rec_min * (contrib / 100.0), 2)
            driver_rec_max = round(rec_max * (contrib / 100.0), 2)
            
            priority = "HIGH" if contrib >= 30 else "MEDIUM" if contrib >= 15 else "LOW"
            
            if 'competitor' in name or 'price' in name:
                comp_ev = evidence.get('competitor', [])
                ev_detail = comp_ev[0]['detail'] if comp_ev else "Competitor pricing pressure detected in sales logs."
                
                # Persona customization
                if persona == 'executive':
                    action = f"Review and adjust {product or 'product'} pricing model in {region} to match TechRival"
                    caveat = "Aggressive price matching may result in short-term gross margin decline."
                else:
                    action = f"Apply competitor matching discounts for {product or 'product'} at POS in {region}"
                    caveat = "Local managers must verify margin buffer before applying discounts."
                    
                struct_action = knowledge_graph.get_structured_action(
                    driver['driver_name'], region, product,
                    f"Potential recovery: ₹{driver_rec_min:,.0f}–₹{driver_rec_max:,.0f}/month",
                    f"{confidence_score}%", persona=persona
                )
                recommendations.append({
                    'action': action,
                    'reason': f"Competitor pricing pressure accounted for {contrib}% of the revenue drop.",
                    'supporting_evidence': f"Observed event: {ev_detail}",
                    'expected_impact': struct_action['expected_impact'],
                    'confidence': struct_action['confidence'],
                    'priority': priority,
                    'risk_caveat': caveat,
                    'driver': driver['driver_name'],
                    'controllable_lever': struct_action['controllable_lever'],
                    'owner': struct_action['owner'],
                    'monitoring_plan': struct_action['monitoring_plan']
                })
                
            elif 'delivery' in name or 'support' in name:
                support_ev = evidence.get('support', [])
                ticket_count = len(support_ev)
                ev_detail = f"Support spike of {ticket_count} delivery delay complaints."
                if support_ev:
                    ev_detail += f" Sample complaint: \"{support_ev[0]['detail']}\""
                    
                if persona == 'executive':
                    action = f"Re-negotiate logistics partner SLA for the {region} region to resolve systemic bottlenecks"
                    caveat = "Contract revisions require 30-day legal review."
                else:
                    action = f"Escalate unresolved Bengaluru shipment backlogs with delivery manager"
                    caveat = "Requires coordinate tracking with logistics center."
                    
                struct_action = knowledge_graph.get_structured_action(
                    driver['driver_name'], region, product,
                    f"Potential recovery: ₹{driver_rec_min:,.0f}–₹{driver_rec_max:,.0f}/month",
                    f"{confidence_score}%", persona=persona
                )
                recommendations.append({
                    'action': action,
                    'reason': f"Logistics issues contributed {contrib}% of the decline, causing customer cancellations.",
                    'supporting_evidence': ev_detail,
                    'expected_impact': struct_action['expected_impact'],
                    'confidence': struct_action['confidence'],
                    'priority': priority,
                    'risk_caveat': caveat,
                    'driver': driver['driver_name'],
                    'controllable_lever': struct_action['controllable_lever'],
                    'owner': struct_action['owner'],
                    'monitoring_plan': struct_action['monitoring_plan']
                })
                
            elif 'marketing' in name:
                mkt_ev = evidence.get('marketing', [])
                ev_detail = mkt_ev[0]['detail'] if mkt_ev else "Marketing spend reductions detected."
                
                if persona == 'executive':
                    action = f"Reallocate marketing budget & restore spend to top-performing campaigns in {region}"
                    caveat = "Ad budget reallocation requires approval from marketing director."
                else:
                    action = f"Reinstate local performance campaigns for {product or 'product'} in {region}"
                    caveat = "Verify campaign click tracking is configured correctly."
                    
                struct_action = knowledge_graph.get_structured_action(
                    driver['driver_name'], region, product,
                    f"Potential recovery: ₹{driver_rec_min:,.0f}–₹{driver_rec_max:,.0f}/month",
                    f"{confidence_score}%", persona=persona
                )
                recommendations.append({
                    'action': action,
                    'reason': f"Marketing spend cuts contributed {contrib}% of the decline, reducing clicks/conversions.",
                    'supporting_evidence': f"Spend variance: {ev_detail}",
                    'expected_impact': struct_action['expected_impact'],
                    'confidence': struct_action['confidence'],
                    'priority': priority,
                    'risk_caveat': caveat,
                    'driver': driver['driver_name'],
                    'controllable_lever': struct_action['controllable_lever'],
                    'owner': struct_action['owner'],
                    'monitoring_plan': struct_action['monitoring_plan']
                })
                
            elif 'other' not in name:
                struct_action = knowledge_graph.get_structured_action(
                    driver['driver_name'], region, product,
                    f"Potential recovery: ₹{driver_rec_min:,.0f}–₹{driver_rec_max:,.0f}/month",
                    f"{confidence_score}%", persona=persona
                )
                recommendations.append({
                    'action': f"Conduct deep-dive operational audit for {driver['driver_name']} in {region}",
                    'reason': f"{driver['driver_name']} accounted for {contrib}% of the overall metric movement.",
                    'supporting_evidence': "Correlation detected in multi-factor correlation matrix.",
                    'expected_impact': struct_action['expected_impact'],
                    'confidence': struct_action['confidence'],
                    'priority': priority,
                    'risk_caveat': "Requires manual log inspection.",
                    'driver': driver['driver_name'],
                    'controllable_lever': struct_action['controllable_lever'],
                    'owner': struct_action['owner'],
                    'monitoring_plan': struct_action['monitoring_plan']
                })
                
        # Sort by priority
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 3))
        
        return recommendations
