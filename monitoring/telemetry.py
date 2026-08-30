"""Runtime telemetry tracking for investigations.

Tracks latency, LLM calls, token usage, and estimated cost.
"""
import time
import os
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import random

# Gemini 2.0 Flash pricing (free tier, but we estimate what it would cost)
# Using approximate pricing for demonstration
GEMINI_PRICING = {
    'input_per_1k_tokens': 0.0,  # Free tier
    'output_per_1k_tokens': 0.0,  # Free tier
    'input_per_1k_tokens_paid': 0.00015,  # Estimated paid pricing for reference
    'output_per_1k_tokens_paid': 0.0006,
}

@dataclass
class TelemetryTracker:
    """Tracks runtime metrics for a single investigation."""
    
    _start_time: Optional[float] = field(default=None, repr=False)
    _end_time: Optional[float] = field(default=None, repr=False)
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    _steps: list = field(default_factory=list, repr=False)
    
    def start(self):
        """Start the telemetry timer."""
        self._start_time = time.time()
        self._steps = []
    
    def record_step(self, step_name: str):
        """Record completion of an analytical step."""
        self._steps.append({
            'step': step_name,
            'timestamp': time.time()
        })
    
    def record_llm_call(self, input_tokens: int, output_tokens: int, model: str = 'gemini-2.0-flash'):
        """Record an LLM API call with token usage.
        
        Args:
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens generated
            model: Model name for cost estimation
        """
        self.llm_calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self._steps.append({
            'step': f'LLM call ({model})',
            'timestamp': time.time(),
            'input_tokens': input_tokens,
            'output_tokens': output_tokens
        })
    
    def end(self):
        """Stop the telemetry timer."""
        self._end_time = time.time()
    
    @property
    def latency_sec(self) -> float:
        """Total elapsed time in seconds."""
        if self._start_time is None:
            return 0.0
        end = self._end_time or time.time()
        return round(end - self._start_time, 3)
    
    @property
    def estimated_cost(self) -> float:
        """Estimated cost in USD based on paid tier pricing."""
        input_cost = (self.input_tokens / 1000) * GEMINI_PRICING['input_per_1k_tokens_paid']
        output_cost = (self.output_tokens / 1000) * GEMINI_PRICING['output_per_1k_tokens_paid']
        return round(input_cost + output_cost, 6)
    
    def get_metrics(self) -> Dict:
        """Get all telemetry metrics as a dictionary.
        
        Returns:
            Dict with latency_sec, llm_calls, input_tokens, output_tokens, estimated_cost, steps
        """
        return {
            'latency_sec': self.latency_sec,
            'llm_calls': self.llm_calls,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'estimated_cost': self.estimated_cost,
            'steps': self._steps[:]
        }

    def get_summary(self) -> Dict:
        """Get telemetry summary expected by Streamlit UI.
        
        Returns:
            Dict with total_ms, llm_calls, step_count, steps, estimated_cost, etc.
        """
        return {
            'total_ms': self.latency_sec * 1000.0,
            'llm_calls': self.llm_calls,
            'step_count': len(self._steps),
            'steps': self._steps[:],
            'estimated_cost': self.estimated_cost,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'latency_sec': self.latency_sec,
            'economics': self.get_economics_breakdown()
        }

    def get_economics_breakdown(self) -> Dict[str, Any]:
        """Return explicit LLM economics breakdown for free vs commercial paid tier."""
        current_free_cost = 0.0
        input_paid_cost = (self.input_tokens / 1000.0) * GEMINI_PRICING['input_per_1k_tokens_paid']
        output_paid_cost = (self.output_tokens / 1000.0) * GEMINI_PRICING['output_per_1k_tokens_paid']
        est_paid_per_iter = input_paid_cost + output_paid_cost
        
        return {
            'free_tier_actual_cost': '$0.0000 (Gemini 2.0 Flash Free Tier)',
            'paid_tier_input_rate': '$0.15 per 1M tokens ($0.00015/1k)',
            'paid_tier_output_rate': '$0.60 per 1M tokens ($0.00060/1k)',
            'estimated_cost_per_iteration': f"${est_paid_per_iter:.6f}",
            'projected_cost_10k_runs': f"${est_paid_per_iter * 10000:.2f}/month",
            'llm_calls_made': self.llm_calls,
            'total_tokens': self.input_tokens + self.output_tokens
        }



def get_file_age_minutes(filename: str) -> int:
    """Get the actual age of a data file in minutes based on OS modification time."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filepath = os.path.join(base_dir, 'data', filename)
    if os.path.exists(filepath):
        import os as local_os
        mtime = local_os.path.getmtime(filepath)
        age_sec = time.time() - mtime
        return max(1, int(age_sec / 60))
    return 10  # fallback default

def format_display_age(minutes: int) -> str:
    """Format minutes into human readable text."""
    if minutes < 60:
        return f"{minutes}m ago"
    elif minutes < 1440:
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m ago"
    else:
        days = minutes // 1440
        hours = (minutes % 1440) // 60
        return f"{days}d {hours}h ago"

def get_source_freshness() -> Dict[str, Dict]:
    """Get actual freshness information for each data source based on file timestamps.
    
    Returns:
        Dict mapping source name to freshness info
    """
    now = datetime.now()
    
    # Calculate actual age
    sales_age = get_file_age_minutes('sales.csv')
    marketing_age = get_file_age_minutes('marketing.csv')
    support_age = get_file_age_minutes('support.csv')
    competitor_age = get_file_age_minutes('competitor.csv')
    
    # Define thresholds (in hours)
    thresholds = {
        'sales': 24,       # 1 day
        'marketing': 168,  # 7 days
        'support': 24,     # 1 day
        'competitor': 72   # 3 days
    }
    
    freshness = {
        'sales': {
            'last_updated': (now - timedelta(minutes=sales_age)).strftime('%Y-%m-%d %H:%M:%S'),
            'age_minutes': sales_age,
            'is_stale': (sales_age / 60.0) > thresholds['sales'],
            'stale_threshold_hours': thresholds['sales'],
            'refresh_frequency': 'daily',
            'display_age': format_display_age(sales_age)
        },
        'marketing': {
            'last_updated': (now - timedelta(minutes=marketing_age)).strftime('%Y-%m-%d %H:%M:%S'),
            'age_minutes': marketing_age,
            'is_stale': (marketing_age / 60.0) > thresholds['marketing'],
            'stale_threshold_hours': thresholds['marketing'],
            'refresh_frequency': 'weekly',
            'display_age': format_display_age(marketing_age)
        },
        'support': {
            'last_updated': (now - timedelta(minutes=support_age)).strftime('%Y-%m-%d %H:%M:%S'),
            'age_minutes': support_age,
            'is_stale': (support_age / 60.0) > thresholds['support'],
            'stale_threshold_hours': thresholds['support'],
            'refresh_frequency': 'event-based',
            'display_age': format_display_age(support_age)
        },
        'competitor': {
            'last_updated': (now - timedelta(minutes=competitor_age)).strftime('%Y-%m-%d %H:%M:%S'),
            'age_minutes': competitor_age,
            'is_stale': (competitor_age / 60.0) > thresholds['competitor'],
            'stale_threshold_hours': thresholds['competitor'],
            'refresh_frequency': 'event-based',
            'display_age': format_display_age(competitor_age)
        }
    }
    
    return freshness


def get_stale_source_freshness() -> Dict[str, Dict]:
    """Get freshness data simulating a stale marketing source.
    
    Used for demonstrating stale data warnings and confidence degradation.
    """
    freshness = get_source_freshness()
    now = datetime.now()
    
    # Force marketing to be 3 days (4320 minutes) old (weekly cadence, not stale, but older)
    # Let's force it to 9 days (12960 minutes) to trigger actual stale warning (>168 hours)
    stale_minutes = 9 * 24 * 60
    freshness['marketing'] = {
        'last_updated': (now - timedelta(minutes=stale_minutes)).strftime('%Y-%m-%d %H:%M:%S'),
        'age_minutes': stale_minutes,
        'is_stale': True,
        'stale_threshold_hours': 168,
        'refresh_frequency': 'weekly',
        'display_age': '9d 0h ago'
    }
    
    # Also force competitor to be 4 days (5760 minutes) old (>72 hours) to trigger stale warning
    stale_comp_minutes = 4 * 24 * 60
    freshness['competitor'] = {
        'last_updated': (now - timedelta(minutes=stale_comp_minutes)).strftime('%Y-%m-%d %H:%M:%S'),
        'age_minutes': stale_comp_minutes,
        'is_stale': True,
        'stale_threshold_hours': 72,
        'refresh_frequency': 'event-based',
        'display_age': '4d 0h ago'
    }
    
    return freshness
