"""Anomaly Detection Module.

Detects significant KPI movements by comparing current vs previous periods.
Uses thresholds from the KPI semantic contract.
Includes sparse-history detection for new products.

Method: Historical baseline comparison (deterministic, no ML).
"""
import duckdb
from typing import List, Dict, Any
from analytics.kpi_engine import load_kpi_definitions, get_date_periods, calculate_kpi

def check_sparse_history(conn: duckdb.DuckDBPyConnection, product: str, 
                         min_days: int = 14) -> Dict[str, Any]:
    """Check if a product has sufficient historical data.
    
    Args:
        conn: DuckDB connection
        product: Product name to check
        min_days: Minimum days of history required (default 14)
    
    Returns:
        Dict with 'is_sparse', 'days_available', 'warning'
    """
    result = conn.execute(f"""
        SELECT COUNT(DISTINCT date) as days_count,
               MIN(date) as first_date,
               MAX(date) as last_date
        FROM sales
        WHERE product = '{product}'
    """).fetchone()
    
    days_available = result[0]
    is_sparse = days_available < min_days
    
    warning = None
    if is_sparse:
        warning = (f"⚠️ Sparse history. {product} has only {days_available} days of data. "
                   f"There is not enough historical data to reliably determine "
                   f"whether this movement is abnormal.")
    
    return {
        'is_sparse': is_sparse,
        'days_available': days_available,
        'first_date': str(result[1])[:10] if result[1] else None,
        'last_date': str(result[2])[:10] if result[2] else None,
        'warning': warning,
        'min_days_required': min_days
    }

def detect_anomalies(conn: duckdb.DuckDBPyConnection, 
                     allowed_regions: List[str]) -> List[Dict[str, Any]]:
    """Detect significant KPI movements across all dimensions.
    
    Scans all KPIs × regions × products for significant changes.
    Also checks for sparse history on each product.
    
    Args:
        conn: DuckDB connection
        allowed_regions: Authorized regions
    
    Returns:
        List of alert dicts, sorted by absolute change (largest first).
        Each dict: {kpi_name, region, product, current_value, previous_value,
                    change_pct, threshold, is_significant, sparse_history, sparse_warning}
    """
    kpi_defs = load_kpi_definitions()
    alerts = []
    
    # Get unique products and regions from data
    products = [row[0] for row in conn.execute(
        "SELECT DISTINCT product FROM sales ORDER BY product"
    ).fetchall()]
    
    for kpi_name in ['revenue', 'orders', 'asp', 'conversion_rate']:
        for region in allowed_regions:
            for product in products:
                result = calculate_kpi(conn, kpi_name, allowed_regions, 
                                      region=region, product=product)
                
                if result.get('error'):
                    continue
                
                # Check sparse history
                sparse = check_sparse_history(conn, product)
                
                alert = {
                    'kpi_name': kpi_name,
                    'region': region,
                    'product': product,
                    'current_value': result['current_value'],
                    'previous_value': result['previous_value'],
                    'change_pct': result['change_pct'],
                    'threshold': result['threshold'],
                    'is_significant': result['is_significant'],
                    'sparse_history': sparse['is_sparse'],
                    'sparse_warning': sparse['warning'],
                    'days_of_history': sparse['days_available']
                }
                
                # Only include if significant OR sparse history
                if alert['is_significant'] or alert['sparse_history']:
                    alerts.append(alert)
    
    # Sort by absolute change percentage (largest first)
    alerts.sort(key=lambda x: abs(x['change_pct']), reverse=True)
    
    return alerts

def get_alert_severity(change_pct: float, threshold: float) -> str:
    """Determine alert severity based on magnitude of change.
    
    Returns: 'critical', 'warning', or 'info'
    """
    abs_change = abs(change_pct)
    if abs_change >= threshold * 2:
        return 'critical'
    elif abs_change >= threshold:
        return 'warning'
    else:
        return 'info'
