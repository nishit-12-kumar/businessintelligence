# BusinessIntelligence.ai

AI-powered business intelligence platform that detects KPI anomalies, investigates root causes, and provides evidence-backed explanations personalized by role.

## Features

This prototype demonstrates a complete end-to-end intelligent BI workflow, fulfilling 22 core requirements:
- Multi-dimensional data generation (Sales, Marketing, Support, Competitor)
- Data ingestion and semantic mapping
- Role-based access control (Security)
- Automated metric evaluation (Anomaly detection)
- Cross-functional root cause analysis
- LLM-powered insights (Gemini 2.0 Flash)
- Evidence tracking and low-confidence abstention
- Executive and Regional Manager dashboards

## Setup Instructions

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the root directory and add your Google API key:
```env
GOOGLE_API_KEY="your_gemini_api_key_here"
```

3. Generate sample data:
```bash
python data/generate_data.py
```

4. Run the Streamlit application:
```bash
streamlit run app/streamlit_app.py
```

## Architecture

BusinessIntelligence.ai uses a layered architecture to maintain clean separation of concerns:
- **Data Layer:** DuckDB in-memory engine parsing synthetic CSVs.
- **Semantic Layer:** YAML-based KPI definitions linking metrics to data sources.
- **Security Layer:** Intercepts data requests to enforce role-based access before querying.
- **Analytics Engine:** Detects anomalies using statistical thresholds.
- **Investigation Engine:** Gathers drivers and contextual data when anomalies are detected.
- **LLM Synthesis:** Analyzes cross-functional data using Google's Gemini models to generate human-readable narratives.
- **Presentation Layer:** Streamlit UI tailored to the active user's role.

## Demo Scenarios

The application comes with predefined scenarios to showcase the system's capabilities:

1. **South Revenue Drop (Multi-factor analysis)**: Demonstrates how the system links competitor price drops, reduced marketing spend, and delivery issues to explain a revenue shortfall.
2. **East TabMax (Low-confidence abstention)**: Shows the system's ability to admit when there isn't enough data to conclusively explain an anomaly.
3. **NovaWatch (Sparse history)**: Highlights handling of newly launched products with limited historical data.
4. **Regional Manager Security (Access denial)**: Validates that a user with restricted access (e.g., South Manager) cannot view unauthorized data.

## Technology Stack

- **UI:** Streamlit
- **Data Processing:** DuckDB, Pandas
- **Visualization:** Plotly
- **AI:** Google Generative AI (Gemini 2.0 Flash)
- **Configuration:** YAML
