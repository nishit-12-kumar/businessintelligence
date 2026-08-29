"""LLM Narrative Generation Module.

Uses Google Gemini (free model) to generate persona-appropriate narratives
from structured analysis results.

The LLM is used ONLY for natural language generation.
All numbers, drivers, and evidence come from the analytics pipeline.
"""
import os
import time
from typing import Dict, Optional, Any

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.prompts import get_executive_prompt, get_regional_manager_prompt, get_abstention_prompt
from monitoring.telemetry import TelemetryTracker

# Configure Gemini
MODEL_NAME = 'gemini-2.0-flash'  # Free tier model

def _configure_genai():
    """Configure the Gemini API with the API key."""
    api_key = os.environ.get('GOOGLE_API_KEY', '')
    if not api_key:
        return False
    if GENAI_AVAILABLE:
        genai.configure(api_key=api_key)
        return True
    return False

def _build_analysis_data(kpi_result: Dict, driver_result: Dict, 
                          actions: list, all_evidence: Dict) -> Dict:
    """Build the analysis data dict expected by prompt templates.
    
    Args:
        kpi_result: From kpi_engine.calculate_kpi()
        driver_result: From driver_analysis.analyze_revenue_drivers()
        actions: From driver_analysis.get_recommended_actions()
        all_evidence: From retriever.get_all_evidence()
    
    Returns:
        Merged dict suitable for prompt generation
    """
    # Flatten evidence for summary
    evidence_summary_parts = []
    evidence_details = []
    SKIP_KEYS = {'coverage', 'contradicting'}
    for source_type, evidence_list in all_evidence.items():
        if source_type in SKIP_KEYS or not isinstance(evidence_list, list):
            continue
        for ev in evidence_list[:3]:  # Limit per source
            evidence_summary_parts.append(f"{ev['source']}: {ev['detail']}")
            evidence_details.append(ev)
    
    return {
        'kpi_name': kpi_result.get('kpi_name', 'Revenue'),
        'region': kpi_result.get('region', 'Unknown'),
        'product': kpi_result.get('product', 'All'),
        'current_value': kpi_result.get('current_value', 0),
        'previous_value': kpi_result.get('previous_value', 0),
        'change_pct': kpi_result.get('change_pct', 0),
        'drivers': driver_result.get('drivers', []),
        'confidence': driver_result.get('confidence', {}),
        'actions': actions,
        'evidence_summary': '\n'.join(evidence_summary_parts),
        'evidence_details': evidence_details,
        'abstention': driver_result.get('abstention', False),
        'abstention_message': driver_result.get('abstention_message')
    }


def generate_narrative(kpi_result: Dict, driver_result: Dict,
                       actions: list, all_evidence: Dict,
                       persona: str = 'executive',
                       telemetry: TelemetryTracker = None) -> Dict[str, Any]:
    """Generate a persona-appropriate narrative using Gemini.
    
    If the driver analysis indicates abstention (low confidence),
    NO LLM call is made — the abstention message is returned directly.
    
    Args:
        kpi_result: KPI calculation result dict
        driver_result: Driver analysis result dict
        actions: Recommended actions list
        all_evidence: Evidence from all sources
        persona: 'executive' or 'regional_manager'
        telemetry: Optional TelemetryTracker instance
    
    Returns:
        Dict with:
        - narrative: str (the generated text)
        - persona: str
        - llm_used: bool (whether LLM was actually called)
        - model: str (model name if LLM was used)
        - telemetry: dict (if tracker provided)
    """
    analysis_data = _build_analysis_data(kpi_result, driver_result, actions, all_evidence)
    
    # Check for abstention — do NOT call LLM
    if analysis_data.get('abstention'):
        return {
            'narrative': analysis_data.get('abstention_message', get_abstention_prompt()),
            'persona': persona,
            'llm_used': False,
            'model': None,
            'abstention': True
        }
    
    # Build prompt based on persona
    if persona == 'executive':
        prompt = get_executive_prompt(analysis_data)
    elif persona == 'regional_manager':
        prompt = get_regional_manager_prompt(analysis_data)
    else:
        prompt = get_executive_prompt(analysis_data)  # default
    
    # Try to call Gemini
    is_configured = _configure_genai()
    
    if is_configured and GENAI_AVAILABLE:
        try:
            model = genai.GenerativeModel(MODEL_NAME)
            
            start_time = time.time()
            response = model.generate_content(prompt)
            elapsed = time.time() - start_time
            
            # Extract token counts
            usage = response.usage_metadata
            input_tokens = getattr(usage, 'prompt_token_count', 0) or 0
            output_tokens = getattr(usage, 'candidates_token_count', 0) or 0
            
            # Record telemetry
            if telemetry:
                telemetry.record_llm_call(input_tokens, output_tokens, MODEL_NAME)
            
            narrative_text = response.text
            
            return {
                'narrative': narrative_text,
                'persona': persona,
                'llm_used': True,
                'model': MODEL_NAME,
                'abstention': False,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens
            }
            
        except Exception as e:
            # Fallback to template-based narrative
            return _generate_fallback_narrative(analysis_data, persona)
    else:
        # No API key or genai not available — use fallback
        return _generate_fallback_narrative(analysis_data, persona)


def _generate_fallback_narrative(analysis_data: Dict, persona: str) -> Dict[str, Any]:
    """Generate a template-based narrative when LLM is not available.
    
    This ensures the app works even without a Gemini API key.
    """
    kpi = analysis_data.get('kpi_name', 'Revenue')
    region = analysis_data.get('region', 'Unknown')
    product = analysis_data.get('product', 'All products')
    change = analysis_data.get('change_pct', 0)
    current = analysis_data.get('current_value', 0)
    previous = analysis_data.get('previous_value', 0)
    drivers = analysis_data.get('drivers', [])
    confidence = analysis_data.get('confidence', {})
    actions = analysis_data.get('actions', [])
    
    direction = 'fell' if change < 0 else 'rose'
    
    if persona == 'executive':
        # Short executive summary
        top_drivers = drivers[:2]
        driver_text = ' and '.join([d['driver_name'].lower() for d in top_drivers]) if top_drivers else 'unknown factors'
        action_text = actions[0]['action'] if actions else 'Review the situation.'
        
        narrative = (
            f"{region} {kpi.lower()} {direction} {abs(change):.1f}% "
            f"(₹{current:,.0f} vs ₹{previous:,.0f}), "
            f"primarily due to {driver_text}. "
            f"Recommend: {action_text} "
            f"Confidence: {confidence.get('level', 'MEDIUM')}."
        )
    else:
        # Detailed regional manager report
        lines = [
            f"## {kpi} Investigation Report — {region}",
            f"",
            f"### KPI Change",
            f"- **{kpi}** {direction} by **{abs(change):.1f}%**",
            f"- Current period: ₹{current:,.0f}",
            f"- Previous period: ₹{previous:,.0f}",
            f"- Product: {product or 'All'}",
            f"",
            f"### Driver Analysis",
        ]
        if drivers:
            for d in drivers:
                lines.append(f"- **{d['driver_name']}**: {d['contribution_pct']}% contribution ({d.get('direction', 'negative')} impact)")
        else:
            lines.append("- No drivers identified.")
            
        lines.extend([
            f"",
            f"### Recommended Actions",
        ])
        if actions:
            for a in actions:
                lines.append(f"- [{a.get('priority', 'medium').upper()}] {a['action']}")
        else:
            lines.append("- No recommended actions.")
            
        lines.extend([
            f"",
            f"### Monitoring Metrics",
            f"- Daily revenue trend for {product or 'all products'} in {region}",
            f"- Competitor price movements",
            f"- Marketing campaign performance",
            f"- Delivery SLA compliance",
            f"",
            f"**Confidence**: {confidence.get('level', 'MEDIUM')} — {confidence.get('reason', 'N/A')}",
        ])
        
        narrative = '\n'.join(lines)
    
    return {
        'narrative': narrative,
        'persona': persona,
        'llm_used': False,
        'model': 'fallback-template',
        'abstention': False,
        'note': 'Generated using template (no Gemini API key configured). Set GOOGLE_API_KEY environment variable for LLM-powered narratives.'
    }


def get_llm_vs_non_llm_breakdown() -> Dict[str, list]:
    """Return what the LLM does vs what deterministic code does.
    
    Used for the 'How the insight was generated' UI section.
    """
    return {
        'non_llm': [
            'SQL-based KPI calculations',
            'Statistical anomaly detection',
            'Contribution/variance analysis',
            'Evidence retrieval (SQL)',
            'Business rules and thresholds',
            'Role-based security enforcement',
            'Confidence scoring'
        ],
        'llm': [
            'Intent understanding',
            'Evidence summarization',
            'Narrative generation',
            'Persona adaptation'
        ]
    }
