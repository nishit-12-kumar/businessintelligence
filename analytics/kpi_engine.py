"""KPI Calculation Engine.

Loads KPI definitions from the semantic contract and computes KPIs using DuckDB SQL.
All calculations are deterministic — no LLM involvement.
"""
import duckdb
import pandas as pd
import yaml
import os
from typing import Dict, List, Optional, Any

def get_base_dir() -> str:
    """Get the project base directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_kpi_definitions(yaml_path: str = None) -> Dict:
    """Load KPI definitions from the semantic YAML contract.
    
    This configuration is actively used for:
    - KPI formulas and thresholds
    - Driver identification
    - Access control rules
    
    Args:
        yaml_path: Path to YAML file. Defaults to semantic/kpi_definitions.yaml
    
    Returns:
        Dict of KPI definitions keyed by KPI name
    """
    if yaml_path is None:
        yaml_path = os.path.join(get_base_dir(), 'semantic', 'kpi_definitions.yaml')
    with open(yaml_path, 'r') as f:
        return yaml.safe_load(f)

def create_connection() -> duckdb.DuckDBPyConnection:
    """Create a DuckDB connection and load all data tables.
    
    Returns:
        DuckDB connection with sales, marketing, support, competitor tables loaded
    """
    conn = duckdb.connect()
    base_dir = get_base_dir()
    data_dir = os.path.join(base_dir, 'data')
    
    conn.execute(f"CREATE TABLE IF NOT EXISTS sales AS SELECT * FROM read_csv_auto('{data_dir}/sales.csv')")
    conn.execute(f"CREATE TABLE IF NOT EXISTS marketing AS SELECT * FROM read_csv_auto('{data_dir}/marketing.csv')")
    conn.execute(f"CREATE TABLE IF NOT EXISTS support AS SELECT * FROM read_csv_auto('{data_dir}/support.csv')")
    conn.execute(f"CREATE TABLE IF NOT EXISTS competitor AS SELECT * FROM read_csv_auto('{data_dir}/competitor.csv')")
    
    return conn

def get_date_periods(conn: duckdb.DuckDBPyConnection) -> Dict[str, str]:
    """Determine current and previous periods based on data.
    
    Current period: last 7 days of data
    Previous period: 7 days before that
    
    Returns:
        Dict with 'current_start', 'current_end', 'previous_start', 'previous_end'
    """
    result = conn.execute("SELECT MAX(date) as max_date FROM sales").fetchone()
    if result is None or result[0] is None:
        max_date = '2026-08-27'  # Fallback to the synthetic dataset end date
    else:
        max_date = result[0]
    
    # Use DuckDB date arithmetic
    periods = conn.execute(f"""
        SELECT 
            '{max_date}'::DATE - INTERVAL 6 DAY as current_start,
            '{max_date}'::DATE as current_end,
            '{max_date}'::DATE - INTERVAL 13 DAY as previous_start,
            '{max_date}'::DATE - INTERVAL 7 DAY as previous_end
    """).fetchone()
    
    return {
        'current_start': str(periods[0])[:10],
        'current_end': str(periods[1])[:10],
        'previous_start': str(periods[2])[:10],
        'previous_end': str(periods[3])[:10]
    }

def calculate_kpi(conn: duckdb.DuckDBPyConnection, kpi_name: str, 
                  allowed_regions: List[str], 
                  region: str = None, 
                  product: str = None) -> Dict[str, Any]:
    """Calculate a single KPI with current vs previous period comparison.
    
    Authorization is enforced by only querying allowed_regions.
    
    Args:
        conn: DuckDB connection
        kpi_name: One of 'revenue', 'orders', 'asp', 'conversion_rate'
        allowed_regions: List of regions the user is authorized to see
        region: Optional specific region filter
        product: Optional specific product filter
    
    Returns:
        Dict with: kpi_name, definition, formula, current_value, previous_value,
                   change_pct, threshold, is_significant, region, product
    """
    kpi_defs = load_kpi_definitions()
    kpi_def = kpi_defs[kpi_name]
    periods = get_date_periods(conn)
    
    # Build region filter — SECURITY: only allowed regions
    if region:
        if region not in allowed_regions:
            return {'error': f'Access denied for region {region}', 'authorized': False}
        region_filter = f"region = '{region}'"
    else:
        region_list = ', '.join(f"'{r}'" for r in allowed_regions)
        region_filter = f"region IN ({region_list})"
    
    product_filter = f"AND product = '{product}'" if product else ""
    
    if kpi_name == 'revenue':
        sql_template = """
            SELECT COALESCE(SUM(units * price), 0) as value
            FROM sales
            WHERE {region_filter} {product_filter}
            AND date BETWEEN '{start}' AND '{end}'
        """
    elif kpi_name == 'orders':
        sql_template = """
            SELECT COALESCE(SUM(orders), 0) as value
            FROM sales
            WHERE {region_filter} {product_filter}
            AND date BETWEEN '{start}' AND '{end}'
        """
    elif kpi_name == 'asp':
        sql_template = """
            SELECT CASE WHEN SUM(units) > 0 
                        THEN SUM(revenue) / SUM(units) 
                        ELSE 0 END as value
            FROM sales
            WHERE {region_filter} {product_filter}
            AND date BETWEEN '{start}' AND '{end}'
        """
    elif kpi_name == 'conversion_rate':
        # Cross-source: orders from sales, clicks from marketing
        # Need to match on region/product and align date ranges
        sql_template = """
            SELECT CASE WHEN m.total_clicks > 0 
                        THEN s.total_orders * 1.0 / m.total_clicks 
                        ELSE 0 END as value
            FROM (
                SELECT COALESCE(SUM(orders), 0) as total_orders
                FROM sales 
                WHERE {region_filter} {product_filter}
                AND date BETWEEN '{start}' AND '{end}'
            ) s,
            (
                SELECT COALESCE(SUM(clicks), 0) as total_clicks
                FROM marketing
                WHERE {region_filter} {product_filter}
                AND date BETWEEN '{start}' AND '{end}'
            ) m
        """
    else:
        raise ValueError(f"Unknown KPI: {kpi_name}")
    
    # Calculate current period value
    current_sql = sql_template.format(
        region_filter=region_filter, product_filter=product_filter,
        start=periods['current_start'], end=periods['current_end']
    )
    current_value = conn.execute(current_sql).fetchone()[0]
    
    # Calculate previous period value
    previous_sql = sql_template.format(
        region_filter=region_filter, product_filter=product_filter,
        start=periods['previous_start'], end=periods['previous_end']
    )
    previous_value = conn.execute(previous_sql).fetchone()[0]
    
    # Calculate change
    if previous_value and previous_value != 0:
        change_pct = round(((current_value - previous_value) / previous_value) * 100, 2)
    else:
        change_pct = 0.0
    
    threshold = kpi_def.get('threshold', 5)
    is_significant = abs(change_pct) >= threshold
    
    return {
        'kpi_name': kpi_name,
        'definition': kpi_def['definition'],
        'formula': kpi_def['formula'],
        'current_value': round(float(current_value), 2),
        'previous_value': round(float(previous_value), 2),
        'change_pct': change_pct,
        'threshold': threshold,
        'is_significant': is_significant,
        'region': region,
        'product': product,
        'authorized': True
    }

def calculate_all_kpis(conn: duckdb.DuckDBPyConnection, 
                       allowed_regions: List[str]) -> List[Dict]:
    """Calculate all 4 KPIs for the dashboard.
    
    Args:
        conn: DuckDB connection
        allowed_regions: Authorized regions list
    
    Returns:
        List of KPI result dicts
    """
    results = []
    for kpi_name in ['revenue', 'orders', 'asp', 'conversion_rate']:
        result = calculate_kpi(conn, kpi_name, allowed_regions)
        results.append(result)
    return results
