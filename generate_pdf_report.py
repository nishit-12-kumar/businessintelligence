import os
import sys
import hashlib

# Patch hashlib.md5 for Python 3.8 compatibility with ReportLab 4.x
_orig_md5 = hashlib.md5
def _safe_md5(*args, **kwargs):
    kwargs.pop('usedforsecurity', None)
    return _orig_md5(*args, **kwargs)
hashlib.md5 = _safe_md5

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Canvas for adding page numbers and running header/footer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#495057"))
        
        # Draw header (on pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "BusinessIntelligence.ai — Technical Project & Architecture Report")
            self.setStrokeColor(colors.HexColor("#dee2e6"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)
            
        # Draw footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 36, page_str)
        self.drawString(54, 36, "CONFIDENTIAL — Decision Intelligence Technical Documentation")
        self.setStrokeColor(colors.HexColor("#dee2e6"))
        self.setLineWidth(0.5)
        self.line(54, 48, 558, 48)
        
        self.restoreState()


def create_pdf(filename="BusinessIntelligence_AI_Detailed_Report.pdf"):
    pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Palette
    PRIMARY = colors.HexColor("#1e3a8a")     # Deep Navy
    SECONDARY = colors.HexColor("#0d6efd")   # Accent Blue
    DARK_TEXT = colors.HexColor("#212529")   # Charcoal
    LIGHT_BG = colors.HexColor("#f8f9fa")    # Off white
    BORDER_COLOR = colors.HexColor("#e9ecef")# Light border
    ALERT_BG = colors.HexColor("#e7f5ff")    # Soft blue container
    ALERT_BORDER = colors.HexColor("#4dabf7")
    
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=PRIMARY,
        spaceAfter=10
    )
    
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#6c757d"),
        spaceAfter=20
    )
    
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=PRIMARY,
        spaceBefore=16,
        spaceAfter=8,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=SECONDARY,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=DARK_TEXT,
        spaceAfter=8
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#2b8a3e"),
        backColor=LIGHT_BG,
        borderColor=BORDER_COLOR,
        borderWidth=1,
        borderPadding=6,
        spaceAfter=8
    )

    story = []

    # Title Block
    story.append(Paragraph("BusinessIntelligence.ai", title_style))
    story.append(Paragraph("Complete Technical Architecture, Analytics Engine & Field Calculation Report", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=15))

    # Executive Overview
    story.append(Paragraph("1. Executive Overview & System Architecture", h1_style))
    story.append(Paragraph(
        "<b>BusinessIntelligence.ai</b> is an enterprise Decision Intelligence product designed to automatically detect, "
        "investigate, attribute, and recommend business actions for revenue and KPI anomalies. Unlike standard LLM "
        "applications that ask generative AI models to calculate numbers (introducing hallucinations and non-deterministic results), "
        "BusinessIntelligence.ai enforces a strict separation between <b>Deterministic Analytics</b> and <b>Generative Narration</b>.",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>Core Architecture Principles:</b><br/>"
        "• <b>SQL & Math Core (DuckDB):</b> All KPI numbers, time-series aggregations, and variance decompositions are calculated via SQL.<br/>"
        "• <b>Deterministic Attribution:</b> Price effect and volume effect driver analysis are calculated using closed-form financial math.<br/>"
        "• <b>5-Pillar Statistical Confidence Scoring:</b> Quantitative confidence score (0-100%) computed from data quality, coverage, driver agreement, evidence relevance, and attribution certainty.<br/>"
        "• <b>Pre-Query Security Interceptor:</b> Role-based access control (RBAC) evaluates permissions before database queries are constructed.<br/>"
        "• <b>Persona-Adapted Narration:</b> Generative AI (Google Gemini) receives strictly structured statistics and synthesized evidence to produce C-Suite or Regional Manager briefings.",
        body_style
    ))

    story.append(Spacer(1, 10))

    # Component Table
    story.append(Paragraph("<b>System Module Layout:</b>", h2_style))
    module_data = [
        [Paragraph("<b>Module Path</b>", body_style), Paragraph("<b>Component Name</b>", body_style), Paragraph("<b>Function & Responsibility</b>", body_style)],
        [Paragraph("<code>semantic/kpi_definitions.yaml</code>", body_style), Paragraph("Semantic Contract", body_style), Paragraph("Single Source of Truth for KPIs, SQL formulas, refresh cadences & RBAC access rules.", body_style)],
        [Paragraph("<code>security/authorization.py</code>", body_style), Paragraph("Security Interceptor", body_style), Paragraph("Enforces pre-query region authorization checks before DuckDB execution.", body_style)],
        [Paragraph("<code>analytics/kpi_engine.py</code>", body_style), Paragraph("KPI Calculation Engine", body_style), Paragraph("DuckDB SQL query parser comparing 7-day current vs previous period statistics.", body_style)],
        [Paragraph("<code>analytics/anomaly_detection.py</code>", body_style), Paragraph("Anomaly & Sparse Checker", body_style), Paragraph("Threshold magnitude evaluation and product history baseline depth check (<14 days).", body_style)],
        [Paragraph("<code>analytics/driver_analysis.py</code>", body_style), Paragraph("Variance Decomposition", body_style), Paragraph("Isolates price effects, volume effects, marketing contribution & delivery issue impacts.", body_style)],
        [Paragraph("<code>retrieval/retriever.py</code>", body_style), Paragraph("Semantic Retriever", body_style), Paragraph("TF-IDF cosine similarity & Gemini dense embeddings matching logs & tickets.", body_style)],
        [Paragraph("<code>analytics/impact_calculator.py</code>", body_style), Paragraph("Impact & Exposure", body_style), Paragraph("Scales 7-day metric changes into monthly exposure (₹) and normalized 0-100 impact scores.", body_style)],
        [Paragraph("<code>analytics/recommendation_engine.py</code>", body_style), Paragraph("Guardrailed Rule Engine", body_style), Paragraph("Generates actionable recommendations gated by system confidence score levels.", body_style)],
        [Paragraph("<code>analytics/simulator.py</code>", body_style), Paragraph("What-If Simulator", body_style), Paragraph("Linear elastic scenario model projecting monthly financial recovery potential.", body_style)],
        [Paragraph("<code>llm/narrative.py</code>", body_style), Paragraph("Persona Narrator", body_style), Paragraph("Generates Gemini-powered C-Level / Regional Manager executive summaries with fallback templates.", body_style)]
    ]
    
    t_module = Table(module_data, colWidths=[150, 110, 244])
    t_module.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_module)

    story.append(Spacer(1, 15))

    # KPI Calculation Section
    story.append(Paragraph("2. Detailed KPI Calculation Engine & Formulas", h1_style))
    story.append(Paragraph(
        "The KPI Engine calculates performance metrics by evaluating a rolling 14-day window relative to the dataset's maximum date (<code>max_date</code>):<br/>"
        "• <b>Current Period (P<sub>curr</sub>):</b> <code>max_date - 6 days</code> to <code>max_date</code> (7 days inclusive)<br/>"
        "• <b>Previous Period (P<sub>prev</sub>):</b> <code>max_date - 13 days</code> to <code>max_date - 7 days</code> (7 days inclusive)",
        body_style
    ))

    kpi_formula_data = [
        [Paragraph("<b>KPI Name</b>", body_style), Paragraph("<b>Mathematical Formula</b>", body_style), Paragraph("<b>SQL Query Logic</b>", body_style)],
        [Paragraph("<b>Revenue</b>", body_style), Paragraph("$$\\sum (Units \\times Price)$$", body_style), Paragraph("<code>SELECT COALESCE(SUM(units * price), 0) FROM sales WHERE ...</code>", body_style)],
        [Paragraph("<b>Orders</b>", body_style), Paragraph("$$\\sum Orders$$", body_style), Paragraph("<code>SELECT COALESCE(SUM(orders), 0) FROM sales WHERE ...</code>", body_style)],
        [Paragraph("<b>ASP (Avg Selling Price)</b>", body_style), Paragraph("$$\\frac{\\sum Revenue}{\\sum Units}$$", body_style), Paragraph("<code>SELECT SUM(units * price) / SUM(units) FROM sales WHERE ...</code>", body_style)],
        [Paragraph("<b>Conversion Rate</b>", body_style), Paragraph("$$\\frac{\\sum Orders}{\\sum Clicks}$$", body_style), Paragraph("<code>SELECT s.orders * 1.0 / m.clicks FROM sales s, marketing m WHERE ...</code>", body_style)]
    ]
    t_kpi = Table(kpi_formula_data, colWidths=[100, 150, 254])
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_kpi)

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<b>Percentage Movement Formula:</b><br/>"
        "Change % is calculated as: <code>Change % = ((V_current - V_previous) / V_previous) * 100</code>.<br/>"
        "If <code>abs(Change %) >= Threshold</code> (Revenue: 5%, Orders: 5%, ASP: 3%, Conversion: 5%), an anomaly alert is triggered.",
        body_style
    ))

    story.append(Spacer(1, 15))

    # Driver Breakdown Math
    story.append(Paragraph("3. Driver Decomposition & Variance Analysis Math", h1_style))
    story.append(Paragraph(
        "For revenue anomalies, the engine decomposes the total revenue change (<code>Total Change = R_curr - R_prev</code>) into isolated underlying drivers:",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>1. Price Effect:</b> Isolates revenue shift caused strictly by average selling price changes:<br/>"
        "<code>Price Effect = (Price_curr - Price_prev) * Units_curr</code><br/><br/>"
        "<b>2. Volume Effect:</b> Isolates revenue shift caused strictly by change in total units sold:<br/>"
        "<code>Volume Effect = (Units_curr - Units_prev) * Price_prev</code><br/><br/>"
        "<b>3. Marketing Sub-Decomposition:</b> Attributes portion of volume drop to marketing campaign conversion changes:<br/>"
        "<code>Marketing Impact = Conversion_Change_% * Price_prev * abs(Units_curr - Units_prev)</code><br/><br/>"
        "<b>4. Delivery Impact:</b> Evaluates support tickets logged for delivery delays:<br/>"
        "<code>Estimated Lost Orders = (Severe Tickets * 1.5) + (Minor Tickets * 0.5)</code><br/>"
        "<code>Delivery Impact = Estimated Lost Orders * Price_prev</code><br/><br/>"
        "<b>5. Contribution Normalization:</b> Converts raw impact into percentages of total revenue change. "
        "If unallocated residual variance exists, an <i>'Other factors'</i> driver is added to guarantee driver contributions total 100%.",
        body_style
    ))

    story.append(PageBreak())

    # Confidence Engine Detail
    story.append(Paragraph("4. The 5-Pillar Statistical Confidence Score Engine", h1_style))
    story.append(Paragraph(
        "The system confidence score (0 - 100%) quantifies the reliability of the analysis before recommending business actions. "
        "It combines 5 weighted base pillars and applies dynamic penalties for stale data or conflicting evidence.",
        body_style
    ))

    conf_data = [
        [Paragraph("<b>Pillar</b>", body_style), Paragraph("<b>Weight</b>", body_style), Paragraph("<b>Calculation Logic & Scoring Rules</b>", body_style)],
        [Paragraph("<b>P1: Data Quality</b>", body_style), Paragraph("20%", body_style), Paragraph("Base score = 95 if marketing data exists (50 if missing). Subtracts 15 if competitor data is missing. Range: [0, 100].", body_style)],
        [Paragraph("<b>P2: Historical Coverage</b>", body_style), Paragraph("20%", body_style), Paragraph("Score = 95 if product history >= 14 days; drops to 30 if history is sparse (< 14 days).", body_style)],
        [Paragraph("<b>P3: Driver Agreement</b>", body_style), Paragraph("20%", body_style), Paragraph("Score = 85 if >= 3 aligned drivers identified; 70 if >= 1 driver; 30 if 0 drivers.", body_style)],
        [Paragraph("<b>P4: Evidence Relevance</b>", body_style), Paragraph("20%", body_style), Paragraph("Score = 90 if competitor AND support evidence exist; 40 if neither exist; 80 otherwise.", body_style)],
        [Paragraph("<b>P5: Attribution Certainty</b>", body_style), Paragraph("20%", body_style), Paragraph("Score = min(abs(Explained Driver Variance) / abs(Total Revenue Change), 1.0) * 100.", body_style)]
    ]
    t_conf = Table(conf_data, colWidths=[130, 60, 314])
    t_conf.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_conf)

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<b>Base Score Formula:</b><br/>"
        "<code>Base Score = (0.20 * P1) + (0.20 * P2) + (0.20 * P3) + (0.20 * P4) + (0.20 * P5)</code><br/><br/>"
        "<b>Dynamic Deductions & Penalties:</b><br/>"
        "• <b>Stale Marketing Data Penalty:</b> -15% if marketing source age > 168 hours.<br/>"
        "• <b>Stale Competitor Data Penalty:</b> -15% if competitor source age > 72 hours.<br/>"
        "• <b>Contradiction Penalty:</b> -20% if conflicting signals detected (e.g. high campaign CTR or positive shipping tickets while delivery backlog is claimed).<br/><br/>"
        "<b>Final Confidence Score:</b><br/>"
        "<code>Final Score = max(10, Base Score - Deductions)</code><br/>"
        "• <b>HIGH Confidence:</b> Score >= 80% &nbsp;|&nbsp; <b>MEDIUM Confidence:</b> 55% <= Score < 80% &nbsp;|&nbsp; <b>LOW Confidence:</b> Score < 55%",
        body_style
    ))

    story.append(Spacer(1, 15))

    # Business Exposure & Impact Math
    story.append(Paragraph("5. Business Financial Exposure & Impact Calculator", h1_style))
    story.append(Paragraph(
        "The impact calculator scales weekly period changes to a <b>monthly financial exposure</b> (4.33 weeks/month) and computes a normalized 0-100 Impact Score:",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>Monthly Exposure Math:</b><br/>"
        "• <b>Revenue:</b> <code>Monthly Exposure = abs(Current_Val - Prev_Val) * 4.33</code><br/>"
        "• <b>Orders:</b> <code>Monthly Exposure = (abs(Orders_diff) * ₹35,000 avg ASP) * 4.33</code><br/>"
        "• <b>ASP:</b> <code>Monthly Exposure = (abs(ASP_diff) * 300 units/week) * 4.33</code><br/>"
        "• <b>Conversion Rate:</b> <code>Monthly Exposure = (abs(CR_diff) * 5,000 clicks * ₹35,000 ASP) * 4.33</code><br/><br/>"
        "<b>Normalized Impact Score Formula:</b><br/>"
        "<code>Raw Impact = w_kpi * abs(Change_%) * log10(Monthly_Exposure + 1) * (Confidence_% / 100)</code><br/>"
        "<code>Impact Score = min(round(Raw Impact * 3.5, 1), 100.0)</code><br/>"
        "• <i>KPI Multipliers (w_kpi):</i> Revenue = 1.0, Conversion Rate = 0.8, Orders = 0.7, ASP = 0.6.<br/>"
        "• <i>Impact Categories:</i> <b>HIGH</b> (Score >= 60), <b>MEDIUM</b> (25 <= Score < 60), <b>LOW</b> (Score < 25).<br/>"
        "• <i>Estimated Recovery Potential:</i> Calculated as 40% (min) to 70% (max) of monthly financial exposure.",
        body_style
    ))

    story.append(Spacer(1, 15))

    # Guardrail Recommendation Rules
    story.append(Paragraph("6. Confidence Guardrails for Recommendations", h1_style))
    story.append(Paragraph(
        "The system confidence score strictly gates the risk level of generated business recommendations:",
        body_style
    ))

    rec_guardrail_data = [
        [Paragraph("<b>Confidence Level</b>", body_style), Paragraph("<b>Guardrail Policy</b>", body_style), Paragraph("<b>Recommendation Type</b>", body_style)],
        [Paragraph("<b>LOW (&lt; 50%)</b>", body_style), Paragraph("<b>Abstain from strategic changes.</b> High risk of error on incomplete data.", body_style), Paragraph("<i>'Continue monitoring & collect additional data.'</i> (Risk avoidance)", body_style)],
        [Paragraph("<b>MEDIUM (50% - 75%)</b>", body_style), Paragraph("<b>Advisory & Pilot testing.</b> Validate telemetry before scaling spend.", body_style), Paragraph("<i>'Conduct competitive audit & run limited pilot promotions.'</i>", body_style)],
        [Paragraph("<b>HIGH (&gt; 75%)</b>", body_style), Paragraph("<b>Full Action Execution.</b> Clear, high-priority operational response.", body_style), Paragraph("<i>'Review and adjust pricing model in region to match competitor.'</i>", body_style)]
    ]
    t_rec = Table(rec_guardrail_data, colWidths=[110, 180, 214])
    t_rec.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_rec)

    story.append(Spacer(1, 15))

    # Evidence Retrieval & Similarity Math
    story.append(Paragraph("7. Semantic Evidence Retrieval & Cosine Similarity Math", h1_style))
    story.append(Paragraph(
        "Supporting logs, competitor announcements, and customer tickets are matched against identified drivers using vector similarity math:",
        body_style
    ))
    story.append(Paragraph(
        "<b>Pure Python TF-IDF Cosine Similarity:</b><br/>"
        "For query <i>q</i> and document text <i>d</i> over vocabulary <i>V</i>:<br/>"
        "<code>TF(t, d) = count(t, d)</code> &nbsp;|&nbsp; <code>IDF(t) = ln(1 + N / (1 + DF(t)))</code><br/>"
        "<code>Vector(d)[i] = TF(t_i, d) * IDF(t_i)</code><br/>"
        "<code>Cosine Similarity(q, d) = (v_q . v_d) / (||v_q|| * ||v_d||)</code><br/><br/>"
        "If a Gemini API key is active, dense vector embeddings (<code>models/embedding-001</code>) are computed automatically with TF-IDF as a fallback.",
        body_style
    ))

    story.append(Spacer(1, 15))

    # What-If Simulator Math
    story.append(Paragraph("8. What-If Scenario Simulator & Linear Elasticity Model", h1_style))
    story.append(Paragraph(
        "The scenario simulator models potential revenue recovery if a negative driver is mitigated:<br/>"
        "<code>Recovery % = Proposed Driver Impact % - Original Driver Impact %</code><br/>"
        "<code>Monthly Estimated Recovery (₹) = (Current Weekly Value * 4.33) * (Recovery % / 100)</code><br/>"
        "All simulation metrics are explicitly tagged as <code>🟡 SIMULATED SCENARIO</code> to maintain clean separation from observed historical data.",
        body_style
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF report at: {pdf_path}")
    return pdf_path

if __name__ == '__main__':
    create_pdf()
