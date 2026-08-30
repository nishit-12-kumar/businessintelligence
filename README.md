# BusinessIntelligence.ai — Decision Intelligence Web Application

A Decision Intelligence web application built with **Flask**, **DuckDB**, **Jinja2**, **Vanilla CSS**, and **JavaScript**, featuring a visual design system inspired by [Superlist](https://www.superlist.com/).

BusinessIntelligence.ai bridges the gap between passive dashboards and defensible business decisions. It automatically detects KPI anomalies, investigates root-cause drivers via variance decomposition, validates empirical correlation via statistical hypothesis testing, matches knowledge graph ontology paths, benchmarks against live market pricing, scores 3-way hybrid confidence, calculates financial exposure, enforces pre-query RBAC authorization across 7 role tiers, connects to external enterprise databases, generates downloadable PDF reports, and recommends guardrailed actions with role-adapted AI executive summaries.

---

## 🏛️ Architecture & Execution Pipeline

The application adheres to a strict layered Decision Intelligence architecture:

```text
Data Layer (sales.csv, marketing.csv, support.csv, competitor.csv, inventory.csv)
   ↓
Semantic Layer (semantic/kpi_definitions.yaml + validator.py)
   ↓
Security & RBAC Layer (security/authorization.py — Pre-query Enforcement across 7 Roles)
   ↓
KPI & Analytics Engine (analytics/kpi_engine.py — DuckDB SQL for 5 Core KPIs)
   ↓
Anomaly Detection (analytics/anomaly_detection.py — Baseline & Sparse History)
   ↓
Investigation Engine (analytics/driver_analysis.py — Variance Decomposition)
   ↓
Statistical Hypothesis Engine (analytics/statistical_confidence.py — Pearson r, R², p-value, H0)
   ↓
Knowledge Graph Layer (semantic/knowledge_graph.py — 5-Node Traversal & Wikidata API)
   ↓
External Market Benchmark (retrieval/external_pricing_api.py — Public E-Commerce REST API)
   ↓
Evidence Retrieval (retrieval/retriever.py — Vector Similarity & Contradiction Detection)
   ↓
Hybrid Confidence & Sanity Check (45% Statistical + 20% Knowledge Graph + 35% AI Vector)
   ↓
Business Impact Calculation (analytics/impact_calculator.py — Exposure & Recovery)
   ↓
Recommendation Engine (analytics/recommendation_engine.py — Guardrailed Structured Actions)
   ↓
LLM Narrative Layer (llm/narrative.py + prompts.py — Gemini Tone Synthesis)
   ↓
Reporting Engine (generate_pdf_report.py — ReportLab Technical PDF Generation)
   ↓
Presentation Layer (Flask Web App + Superlist-Inspired UI)
```

### Deterministic Analytics vs. LLM Boundary
- **Deterministic Analytics**: KPI formulas, anomaly flags, driver contribution percentages, statistical hypothesis correlation ($r$, $R^2$, $p$-value), knowledge graph ontology matching, evidence relevance scoring, hybrid confidence scores, business exposure calculations, RBAC authorization, and structured action schemas are computed **100% deterministically in Python/SQL**.
- **LLM Functionality (Google Gemini)**: Used **strictly for narrative synthesis and persona adaptation** (Executive vs. Operations Lead vs. Regional Manager). The LLM never calculates numbers, invents data, or overrides analytics.

---

## ✨ Features & User Experience

1. **Business Pulse (`/`)**:
   - Executive health dashboard with 5 KPI cards (**Revenue, Orders, ASP, Conversion Rate, Inventory Stockout Rate**).
   - Priority attention alerts with monthly business exposure (`₹X L/mo`) and 1-click investigation routing.
   - Performing well signals and real-time data source freshness meters with stale data penalty warnings.
2. **Investigation Workspace (`/investigation`)**:
   - Continuous decision workflow:
     - **WHAT**: KPI movement comparison (Current, Previous, Change %, Anomaly Status) with Observed & Calculated badges.
     - **WHY**: Driver Contribution Breakdown with interactive Plotly bar chart + ASCII tree expander.
     - **STATISTICAL SIGNAL**: Empirical Null Hypothesis ($H_0$), Pearson correlation ($r$), $R^2$, and $p$-value table per driver.
     - **EVIDENCE**: Supporting logs with relevance bars + Contradiction alert cards + Coverage progress checklist.
     - **KNOWLEDGE GRAPH**: 5-node traversal path visualizer (`KPI → Driver → Channel → Lever → Owner → Plan`) with Wikidata API curation.
     - **HOW CONFIDENT**: Radial gauge + Sanity Check divergence mechanism + Transparent 3-way breakdown (45% Statistical, 20% Knowledge Graph, 35% AI Vector Evidence).
     - **MARKET BENCHMARK**: External competitor pricing benchmark card (Our Price, Competitor Price, Discount %, Source).
     - **STRUCTURED ACTIONS**: Guardrailed action table (`driver → lever → action → impact → owner → confidence → monitoring plan`) + Expandable prioritized action cards with `✅ Accept Action` / `❌ Reject` buttons.
     - **WHAT WOULD CHANGE MY MIND**: Reversal condition checklist.
     - **AI EXECUTIVE BRIEFING**: Role-adapted synthesis with LLM transparency breakdown.
     - **DECISION TRACE**: Step-by-step pipeline audit trail.
     - **WHAT-IF SIMULATOR**: Interactive scenario recovery slider with live monthly recovery estimates.
     - **PDF REPORT DOWNLOAD**: 1-click download of the complete `BusinessIntelligence_AI_Detailed_Report.pdf`.
     - **Abstention UX**: When products have sparse history (<14 days, e.g. NovaWatch), the engine halts attribution and clearly explains why rather than guessing.
3. **Security & RBAC (`/security`)**:
   - Role permission viewer with assigned regions and access levels (Executive, Operations Lead, Regional Managers South/North/East/West, Data Analyst).
   - **Live Pre-Query Authorization Tester**: Interactively test role access to regions and KPIs, demonstrating access granted/denied before query execution.
   - Complete 7-role RBAC policy map.
   - **External Enterprise Database Connector**: Interactively test connections and ingest remote queries from **PostgreSQL, MySQL, SQLite, Snowflake, and DuckDB** directly into analytical memory.
4. **Data Lineage & Semantics (`/lineage`)**:
   - Real-time semantic contract validation status.
   - End-to-end data pipeline flow visualizer.
   - Expandable KPI cards displaying formulas, source tables, thresholds, drivers, and access rules for all 5 metrics.
5. **Outcomes & Telemetry (`/outcomes`)**:
   - Decision learning loop metrics (Recommendations Issued, Accepted, Rejected, Acceptance Rate %).
   - Decision audit log table connected to `data/feedback.json`.
   - Performance telemetry tracking execution latency (ms), LLM API calls, and step sequence timings.
   - **LLM Economics & Production Cost Projection**: Transparent table breaking down free tier vs. commercial paid tier costs ($0.15/1M input, $0.60/1M output) and projecting monthly costs for 10,000 runs.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+ (tested on Python 3.10, 3.11, 3.12, 3.14)
- Pip

### 1. Clone & Environment Setup
```bash
git clone https://github.com/nishit-12-kumar/businessintelligence.git
cd businessintelligence

# Create virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` (optional):
```text
FLASK_SECRET_KEY=your-secure-secret-key
GOOGLE_API_KEY=your-optional-gemini-api-key
FLASK_DEBUG=1
```
*(Note: If `GOOGLE_API_KEY` is omitted, the application seamlessly uses structured offline narrative templates).*

### 3. Generate / Refresh Data
Synthetic dataset files are pre-populated in `data/`. To regenerate:
```bash
python data/generate_data.py
```

### 4. Run the Flask Web Application
```bash
python app.py
```
Open your browser at:
```text
http://127.0.0.1:5000
```

---

## 🧪 Demo Scenarios

The UI supports all core Decision Intelligence demonstration paths:

1. **South Region Revenue Drop (Primary Path)**:
   - Go to **Investigation Workspace**.
   - Select KPI: **Revenue**, Region: **South**, Product: **XPhone Pro**.
   - Click **Run Investigation**.
   - Observe -12.4% drop, drivers (Competitor pricing -50%, Delivery delays -31%, Marketing cuts -19%), Pearson correlation ($r = 0.864, p < 0.05$), 5-node knowledge graph path, external competitor benchmark, 82% confidence, and guardrailed pricing/logistics recommendations.
2. **NovaWatch Sparse History (Abstention Path)**:
   - Select KPI: **Revenue**, Region: **East**, Product: **NovaWatch**.
   - Click **Run Investigation**.
   - Observe that attribution halts with an amber **Insufficient Evidence** banner (11 days of data vs 14 days required).
3. **Inventory Stockout Rate Investigation**:
   - Select KPI: **Inventory Stockout Rate**, Region: **South**, Product: **XPhone Pro**.
   - Run investigation to inspect stockout events, warehouse SLAs, and logistics recommendations.
4. **Stale Marketing Data Simulation**:
   - Toggle **Stale Marketing** in controls or settings.
   - Run investigation and observe that confidence is penalized by 15% with an explicit data quality warning.
5. **Regional Manager RBAC Interception**:
   - Switch role to **Regional Manager (South)** via the role switcher or settings drawer.
   - Go to **Security & Access** and test querying **North** region.
   - Observe **Access Denied — Query Not Executed**.
6. **External Database Ingestion**:
   - Go to **Security & Access** → **External Enterprise Database Connector**.
   - Select engine (DuckDB / SQLite / PostgreSQL / MySQL / Snowflake), enter query, and click **Test Connection & Ingest Data**.
7. **Download PDF Investigation Report**:
   - Click **PDF Report** in the top navigation bar or trigger `/api/report/investigation` to download the comprehensive ReportLab PDF report.

---

## 🔌 API Surface

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Business Pulse page view (5 KPIs) |
| `GET` | `/investigation` | Investigation Workspace view |
| `GET` | `/security` | RBAC & External DB Connector view |
| `GET` | `/lineage` | Data Lineage & Semantic Contract view |
| `GET` | `/outcomes` | Decision Outcomes, Telemetry & LLM Economics view |
| `GET` | `/health` | Service health status |
| `GET` | `/api/pulse` | Live calculations across all 5 KPIs and anomaly alerts |
| `POST` | `/api/investigation` | Execute complete decision intelligence pipeline |
| `POST` | `/api/security/test` | Test pre-query RBAC authorization rules |
| `POST` | `/api/simulation` | Run What-If recovery scenario simulation |
| `GET` | `/api/pricing/<product>` | Fetch external competitor pricing benchmarks |
| `POST` | `/api/external-db/test` | Test connection to remote database engine |
| `POST` | `/api/external-db/ingest` | Ingest external database query into DuckDB |
| `GET` | `/api/report/investigation` | Generate and download ReportLab PDF technical report |
| `GET` | `/api/lineage` | Semantic contract validation & KPI definitions |
| `GET` | `/api/outcomes` | Outcome feedback metrics, decision logs & telemetry |
| `POST` | `/api/feedback` | Record recommendation acceptance/rejection |
| `GET` | `/api/preferences` | Retrieve session preferences |
| `POST` | `/api/preferences` | Update active role, region, and simulation modes |

---

## 🧪 Testing

Run the full automated test suite with `pytest`:
```bash
pytest tests/ -v
```

- `tests/test_analytics.py`: 20 backend unit tests validating DuckDB 5-KPI calculation, baseline anomaly detection, variance decomposition, TF-IDF retriever, statistical hypothesis correlation ($r$, $R^2$, $p$-value), knowledge graph traversal, external pricing API, external DB connector, impact calculator, guardrailed recommendations, and RBAC authorization.
- `tests/test_app.py`: 15 Flask integration tests covering all 5 views, 5-KPI pulse, statistical confidence payloads, abstention flows, RBAC enforcement, external pricing, external DB testing/ingestion, PDF report download, and feedback persistence.
