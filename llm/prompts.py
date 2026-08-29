"""Prompt templates for persona-specific narrative generation.

The LLM is used ONLY for:
- Intent understanding
- Evidence summarization  
- Narrative generation
- Persona adaptation

The LLM does NOT:
- Calculate KPI values
- Invent or fabricate evidence
- Determine driver contributions
"""

def get_executive_prompt(analysis_data: dict) -> str:
    """Generate prompt for Executive persona.
    
    Executive wants:
    - What happened? (brief)
    - Business impact? (quantified)
    - Main reason? (top 1-2 drivers)
    - Recommended action? (actionable)
    - Confidence? (stated clearly)
    
    Keep it SHORT — 3-5 sentences max.
    """
    kpi_name = analysis_data.get('kpi_name', 'Revenue')
    region = analysis_data.get('region', 'Unknown')
    product = analysis_data.get('product', 'All products')
    change_pct = analysis_data.get('change_pct', 0)
    current_value = analysis_data.get('current_value', 0)
    previous_value = analysis_data.get('previous_value', 0)
    drivers = analysis_data.get('drivers', [])
    confidence = analysis_data.get('confidence', {})
    actions = analysis_data.get('actions', [])
    evidence = analysis_data.get('evidence_summary', '')
    
    drivers_text = '\n'.join([
        f"  - {d['driver_name']}: {d['contribution_pct']}% contribution"
        for d in drivers
    ])
    
    actions_text = '\n'.join([
        f"  - [{a.get('priority', 'medium').upper()}] {a['action']}"
        for a in actions[:3]
    ])
    
    return f"""You are a business intelligence analyst presenting to a C-level executive.

IMPORTANT RULES:
- Use ONLY the data provided below. Do NOT calculate or invent any numbers.
- Keep your summary to 3-5 sentences maximum.
- Be direct, action-oriented, and quantitative.
- Use INR (₹) for all currency values.
- State the confidence level clearly.

KPI: {kpi_name}
Region: {region}
Product: {product}
Current Period Value: ₹{current_value:,.0f}
Previous Period Value: ₹{previous_value:,.0f}
Change: {change_pct:+.1f}%

Identified Drivers (from data analysis, NOT from you):
{drivers_text}

Supporting Evidence:
{evidence}

Recommended Actions:
{actions_text}

Confidence Level: {confidence.get('level', 'MEDIUM')}
Confidence Reason: {confidence.get('reason', 'N/A')}

Generate a concise executive summary (3-5 sentences) covering:
1. What happened (the KPI change)
2. Primary driver(s)
3. Recommended action
4. Confidence level

Do NOT add any numbers that are not provided above."""


def get_regional_manager_prompt(analysis_data: dict) -> str:
    """Generate prompt for Regional Manager persona.
    
    Regional Manager wants:
    - KPI change (detailed)
    - Affected products (specific)
    - Driver contribution (with percentages)
    - Evidence (detailed, with sources)
    - Recommended actions (specific, prioritized)
    - Monitoring metrics (what to watch)
    
    More detailed than executive — include tables and specific data points.
    """
    kpi_name = analysis_data.get('kpi_name', 'Revenue')
    region = analysis_data.get('region', 'Unknown')
    product = analysis_data.get('product', 'All products')
    change_pct = analysis_data.get('change_pct', 0)
    current_value = analysis_data.get('current_value', 0)
    previous_value = analysis_data.get('previous_value', 0)
    drivers = analysis_data.get('drivers', [])
    confidence = analysis_data.get('confidence', {})
    actions = analysis_data.get('actions', [])
    evidence_details = analysis_data.get('evidence_details', [])
    
    drivers_text = '\n'.join([
        f"  - {d['driver_name']}: {d['contribution_pct']}% contribution ({d.get('direction', 'negative')} impact)"
        for d in drivers
    ])
    
    evidence_text = ''
    for ev in evidence_details:
        evidence_text += f"\n  Source: {ev.get('source', 'N/A')}"
        evidence_text += f"\n  Date: {ev.get('date', 'N/A')}"
        evidence_text += f"\n  Region: {ev.get('region', 'N/A')}"
        evidence_text += f"\n  Product: {ev.get('product', 'N/A')}"
        evidence_text += f"\n  Detail: {ev.get('detail', 'N/A')}"
        if ev.get('ticket_id'):
            evidence_text += f"\n  Ticket ID: {ev['ticket_id']}"
        evidence_text += '\n  ---'
    
    actions_text = '\n'.join([
        f"  - [{a.get('priority', 'medium').upper()}] {a['action']}"
        for a in actions
    ])
    
    return f"""You are a business intelligence analyst presenting a detailed investigation report to a Regional Manager.

IMPORTANT RULES:
- Use ONLY the data provided below. Do NOT calculate or invent any numbers.
- Provide a structured, detailed report.
- Use INR (₹) for all currency values.
- Include specific evidence references.
- Suggest monitoring metrics.

KPI: {kpi_name}
Region: {region}
Product: {product}
Current Period Value: ₹{current_value:,.0f}
Previous Period Value: ₹{previous_value:,.0f}
Change: {change_pct:+.1f}%

Identified Drivers (from data analysis, NOT from you):
{drivers_text}

Detailed Evidence:
{evidence_text}

Recommended Actions:
{actions_text}

Confidence Level: {confidence.get('level', 'MEDIUM')}
Confidence Reason: {confidence.get('reason', 'N/A')}

Generate a detailed regional manager report with these sections:
1. **KPI Change Summary**: What changed and by how much
2. **Affected Products**: Which products are impacted
3. **Driver Analysis**: Each driver with its contribution percentage
4. **Key Evidence**: Reference specific data points and sources
5. **Recommended Actions**: Prioritized list with specific steps
6. **Monitoring Metrics**: What metrics to watch going forward

Do NOT add any numbers that are not provided above."""


def get_abstention_prompt() -> str:
    """Return the abstention message template (no LLM call needed)."""
    return (
        "⚠️ Insufficient evidence to determine the primary driver.\n\n"
        "The system does not have enough data to provide a reliable explanation. "
        "Please ensure all data sources are refreshed before retrying the investigation."
    )
