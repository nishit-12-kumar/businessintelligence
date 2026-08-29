"""What-If / Scenario Simulator.

Provides lightweight scenario modeling of driver adjustments and estimated recovery
potential. All results are explicitly labelled as SIMULATED SCENARIO.
"""
from typing import Dict, Any

def run_what_if_simulation(kpi_name: str, region: str, product: str, 
                           driver_name: str, original_driver_impact: float, 
                           proposed_driver_impact: float, kpi_current_val: float) -> Dict[str, Any]:
    """Simulate recovery potential by adjusting driver impact values.
    
    Formula:
        Recovery Pct = (Proposed Impact - Original Impact)
        Recovered Monthly Value = Current Value * Recovery Pct * 4.33
        
    Args:
        kpi_name: KPI name
        region: Affected region
        product: Affected product
        driver_name: Driver targeted for adjustment (pricing, delivery, marketing)
        original_driver_impact: The calculated driver impact from analysis (e.g. -6.2%)
        proposed_driver_impact: The user adjusted driver impact (e.g. -2.0%)
        kpi_current_val: Current weekly value of the KPI
        
    Returns:
        Dict containing simulated recovery metrics
    """
    # Proposed driver impact is closer to 0 (less negative)
    # E.g. pricing gap improved from -6.2% to -2.0%
    recovery_pct = proposed_driver_impact - original_driver_impact
    
    # Cap recovery pct to positive values
    if recovery_pct < 0:
        recovery_pct = 0.0
        
    # Scale from weekly to monthly
    # Current value is weekly. Monthly current value is weekly * 4.33
    current_monthly_val = kpi_current_val * 4.33
    estimated_recovery_value = current_monthly_val * (recovery_pct / 100.0)
    
    # Calculate estimated KPI change pct
    # If the original KPI was down 12.4%, and we recover 4.2%, the new estimated KPI change is -8.2%
    
    return {
        'kpi_name': kpi_name,
        'driver_name': driver_name,
        'original_impact_pct': original_driver_impact,
        'proposed_impact_pct': proposed_driver_impact,
        'estimated_kpi_recovery_pct': round(recovery_pct, 2),
        'estimated_recovery_monthly': round(estimated_recovery_value, 2),
        'confidence': 'MEDIUM',
        'label': '🟡 SIMULATED SCENARIO',
        'model_description': "Estimated recovery simulated using a linear elastic response model."
    }
