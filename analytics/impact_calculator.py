"""Business Impact & Exposure Calculator.

Calculates the financial exposure, impact scores, and potential recoveries
for detected anomalies. All calculations are deterministic.
"""
from typing import Dict, Any

# KPI Importance multipliers
KPI_IMPORTANCE = {
    'revenue': 1.0,
    'conversion_rate': 0.8,
    'orders': 0.7,
    'asp': 0.6
}

def calculate_impact_score(kpi_name: str, change_pct: float, 
                           current_val: float, previous_val: float,
                           confidence_pct: float) -> Dict[str, Any]:
    """Calculate the business impact score and financial exposure.
    
    Formula:
    Impact Score = KPI_Importance * |Change %| * log10(Exposure + 1) * (Confidence % / 100)
    
    Args:
        kpi_name: KPI identifier
        change_pct: Percentage change
        current_val: Current period value
        previous_val: Previous period value
        confidence_pct: Clustered confidence score (0 to 100)
        
    Returns:
        Dict with impact_score (0-100), impact_category (HIGH/MEDIUM/LOW),
        exposure_monthly, recovery_min, recovery_max, and labelling
    """
    importance = KPI_IMPORTANCE.get(kpi_name, 0.5)
    abs_change_pct = abs(change_pct)
    
    # Calculate raw monetary change (weekly base, since our period is 7 days)
    monetary_change = abs(current_val - previous_val)
    
    # Scale exposure to monthly basis (approx. 4.3 weeks per month)
    # If the metric is conversion rate or ASP, we calculate exposure based on the underlying revenue change
    if kpi_name == 'revenue':
        exposure_monthly = monetary_change * 4.33
        label = "Calculated Exposure"
    elif kpi_name == 'orders':
        # Estimate: Orders loss * ASP (use national average ASP approx ₹35,000 if not available)
        exposure_monthly = (monetary_change * 35000) * 4.33
        label = "Estimated Exposure Scenario"
    elif kpi_name == 'asp':
        # Estimate: ASP change * current units * monthly
        exposure_monthly = (monetary_change * 300) * 4.33 # approx 300 units per week
        label = "Estimated Exposure Scenario"
    else: # conversion_rate
        # Estimate: conversion drop * clicks * average ASP
        exposure_monthly = (monetary_change * 5000 * 35000) * 4.33
        label = "Simulated Exposure Scenario"
        
    # Boundary logic for log scaling
    log_factor = 1.0
    if exposure_monthly > 0:
        import math
        # Use log10 to scale wide range of exposures
        log_factor = math.log10(exposure_monthly)
        
    # Compute Raw Score
    raw_score = importance * abs_change_pct * log_factor * (confidence_pct / 100.0)
    
    # Normalize score to 0 - 100 scale (capping at 100)
    normalized_score = min(round(raw_score * 3.5, 1), 100.0)
    
    # Determine Category
    if normalized_score >= 60.0:
        category = "HIGH"
    elif normalized_score >= 25.0:
        category = "MEDIUM"
    else:
        category = "LOW"
        
    # Recovery range is estimated at 40% - 70% of potential monthly exposure
    recovery_min = round(exposure_monthly * 0.40, 2)
    recovery_max = round(exposure_monthly * 0.70, 2)
    
    return {
        'impact_score': normalized_score,
        'impact_category': category,
        'exposure_monthly': round(exposure_monthly, 2),
        'recovery_min': recovery_min,
        'recovery_max': recovery_max,
        'exposure_type': label,
        'observed_monetary_change': round(monetary_change, 2)
    }
