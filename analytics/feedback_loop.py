"""Feedback and Outcome Learning Loop.

Tracks user feedback on insights and recommendations to simulate a feedback
loop that records decision outcomes.
"""
import json
import os
from typing import Dict, List, Any

FEEDBACK_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
    'data', 
    'feedback.json'
)

def _init_feedback_file():
    """Ensure the feedback JSON file exists with starting values."""
    if not os.path.exists(FEEDBACK_FILE):
        # Starting historical data for the mock learning dashboard
        default_data = {
            'recommendations_issued': 42,
            'accepted': 28,
            'implemented': 21,
            'successful': 16,
            'logs': [
                {
                    'insight': 'South revenue drop -12.4%',
                    'recommendation': 'Review pricing + logistics SLA',
                    'rating': 'thumbs_up',
                    'actioned': 'accepted',
                    'outcome': 'successful',
                    'timestamp': '2026-08-25 10:30:00'
                }
            ]
        }
        os.makedirs(os.path.dirname(FEEDBACK_FILE), exist_ok=True)
        with open(FEEDBACK_FILE, 'w') as f:
            json.dump(default_data, f, indent=4)

def load_feedback_metrics() -> Dict[str, Any]:
    """Load feedback counts and logs from disk with computed metrics."""
    _init_feedback_file()
    try:
        with open(FEEDBACK_FILE, 'r') as f:
            data = json.load(f)
    except Exception:
        data = {
            'recommendations_issued': 0, 'accepted': 0, 'rejected': 0,
            'implemented': 0, 'successful': 0, 'logs': []
        }
    
    issued = data.get('recommendations_issued', 0)
    accepted = data.get('accepted', 0)
    rejected = data.get('rejected', max(0, issued - accepted))
    data['total_recommendations'] = issued
    data['accepted'] = accepted
    data['rejected'] = rejected
    data['acceptance_rate'] = (accepted / issued * 100.0) if issued > 0 else 0.0
    data['recent_feedback'] = data.get('logs', [])
    return data

def save_feedback(insight: str, recommendation: str, rating: str, actioned: str, outcome: str = 'pending'):
    """Record a new feedback event and update overall counters."""
    data = load_feedback_metrics()
    
    # Update counters
    data['recommendations_issued'] += 1
    if actioned == 'accepted':
        data['accepted'] += 1
        data['implemented'] += 1  # For mock, we automatically implement accepted ones
        if rating == 'thumbs_up':
            data['successful'] += 1
            outcome = 'successful'
    elif actioned == 'rejected':
        data['rejected'] = data.get('rejected', 0) + 1
        outcome = 'rejected'
            
    # Add log entry
    from datetime import datetime
    data['logs'].append({
        'insight': insight,
        'recommendation': recommendation,
        'rating': rating,
        'actioned': actioned,
        'outcome': outcome,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    # Clean up derived keys before saving to JSON file
    save_data = {
        'recommendations_issued': data['recommendations_issued'],
        'accepted': data['accepted'],
        'rejected': data['rejected'],
        'implemented': data['implemented'],
        'successful': data['successful'],
        'logs': data['logs']
    }
    
    with open(FEEDBACK_FILE, 'w') as f:
        json.dump(save_data, f, indent=4)

