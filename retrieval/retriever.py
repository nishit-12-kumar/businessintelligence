"""Evidence Retrieval Module.

Retrieves supporting and contradicting evidence from data sources for identified drivers.
Supports keyword filtering and semantic search similarity scoring (TF-IDF & Gemini).
"""
import duckdb
import pandas as pd
import re
import math
import os
from collections import Counter
from typing import List, Dict, Optional, Any
from analytics.kpi_engine import get_date_periods

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# --- Semantic Helper Functions ---

def _tokenize(text: str) -> List[str]:
    """Helper regex tokenizer."""
    return re.findall(r'\w+', text.lower())

def calculate_tf_idf_similarity(query: str, documents: List[str]) -> List[float]:
    """Calculate TF-IDF cosine similarity between query and documents (Pure Python)."""
    if not documents:
        return []
        
    query_tokens = _tokenize(query)
    doc_tokens_list = [_tokenize(doc) for doc in documents]
    
    # Vocabulary builder
    vocab = set(query_tokens)
    for doc_tokens in doc_tokens_list:
        vocab.update(doc_tokens)
        
    vocab = list(vocab)
    vocab_index = {word: idx for idx, word in enumerate(vocab)}
    
    # Document frequency
    df = Counter()
    for doc_tokens in doc_tokens_list:
        unique_tokens = set(doc_tokens)
        for token in unique_tokens:
            df[token] += 1
            
    num_docs = len(documents)
    
    # Inverse Document Frequency (IDF) with smoothing
    idf = {}
    for token in vocab:
        idf[token] = math.log(1 + num_docs / (1 + df[token]))
        
    # Vectors calculation
    def get_vector(tokens):
        tf = Counter(tokens)
        vec = [0.0] * len(vocab)
        for token, count in tf.items():
            if token in vocab_index:
                vec[vocab_index[token]] = count * idf[token]
        return vec
        
    query_vec = get_vector(query_tokens)
    doc_vecs = [get_vector(tokens) for tokens in doc_tokens_list]
    
    def magnitude(vec):
        return math.sqrt(sum(val ** 2 for val in vec))
        
    query_mag = magnitude(query_vec)
    
    scores = []
    for doc_vec in doc_vecs:
        doc_mag = magnitude(doc_vec)
        if query_mag == 0 or doc_mag == 0:
            scores.append(0.0)
            continue
        dot_product = sum(query_vec[i] * doc_vec[i] for i in range(len(vocab)))
        cosine_sim = dot_product / (query_mag * doc_mag)
        scores.append(cosine_sim)
        
    return scores

def calculate_gemini_similarity(query: str, documents: List[str]) -> List[float]:
    """Calculate semantic similarity using Gemini Embeddings API if available."""
    api_key = os.environ.get('GOOGLE_API_KEY', '')
    if not api_key or not GENAI_AVAILABLE:
        return []
    try:
        genai.configure(api_key=api_key)
        # Embed query
        query_emb = genai.embed_content(
            model="models/embedding-001",
            content=query,
            task_type="retrieval_query"
        )['embedding']
        
        # Embed documents
        doc_embs = genai.embed_content(
            model="models/embedding-001",
            content=documents,
            task_type="retrieval_document"
        )['embedding']
        
        def dot_product(v1, v2):
            return sum(x * y for x, y in zip(v1, v2))
            
        def norm(v):
            return math.sqrt(sum(x * x for x in v))
            
        q_norm = norm(query_emb)
        scores = []
        for d_emb in doc_embs:
            d_norm = norm(d_emb)
            if q_norm == 0 or d_norm == 0:
                scores.append(0.0)
            else:
                scores.append(dot_product(query_emb, d_emb) / (q_norm * d_norm))
        return scores
    except Exception:
        # Fallback to TF-IDF on error
        return []

def calculate_semantic_scores(query: str, documents: List[str]) -> List[float]:
    """Compute semantic relevance scores, trying Gemini first, falling back to TF-IDF."""
    scores = calculate_gemini_similarity(query, documents)
    if not scores:
        scores = calculate_tf_idf_similarity(query, documents)
    return [round(s, 2) for s in scores]

# --- Core Retrieval Logic ---

def get_competitor_evidence(conn: duckdb.DuckDBPyConnection,
                            region: str, product: str = None,
                            query: str = "competitor price reduction discount",
                            date_range: tuple = None) -> List[Dict]:
    """Retrieve competitor price/event evidence with semantic scoring."""
    periods = get_date_periods(conn)
    start = date_range[0] if date_range else periods['previous_start']
    end = date_range[1] if date_range else periods['current_end']
    
    product_filter = f"AND product = '{product}'" if product else ""
    
    results = conn.execute(f"""
        SELECT date, region, product, competitor_name, competitor_price,
               event_type, description
        FROM competitor
        WHERE region = '{region}' {product_filter}
        AND date BETWEEN '{start}' AND '{end}'
        ORDER BY date DESC
    """).fetchdf()
    
    if results.empty:
        return []
        
    descriptions = results['description'].tolist()
    relevance_scores = calculate_semantic_scores(query, descriptions)
    
    evidence = []
    for idx, row in results.iterrows():
        score = relevance_scores[idx] if idx < len(relevance_scores) else 0.5
        
        why_relevant = "Keyword overlap" if score > 0.3 else "General temporal overlap"
        if "price" in query.lower() and "price" in row['description'].lower():
            why_relevant = "Direct competitor price shift description matching query"
            
        evidence.append({
            'source': 'Competitor Events',
            'date': str(row['date'])[:10],
            'region': row['region'],
            'product': row['product'],
            'detail': (f"{row['competitor_name']}: {row['description']}. "
                      f"Competitor price: ₹{row['competitor_price']:,.0f}"),
            'ticket_id': None,
            'event_type': row['event_type'],
            'relevance_score': score,
            'why_relevant': why_relevant
        })
        
    evidence.sort(key=lambda x: x['relevance_score'], reverse=True)
    return evidence

def get_support_evidence(conn: duckdb.DuckDBPyConnection,
                         region: str, product: str = None,
                         query: str = "delivery delays package shipment backlog late SLA missed",
                         date_range: tuple = None) -> List[Dict]:
    """Retrieve support ticket evidence scored semantically against query."""
    periods = get_date_periods(conn)
    start = date_range[0] if date_range else periods['previous_start']
    end = date_range[1] if date_range else periods['current_end']
    
    product_filter = f"AND product = '{product}'" if product else ""
    
    results = conn.execute(f"""
        SELECT date, region, product, ticket_id, ticket_text, issue_type, severity
        FROM support
        WHERE region = '{region}' {product_filter}
        AND date BETWEEN '{start}' AND '{end}'
        ORDER BY date DESC
    """).fetchdf()
    
    if results.empty:
        return []
        
    texts = results['ticket_text'].tolist()
    relevance_scores = calculate_semantic_scores(query, texts)
    
    evidence = []
    for idx, row in results.iterrows():
        score = relevance_scores[idx] if idx < len(relevance_scores) else 0.5
        
        why_relevant = "Low similarity"
        if score >= 0.7:
            why_relevant = "Strong semantic synonym match"
        elif score >= 0.4:
            why_relevant = "Moderate semantic similarity"
        elif row['issue_type'] == 'delivery_delay':
            why_relevant = "Explicit category match"
            score = max(score, 0.7)
            
        evidence.append({
            'source': 'Support Tickets',
            'date': str(row['date'])[:10],
            'region': row['region'],
            'product': row['product'],
            'detail': f"[{row['severity'].upper()}] {row['ticket_text']}",
            'ticket_id': row['ticket_id'],
            'issue_type': row['issue_type'],
            'relevance_score': score,
            'why_relevant': why_relevant
        })
        
    evidence.sort(key=lambda x: x['relevance_score'], reverse=True)
    return evidence

def get_marketing_evidence(conn: duckdb.DuckDBPyConnection,
                           region: str, product: str = None,
                           date_range: tuple = None) -> List[Dict]:
    """Retrieve marketing spend performance evidence (Numeric - always relevance score 1.0)."""
    periods = get_date_periods(conn)
    start = date_range[0] if date_range else periods['previous_start']
    end = date_range[1] if date_range else periods['current_end']
    
    product_filter = f"AND product = '{product}'" if product else ""
    
    results = conn.execute(f"""
        SELECT date, region, product, campaign, spend, clicks, conversions
        FROM marketing
        WHERE region = '{region}' {product_filter}
        AND date BETWEEN '{start}' AND '{end}'
        ORDER BY date DESC
    """).fetchdf()
    
    evidence = []
    for _, row in results.iterrows():
        evidence.append({
            'source': 'Marketing Data',
            'date': str(row['date'])[:10],
            'region': row['region'],
            'product': row['product'],
            'detail': (f"Campaign: {row['campaign']}, "
                      f"Spend: ₹{row['spend']:,.0f}, "
                      f"Clicks: {row['clicks']:,}, "
                      f"Conversions: {row['conversions']:,}"),
            'ticket_id': None,
            'campaign': row['campaign'],
            'relevance_score': 1.0,
            'why_relevant': "Direct metric record for campaign performance"
        })
        
    return evidence

# --- New Hackathon Additions (Contradictions & Coverage) ---

def get_contradicting_evidence(conn: duckdb.DuckDBPyConnection,
                               region: str, product: str = None) -> List[Dict]:
    """Retrieve contradicting evidence that opposes the negative drivers."""
    periods = get_date_periods(conn)
    product_filter = f"AND product = '{product}'" if product else ""
    
    contradictions = []
    
    # Query CTR in marketing to see if any campaigns are highly efficient
    ctr_results = conn.execute(f"""
        SELECT campaign, spend, clicks, conversions,
               CASE WHEN clicks > 0 THEN conversions * 1.0 / clicks ELSE 0 END as ctr
        FROM marketing
        WHERE region = '{region}' {product_filter}
        AND date BETWEEN '{periods['current_start']}' AND '{periods['current_end']}'
    """).fetchdf()
    
    for _, row in ctr_results.iterrows():
        # High CTR campaign contradicts full marketing collapse
        if row['ctr'] >= 0.05:
            contradictions.append({
                'source': 'Marketing ROI Analysis',
                'date': periods['current_start'],
                'region': region,
                'product': product or 'All',
                'detail': f"Campaign '{row['campaign']}' shows high conversion rate ({row['ctr']*100:.1f}%), opposing marketing drop.",
                'relevance_score': round(float(row['ctr'] * 15.0), 2),  # proportional score
                'why_contradictory': "High campaign conversion efficiency contradicts the marketing failure hypothesis."
            })
            
    # Look for positive customer support indicators
    # We query tickets matching "on time", "fast", or "satisfied"
    positive_tickets = conn.execute(f"""
        SELECT ticket_id, ticket_text, date, severity FROM support
        WHERE region = '{region}' {product_filter}
        AND (ticket_text LIKE '%on time%' OR ticket_text LIKE '%fast%' OR ticket_text LIKE '%satisfied%')
        LIMIT 3
    """).fetchdf()
    
    for _, row in positive_tickets.iterrows():
        contradictions.append({
            'source': 'Customer Sentiment Analysis',
            'date': str(row['date'])[:10],
            'region': region,
            'product': product or 'All',
            'detail': f"[{row['severity'].upper()}] {row['ticket_text']}",
            'ticket_id': row['ticket_id'],
            'relevance_score': 0.80,
            'why_contradictory': "Explicit customer confirmation of fast or on-time shipping opposes delivery backlog."
        })
        
    return contradictions

def calculate_evidence_coverage(drivers: List[Dict], evidence: Dict[str, List[Dict]]) -> Dict[str, Any]:
    """Calculate how completely the available evidence supports the drivers.
    
    Returns:
        Dict containing total_coverage_pct (int) and source_checklist list of dicts.
    """
    if not drivers:
        return {'score': 100, 'checklist': []}
        
    checklist = []
    scores = []
    
    for driver in drivers:
        name = driver['driver_name'].lower()
        if 'other' in name:
            continue
            
        if 'competitor' in name or 'price' in name:
            # Expected competitor events & internal sales logs
            has_comp_events = len(evidence.get('competitor', [])) > 0
            checklist.append({'driver': driver['driver_name'], 'source': 'Competitor events logs', 'available': has_comp_events})
            checklist.append({'driver': driver['driver_name'], 'source': 'Sales discount logs', 'available': True}) # sales always available
            scores.extend([100 if has_comp_events else 0, 100])
            
        elif 'delivery' in name or 'support' in name:
            # Expected support delay tickets, logistics logs (simulated), customer satisfaction logs (simulated)
            has_tickets = len(evidence.get('support', [])) > 0
            checklist.append({'driver': driver['driver_name'], 'source': 'Customer support delay complaints', 'available': has_tickets})
            checklist.append({'driver': driver['driver_name'], 'source': 'Logistics transit records', 'available': True})
            checklist.append({'driver': driver['driver_name'], 'source': 'Direct client feedback transcripts', 'available': False})
            scores.extend([100 if has_tickets else 0, 100, 0])
            
        elif 'marketing' in name:
            # Expected weekly campaign spend, CTR conversion rates, ad manager telemetry (simulated)
            has_mkt = len(evidence.get('marketing', [])) > 0
            checklist.append({'driver': driver['driver_name'], 'source': 'Weekly campaign spend logs', 'available': has_mkt})
            checklist.append({'driver': driver['driver_name'], 'source': 'Click CTR logs', 'available': has_mkt})
            checklist.append({'driver': driver['driver_name'], 'source': 'Ad manager telemetry', 'available': False})
            scores.extend([100 if has_mkt else 0, 100 if has_mkt else 0, 0])
            
    coverage_score = int(sum(scores) / len(scores)) if scores else 100
    
    return {
        'score': coverage_score,
        'checklist': checklist
    }

def get_all_evidence(conn: duckdb.DuckDBPyConnection,
                     region: str, product: str = None) -> Dict[str, List[Dict]]:
    """Get all evidence scored semantically for a region/product."""
    return {
        'competitor': get_competitor_evidence(conn, region, product),
        'support': get_support_evidence(conn, region, product),
        'marketing': get_marketing_evidence(conn, region, product)
    }
