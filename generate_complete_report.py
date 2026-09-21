"""
Fix: Rewrite tbl() with direct XML text node + rebuild all table data in the docx.
Run this to regenerate a corrected Word document.
"""
import os, math, re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
from docx import Document
from docx.shared import Pt, Inches, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

DIAGRAMS_DIR = "report_diagrams"
os.makedirs(DIAGRAMS_DIR, exist_ok=True)
def dpath(name): return os.path.join(DIAGRAMS_DIR, name)
ACCENT = RGBColor(0x1F, 0x37, 0x64)
BODY   = 'Times New Roman'
MONO   = 'Courier New'

# ── Doc Helpers ───────────────────────────────────────────────────────────────

def setup_styles(doc):
    n = doc.styles['Normal']
    n.font.name = BODY; n.font.size = Pt(11)
    n.paragraph_format.line_spacing = 1.5
    n.paragraph_format.space_after  = Pt(8)
    n.paragraph_format.alignment    = WD_ALIGN_PARAGRAPH.JUSTIFY
    for sname, sz, bold, italic, caps, align, before, after in [
        ('Heading 1', 14, True,  False, True,  WD_ALIGN_PARAGRAPH.LEFT,   Pt(18), Pt(6)),
        ('Heading 2', 12, True,  False, False, WD_ALIGN_PARAGRAPH.LEFT,   Pt(14), Pt(4)),
        ('Heading 3', 11, False, True,  False, WD_ALIGN_PARAGRAPH.LEFT,   Pt(10), Pt(3)),
    ]:
        s = doc.styles[sname]
        s.font.name = BODY; s.font.size = Pt(sz); s.font.bold = bold
        s.font.italic = italic; s.font.small_caps = caps
        s.font.color.rgb = ACCENT
        s.paragraph_format.alignment    = align
        s.paragraph_format.space_before = before
        s.paragraph_format.space_after  = after
        s.paragraph_format.keep_with_next = True

def add_page_number(doc):
    section = doc.sections[0]
    footer  = section.footer
    para    = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run()
    for tag, text in [('begin', None), (None, 'PAGE'), ('end', None)]:
        if tag:
            el = OxmlElement('w:fldChar'); el.set(qn('w:fldCharType'), tag)
            run._r.append(el)
        else:
            el = OxmlElement('w:instrText'); el.text = text
            run._r.append(el)
    run.font.name = BODY; run.font.size = Pt(10)

def add_header(doc, text):
    section = doc.sections[0]
    header  = section.header
    para    = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = para.add_run(text)
    run.font.name = BODY; run.font.size = Pt(9); run.italic = True

def p(doc, text, bold_run=None, size=11, justify=True):
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if justify else WD_ALIGN_PARAGRAPH.LEFT
    if bold_run:
        r = para.add_run(bold_run); r.bold = True
        r.font.name = BODY; r.font.size = Pt(size)
    r2 = para.add_run(text)
    r2.font.name = BODY; r2.font.size = Pt(size)
    return para

def code(doc, text, caption=None):
    bdr = doc.add_paragraph()
    bdr.paragraph_format.space_before = Pt(4)
    bdr.paragraph_format.space_after  = Pt(2)
    bdr.paragraph_format.left_indent  = Inches(0.25)
    pPr = bdr._p.get_or_add_pPr()
    shd = OxmlElement('w:shd'); shd.set(qn('w:fill'), 'EFF2F7'); shd.set(qn('w:val'), 'clear')
    pPr.append(shd)
    run = bdr.add_run(text)
    run.font.name = MONO; run.font.size = Pt(8.5)
    if caption:
        cp = doc.add_paragraph(caption); cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in cp.runs: r.font.name = BODY; r.font.size = Pt(9); r.italic = True

def fig(doc, path, caption, width=Inches(5.5)):
    doc.add_picture(path, width=width)
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp = doc.add_paragraph(caption); cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in cp.runs: r.font.name = BODY; r.font.size = Pt(9); r.italic = True

def set_cell_text(cell, text, bold=False, center=False, fontsize=9, color=None, bg=None):
    """Properly set cell text by adding a run – avoids the empty-run bug."""
    cell.paragraphs[0].clear()   # remove any existing runs
    run = cell.paragraphs[0].add_run(str(text))
    run.font.name = BODY; run.font.size = Pt(fontsize); run.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)
    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.LEFT
    cell.paragraphs[0].paragraph_format.space_before = Pt(2)
    cell.paragraphs[0].paragraph_format.space_after  = Pt(2)
    if bg:
        shd = OxmlElement('w:shd')
        shd.set(qn('w:fill'), bg); shd.set(qn('w:val'), 'clear')
        cell._tc.get_or_add_tcPr().append(shd)

def tbl(doc, headers, rows, widths=None, hcolor='1F3864', center_cols=None):
    """Build a table with properly populated cells."""
    if center_cols is None:
        center_cols = set(range(len(headers)))

    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = 'Table Grid'

    # Header row
    for i, h in enumerate(headers):
        set_cell_text(table.rows[0].cells[i], h, bold=True, center=True, fontsize=9,
                      color=(255, 255, 255), bg=hcolor)

    # Data rows
    for ri, row_data in enumerate(rows):
        row = table.add_row()
        alt_bg = 'F1F5F9' if ri % 2 == 0 else None
        for ci, v in enumerate(row_data):
            center = ci in center_cols
            set_cell_text(row.cells[ci], v, center=center, fontsize=9,
                          bg=alt_bg)

    # Set column widths
    if widths:
        for row in table.rows:
            for i, w in enumerate(widths):
                if i < len(row.cells):
                    row.cells[i].width = w

    # Allow word wrap in all cells
    for row in table.rows:
        for cell in row.cells:
            tcPr = cell._tc.get_or_add_tcPr()
            noWrap = OxmlElement('w:noWrap')
            noWrap.set(qn('w:val'), '0')
            tcPr.append(noWrap)

    doc.add_paragraph()
    return table

def bullets(doc, items):
    for item in items:
        para = doc.add_paragraph(style='List Bullet')
        para.paragraph_format.left_indent = Inches(0.4)
        r = para.add_run(item); r.font.name = BODY; r.font.size = Pt(11)

def numbered(doc, items):
    for item in items:
        para = doc.add_paragraph(style='List Number')
        para.paragraph_format.left_indent = Inches(0.4)
        r = para.add_run(item); r.font.name = BODY; r.font.size = Pt(11)

# ── Diagrams (reuse existing PNGs from report_diagrams/) ─────────────────────
# (diagrams already generated – we skip regenerating to save time)

# ── Document Builder ──────────────────────────────────────────────────────────

W3  = [Inches(0.7), Inches(4.1), Inches(0.9)]   # FR table
W3n = [Inches(0.7), Inches(1.3), Inches(3.7)]   # NFR table
W3h = [Inches(1.2), Inches(2.0), Inches(2.0)]   # HW table
W3s = [Inches(1.5), Inches(2.0), Inches(1.2)]   # SW table
W5d = [Inches(1.5), Inches(1.1), Inches(0.9), Inches(1.8), Inches(1.1)]  # DB table
W5a = [Inches(1.5), Inches(1.3), Inches(1.0), Inches(1.1), Inches(0.9)]  # DS summary
W3m = [Inches(1.6), Inches(1.4), Inches(2.7)]   # Module table
W4e = [Inches(0.55), Inches(2.0), Inches(0.65), Inches(2.5)]  # API table
W4f = [Inches(1.6), Inches(0.85), Inches(1.1), Inches(2.2)]  # Functions table
W3l = [Inches(1.2), Inches(1.9), Inches(2.7)]   # Layer/error table
W6t = [Inches(0.55), Inches(0.85), Inches(1.7), Inches(1.35), Inches(1.2), Inches(0.55)]  # test case
W3f = [Inches(2.4), Inches(1.15), Inches(2.15)] # features table
W3o = [Inches(1.8), Inches(2.2), Inches(1.7)]   # optimization table
W3u = [Inches(1.5), Inches(2.5), Inches(1.7)]   # Use case table
W4d = [Inches(1.3), Inches(1.0), Inches(0.85), Inches(1.8), Inches(0.85)] # DB design

CL  = set()          # center all columns
CL2 = {0, 1, 2}     # center first 3

def build():
    doc = Document()
    setup_styles(doc)
    for sec in doc.sections:
        sec.page_width  = Cm(21.0); sec.page_height = Cm(29.7)
        sec.left_margin = sec.right_margin = Cm(2.54)
        sec.top_margin  = sec.bottom_margin = Cm(2.54)

    add_page_number(doc)
    add_header(doc, 'RetainAI – MCA Project Report | Christ University | Sandeep Kumar')

    # ── TITLE PAGE ────────────────────────────────────────────────
    doc.add_paragraph('\n\n\n')
    for line, sz, bold in [
        ('CHRIST UNIVERSITY', 16, True), ('Bengaluru - 560029', 12, False),
        ('\n', 10, False), ('DEPARTMENT OF COMPUTER SCIENCE', 13, True), ('\n', 10, False),
        ('Master of Computer Applications (MCA)', 12, True),
        ('Academic Session: 2026-2027', 11, False), ('\n\n', 10, False),
        ('PROJECT REPORT', 14, True), ('\n', 10, False),
        ('RetainAI: A Predictive Analytics and\nAI-Assisted Customer Churn Mitigation Platform', 18, True),
        ('\n\n\n', 10, False), ('Submitted by:', 11, False), ('Sandeep Kumar', 13, True),
        ('\n', 10, False), ('Under the Guidance of:', 11, False),
        ('Prof. Ramesh Chandra Poonia', 12, True), ('\n\n', 10, False), ('September 2026', 11, False),
    ]:
        pp = doc.add_paragraph(); pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r  = pp.add_run(line); r.font.name = BODY; r.font.size = Pt(sz); r.bold = bold
        if 'RetainAI' in line: r.font.color.rgb = ACCENT
    doc.add_page_break()

    # ── ABSTRACT ──────────────────────────────────────────────────
    doc.add_heading('Abstract', level=1)
    p(doc, 'Customer churn is one of the most significant challenges facing SaaS businesses today. '
           'The inability to proactively identify at-risk customers before they cancel leads to '
           'preventable revenue loss. RetainAI is a real-time, full-stack B2B analytics platform '
           'that predicts customer churn using a scikit-learn Random Forest model, explains every '
           'prediction via SHAP feature attribution, and automatically drafts personalized retention '
           'emails using OpenAI GPT-4o-mini. The platform is built with FastAPI (Python 3.11), '
           'Neon PostgreSQL, React 19, Tailwind CSS, and Recharts. This report presents the '
           'complete design, architecture, data structures, algorithms, implementation, testing, '
           'security analysis, and evaluation of the system.')
    p(doc, 'Customer Churn, Machine Learning, SHAP, FastAPI, Generative AI, SaaS, PostgreSQL, React.',
       bold_run='Keywords: ')
    doc.add_page_break()

    # ── TOC ───────────────────────────────────────────────────────
    doc.add_heading('Table of Contents', level=1)
    for item in ['Chapter 1 - Introduction', 'Chapter 2 - Literature Review',
                 'Chapter 3 - System Requirements', 'Chapter 4 - System Analysis and Design',
                 'Chapter 5 - Data Structures and Algorithms', 'Chapter 6 - System Implementation',
                 'Chapter 7 - Testing', 'Chapter 8 - Results and Discussion',
                 'Chapter 9 - Security and Performance', 'Chapter 10 - Conclusion and Future Scope',
                 'References', 'Appendix']:
        pp = doc.add_paragraph(item)
        pp.paragraph_format.space_after = Pt(3)
        for r in pp.runs: r.font.name = BODY; r.font.size = Pt(11)
    doc.add_page_break()

    # ── CHAPTER 1 ─────────────────────────────────────────────────
    doc.add_heading('Chapter 1 - Introduction', level=1)
    doc.add_heading('1.1 Introduction', level=2)
    p(doc, 'The Software-as-a-Service (SaaS) industry relies on subscription revenue. Customer '
           'retention is therefore the single most important driver of sustainable growth. '
           'Losing a customer eliminates recurring revenue and, at typical SaaS ARR multiples, '
           'significantly reduces company valuation. Most CS teams operate reactively, '
           'identifying churned customers only after they have already cancelled. RetainAI '
           'transforms this reactive model into a proactive one.')
    doc.add_heading('1.2 Background', level=2)
    p(doc, 'Research by Bain and Company shows that a 5% increase in customer retention rates '
           'increases profits by 25% to 95%. Machine learning has proven effective at identifying '
           'churn signals weeks before the customer decides to leave. The challenge is converting '
           'model predictions into immediate, personalized, and scalable interventions.')
    doc.add_heading('1.3 Problem Statement', level=2)
    p(doc, 'Customer success teams face three problems: (1) No unified real-time view of which '
           'customers are at risk and why. (2) Even when scores exist, agents cannot interpret '
           'them to craft effective responses. (3) Manual processes for drafting personalized '
           'outreach are too slow to scale across hundreds of accounts.')
    doc.add_heading('1.4 Objectives', level=2)
    bullets(doc, [
        'Build a real-time ML scoring pipeline that recalculates churn probabilities every 15 seconds.',
        'Provide SHAP-based explanations for every prediction, making the model interpretable.',
        'Automate personalized retention email drafting using OpenAI GPT-4o-mini.',
        'Deliver a professional dark-mode B2B dashboard with live Recharts visualizations.',
        'Implement complete user management, billing plan enforcement, and role-based access.',
    ])
    doc.add_heading('1.5 Scope', level=2)
    p(doc, 'In scope: user authentication, real-time ML scoring, SHAP interpretability, '
           'dashboard visualizations, AI email generation and dispatch, CS notes, customer '
           'ownership, five analytics report types, team management, billing quotas, and alerts. '
           'Out of scope: multi-tenancy, mobile applications, real-time streaming infrastructure.')
    doc.add_page_break()

    # ── CHAPTER 2 ─────────────────────────────────────────────────
    doc.add_heading('Chapter 2 - Literature Review', level=1)
    doc.add_heading('2.1 Churn Prediction Using Machine Learning', level=2)
    p(doc, 'Neslin et al. (2006) conducted a comparative study of classification algorithms for '
           'churn prediction across multiple industries, finding that ensemble methods consistently '
           'outperformed single classifiers in both accuracy and business impact metrics. '
           'Burez and Van den Poel (2009) demonstrated that the length of the observation window '
           'significantly affects model performance - a finding that directly motivated RetainAI\'s '
           'specific look-back windows: 14 days for logins, 7 days for feature usage, and 30 days '
           'for support tickets.')
    doc.add_heading('2.2 Model Interpretability with SHAP', level=2)
    p(doc, 'Lundberg and Lee (2017) introduced SHAP (SHapley Additive exPlanations) as a unified '
           'framework for model interpretation based on Shapley values from cooperative game theory. '
           'Unlike earlier local approximation methods such as LIME (Ribeiro et al., 2016), SHAP '
           'provides consistent, globally coherent explanations. The TreeExplainer variant computes '
           'exact SHAP values in polynomial time for tree-based models, making real-time application '
           'practical. RetainAI uses TreeExplainer to generate per-customer feature attribution '
           'during every 15-second scoring pass.')
    doc.add_heading('2.3 Generative AI for Personalized Communication', level=2)
    p(doc, 'OpenAI\'s GPT series (Brown et al., 2020; OpenAI, 2023) demonstrated that large '
           'language models can generate coherent, contextually appropriate text from structured '
           'prompts. RetainAI exploits this by constructing prompts that include specific SHAP '
           'values in human-readable form, enabling the LLM to draft retention emails that directly '
           'address the exact behavioural drivers of each customer\'s risk score.')
    doc.add_heading('2.4 Existing Systems and Research Gap', level=2)
    p(doc, 'Commercial tools such as Gainsight, ChurnZero, and Totango provide customer health '
           'scores and workflow management. However, they do not provide open SHAP-level feature '
           'attribution, and they do not integrate LLM-based personalization at the feature-driver '
           'level. Academic research has focused almost exclusively on prediction accuracy, rarely '
           'on the full pipeline from data ingestion through interpretable prediction to automated, '
           'personalized intervention. RetainAI fills this gap.')
    doc.add_heading('2.5 Summary', level=2)
    p(doc, 'The literature confirms that ensemble ML methods, real-time feature engineering, '
           'model interpretability, and personalized AI communication are each valuable for churn '
           'prevention. RetainAI is distinguished by integrating all four into a single, '
           'production-quality platform.')
    doc.add_page_break()

    # ── CHAPTER 3 ─────────────────────────────────────────────────
    doc.add_heading('Chapter 3 - System Requirements', level=1)
    doc.add_heading('3.1 Functional Requirements', level=2)
    tbl(doc, ['FR ID', 'Requirement', 'Priority'],
        [['FR-01', 'System shall allow new users to register with email and password', 'High'],
         ['FR-02', 'System shall authenticate users and return a JWT access token (24h)', 'High'],
         ['FR-03', 'System shall maintain user session via JWT in browser localStorage', 'High'],
         ['FR-04', 'System shall recalculate churn risk scores every 15 seconds', 'High'],
         ['FR-05', 'System shall display live KPI tiles: total customers, high-risk count, avg score', 'High'],
         ['FR-06', 'System shall render a customer risk-distribution pie chart from live data', 'High'],
         ['FR-07', 'System shall display SHAP feature importance per customer as a bar chart', 'High'],
         ['FR-08', 'System shall display a 14-day churn risk trend line chart per customer', 'High'],
         ['FR-09', 'System shall allow agents to generate AI-powered retention email drafts', 'High'],
         ['FR-10', 'System shall support tone (professional/friendly/empathetic/urgent) and length (short/medium/long) for email generation', 'Medium'],
         ['FR-11', 'System shall support batch email generation for a risk range (max 7 per batch)', 'Medium'],
         ['FR-12', 'System shall allow agents to send finalized emails to customers via SMTP', 'High'],
         ['FR-13', 'System shall allow agents to send a test email to themselves before dispatch', 'Medium'],
         ['FR-14', 'System shall allow CS agents to add private notes to customer profiles', 'Medium'],
         ['FR-15', 'System shall allow admins to assign a customer owner (CS agent)', 'Medium'],
         ['FR-16', 'System shall enforce AI email quotas based on the active billing plan tier', 'High'],
         ['FR-17', 'System shall support two roles: Admin (full access) and Member (CS agent)', 'High'],
         ['FR-18', 'System shall generate five types of downloadable analytics reports', 'Medium'],
         ['FR-19', 'System shall trigger Slack webhook and email alerts for high-risk customers', 'Medium'],
         ['FR-20', 'System shall allow admins to configure the global high-risk threshold', 'Low'],],
        widths=W3, center_cols={0, 2})

    doc.add_heading('3.2 Non-Functional Requirements', level=2)
    tbl(doc, ['NFR ID', 'Category', 'Requirement'],
        [['NFR-01', 'Performance',    'Core API endpoints must respond within 100ms at P95 under normal load'],
         ['NFR-02', 'Performance',    'ML scoring pipeline must complete within 5 seconds for 500 customers'],
         ['NFR-03', 'Scalability',    'API layer must be horizontally scalable behind a load balancer'],
         ['NFR-04', 'Security',       'Passwords must be hashed with bcrypt (cost factor 12)'],
         ['NFR-05', 'Security',       'All API endpoints except /auth/* must require a valid JWT token'],
         ['NFR-06', 'Security',       'Admin-only routes must additionally verify the user role equals "admin"'],
         ['NFR-07', 'Reliability',    'DB connections must use pool_pre_ping=True to handle Neon cold starts'],
         ['NFR-08', 'Reliability',    'ML pipeline failures must be caught and logged without crashing the scheduler'],
         ['NFR-09', 'Usability',      'Dashboard must be fully responsive for screen widths >= 1280px'],
         ['NFR-10', 'Maintainability','Business logic must be separated from FastAPI route definitions'],
         ['NFR-11', 'Data Integrity', 'All foreign key relationships must be enforced at the database level'],
         ['NFR-12', 'Availability',   'System must reconnect to Neon PostgreSQL automatically after idle timeouts'],],
        widths=W3n, center_cols={0, 1})

    doc.add_heading('3.3 Hardware Requirements', level=2)
    tbl(doc, ['Component', 'Minimum', 'Recommended'],
        [['CPU',     '2-core, 2.0 GHz',    '4-core, 3.0 GHz or higher'],
         ['RAM',     '4 GB',               '8 GB or more'],
         ['Storage', '20 GB SSD',          '50 GB SSD'],
         ['Network', '10 Mbps broadband',  '100 Mbps broadband'],
         ['GPU',     'Not required',        'Not required'],],
        widths=W3h)

    doc.add_heading('3.4 Software Requirements', level=2)
    tbl(doc, ['Category', 'Technology', 'Version'],
        [['Backend Language',  'Python',              '3.11 or higher'],
         ['Backend Framework', 'FastAPI',             '0.110 or higher'],
         ['Database',          'PostgreSQL (Neon)',   '15 or higher'],
         ['ORM',               'SQLAlchemy',          '2.0 or higher'],
         ['ML Library',        'scikit-learn',        '1.4 or higher'],
         ['Explainability',    'SHAP',                '0.45 or higher'],
         ['Frontend',          'React + Vite',        '19 + 5 or higher'],
         ['UI Framework',      'Tailwind CSS',        '3.4 or higher'],
         ['Charts',            'Recharts',            '2.9 or higher'],
         ['Auth Library',      'JWT (python-jose)',   '3.3 or higher'],
         ['Password Hashing',  'passlib[bcrypt]',     '1.7 or higher'],
         ['Scheduler',         'APScheduler',         '3.10 or higher'],
         ['AI Generation',     'OpenAI GPT-4o-mini',  'v1 API'],
         ['Email Relay',       'Resend / SMTP',       'N/A'],],
        widths=W3s)

    doc.add_heading('3.5 User Requirements', level=2)
    p(doc, 'Two user roles are supported:')
    bullets(doc, [
        'Admin: Full system access including team management, billing plan changes, alert configuration, customer owner assignment, and system settings.',
        'Member (CS Agent): Can view all customers, generate and send emails, add CS notes, generate reports, and view the full dashboard.',
    ])

    doc.add_heading('3.6 System Constraints', level=2)
    bullets(doc, [
        'OpenAI API Key: AI email generation requires a valid, funded OpenAI API key. Without it, the system uses a template-based fallback email automatically.',
        'SMTP Credentials: Email dispatch requires valid SMTP credentials (Resend). Without them, email drafts can still be saved and reviewed but not sent.',
        'Neon Free Tier: The cloud database may cold-start after idle periods, causing a 2-5 second initial connection delay on the first request.',
        'AI Email Quota: The Starter billing plan limits AI-generated emails to 50 per 30-day billing cycle.',
        'Batch Size Cap: Batch email generation is capped at 7 customers per run to enforce mandatory human review before sending.',
    ])
    doc.add_page_break()

    # ── CHAPTER 4 ─────────────────────────────────────────────────
    doc.add_heading('Chapter 4 - System Analysis and Design', level=1)
    doc.add_heading('4.1 Overall System Architecture', level=2)
    p(doc, 'RetainAI follows a two-tier client-server architecture. The React SPA (Single Page '
           'Application) communicates with the FastAPI backend exclusively via RESTful HTTP/JSON. '
           'The backend manages all business logic, ML scheduling, database access, caching, '
           'and third-party API integrations. No server-side rendering is used.')
    fig(doc, dpath('diag_architecture.png'), 'Figure 4.1: RetainAI System Architecture Diagram', Inches(6.0))
    p(doc, 'The system has four logical layers: (1) Presentation Layer - React 19 SPA with '
           'Tailwind CSS and Recharts. (2) Application Layer - FastAPI with JWT auth, APScheduler, '
           'and business logic. (3) Data Layer - Neon PostgreSQL with SQLAlchemy ORM and in-memory '
           'TTL cache. (4) External Services - OpenAI GPT-4o-mini and Resend/SMTP.')

    doc.add_heading('4.2 Data Flow Diagrams', level=2)
    fig(doc, dpath('diag_dfd0.png'), 'Figure 4.2: Context Level DFD (Level 0)', Inches(5.8))
    p(doc, 'The Level 0 DFD represents the entire system as a single process (Process 0) with '
           'four external entities: CS Agent/Admin (interacts via dashboard), OpenAI API '
           '(provides generated email content), Resend/SMTP (dispatches emails to customers), '
           'and the Customer (receives the retention email).')

    fig(doc, dpath('diag_dfd1.png'), 'Figure 4.3: Level 1 DFD - RetainAI Subsystems', Inches(6.0))
    p(doc, 'The Level 1 DFD decomposes the system into six processes: P1 (User Authentication), '
           'P2 (ML Scoring Pipeline), P3 (AI Email Generation), P4 (Dashboard and Reporting), '
           'P5 (Email Draft Management), and P6 (Alert Dispatch). All processes share a central '
           'data store D1 (PostgreSQL database).')

    doc.add_heading('4.3 Use Case Diagram', level=2)
    fig(doc, dpath('diag_usecase.png'), 'Figure 4.4: Use Case Diagram - RetainAI', Inches(6.0))
    p(doc, 'Three actors are identified: CS Agent (customer-facing operations), Admin (system '
           'configuration and team management), and System (automated background tasks). '
           'Twenty use cases are distributed across these three actors.')
    tbl(doc, ['Actor', 'Use Case', 'Description'],
        [['CS Agent', 'UC-01: Login / Logout',          'Authenticate using JWT-backed credentials'],
         ['CS Agent', 'UC-02: View Dashboard',           'View KPI tiles, charts, and high-risk customer table'],
         ['CS Agent', 'UC-03: View Customer Detail',     'Open individual profile with SHAP chart and trend'],
         ['CS Agent', 'UC-04: Generate Retention Email', 'Trigger AI email draft for a specific customer'],
         ['CS Agent', 'UC-05: Edit and Send Email',      'Review, edit draft, and dispatch via SMTP'],
         ['CS Agent', 'UC-06: Send Test Email',          'Send test copy to own inbox before dispatch'],
         ['CS Agent', 'UC-07: Add CS Notes',             'Log intervention notes on a customer profile'],
         ['CS Agent', 'UC-08: Generate Reports',         'Create and download analytics reports as CSV'],
         ['Admin',    'UC-09: Manage Team Roles',        'View team members and change user roles'],
         ['Admin',    'UC-10: Assign Customer Owner',    'Assign a CS agent to a specific customer account'],
         ['Admin',    'UC-11: Send High-Risk Alerts',    'Trigger Slack and email alerts for at-risk customers'],
         ['Admin',    'UC-12: Configure App Settings',   'Adjust global high-risk threshold and other settings'],
         ['Admin',    'UC-13: Manage Billing Plan',      'Change subscription plan and monitor AI email quota'],
         ['System',   'UC-14: Score All Customers',      'Run ML pipeline every 15 seconds automatically'],
         ['System',   'UC-15: Update Predictions DB',    'Bulk upsert all scoring results to PostgreSQL'],],
        widths=[Inches(1.0), Inches(1.8), Inches(2.9)], center_cols={0})

    doc.add_heading('4.4 Authentication Flow (Sequence/Activity Diagram)', level=2)
    fig(doc, dpath('diag_auth.png'), 'Figure 4.5: JWT Authentication and Authorization Flow', Inches(5.0))
    p(doc, 'The flow validates user existence, verifies bcrypt password hash, issues a signed '
           'JWT (HS256, 24-hour expiry), and returns it to the client. On every subsequent '
           'request, FastAPI\'s Depends(get_current_user) decodes and validates the token '
           'in under 1ms without a database round trip.')

    doc.add_heading('4.5 Component Diagram', level=2)
    fig(doc, dpath('diag_component.png'), 'Figure 4.8: Component Diagram - RetainAI', Inches(6.0))
    p(doc, 'The component diagram shows the dependencies between all major software components '
           'across the three layers. Frontend page components depend on api.js, which calls '
           'FastAPI endpoints. Endpoints delegate to pipeline.py for ML operations and to '
           'database.py for ORM-based persistence. External services are invoked only from the '
           'application layer.')

    doc.add_heading('4.6 Deployment Diagram', level=2)
    fig(doc, dpath('diag_deployment.png'), 'Figure 4.9: Deployment Diagram - RetainAI', Inches(5.8))
    p(doc, 'In the current deployment, the Vite dev server (port 5173) and FastAPI server '
           '(port 8000) run on the developer machine. Neon PostgreSQL is cloud-hosted with '
           'TLS-encrypted connections. OpenAI and Resend are accessed as external SaaS APIs '
           'over HTTPS.')

    doc.add_heading('4.7 Database Design (ER Diagram)', level=2)
    fig(doc, dpath('diag_er.png'), 'Figure 4.7: Entity-Relationship (ER) Diagram', Inches(6.2))
    p(doc, 'The database has 12 tables. ml_customers is the central entity (UUID primary key) '
           'referenced by all activity and analytical tables via indexed foreign keys. '
           'customer_predictions stores the ML output per customer. email_drafts stores '
           'AI-generated and manually created drafts. The users table is standalone for '
           'authentication.')
    tbl(doc, ['Table Name', 'Primary Key', 'Foreign Key', 'Key Columns', 'Purpose'],
        [['ml_customers',         'customer_id UUID', 'None',           'name, email, signup_date',            'Customer master record'],
         ['customer_predictions', 'id INTEGER',       'customer_id',    'churn_probability, shap_values, top_driver', 'ML scoring output'],
         ['login_events',         'id INTEGER',       'customer_id',    'login_at, device, ip_country',         'Login activity log'],
         ['usage_events',         'id INTEGER',       'customer_id',    'occurred_at, duration_secs, feature',   'Feature usage log'],
         ['support_tickets',      'id INTEGER',       'customer_id',    'created_at, subject, status',           'Support history'],
         ['payment_events',       'id INTEGER',       'customer_id',    'occurred_at, amount_usd, status',       'Payment history'],
         ['email_drafts',         'id INTEGER',       'customer_id',    'subject, body, tone, length, status',   'Email drafts store'],
         ['customer_notes',       'id INTEGER',       'customer_id',    'text, author, created_at',              'CS agent notes'],
         ['customer_owners',      'id INTEGER',       'customer_id',    'owner_email, assigned_at',              'Agent assignment'],
         ['users',                'email VARCHAR',    'None',           'hashed_password, role, full_name',      'Authentication'],
         ['reports',              'id INTEGER',       'None',           'report_type, result_json, created_by',  'Report snapshots'],
         ['app_settings',         'key VARCHAR',      'None',           'value, updated_by, updated_at',         'Global config store'],],
        widths=W4d, center_cols={0, 1, 2})
    doc.add_page_break()

    # ── CHAPTER 5 ─────────────────────────────────────────────────
    doc.add_heading('Chapter 5 - Data Structures and Algorithms', level=1)
    doc.add_heading('5.1 Data Structures Used in RetainAI', level=2)
    p(doc, 'The following analysis covers only the data structures actually used in the '
           'RetainAI codebase. Data structures with no direct relevance (linked lists, '
           'binary search trees, graphs) are excluded.')
    tbl(doc, ['Data Structure', 'Purpose', 'Project Usage', 'Time Complexity', 'Space Complexity'],
        [['pandas DataFrame (2D Array)',    'Vectorized batch operations',  'Feature matrix: all 500 customers x 4 features per scoring pass', 'O(N) build, O(1) col access', 'O(N x F)'],
         ['Python Dictionary (HashMap)',    'O(1) key-value lookup',        'TTL cache, SHAP JSON per customer, API response dicts',           'O(1) avg get/set',            'O(K) keys'],
         ['Python List (Dynamic Array)',    'Ordered mutable sequence',     'Customer lists, event lists, bulk upsert row payloads',            'O(1) append, O(N) search',    'O(N)'],
         ['Python Set (Hash Set)',          'O(1) membership test',         'Already-drafted customer IDs in batch email deduplication',       'O(1) lookup, O(D) build',     'O(D)'],
         ['threading.Lock (Mutex)',         'Thread-safe critical section', 'Prevents overlapping ML scoring pipeline runs in APScheduler',    'O(1) acquire/release',        'O(1)'],],
        widths=W5a, center_cols={0})

    doc.add_heading('5.1.1 pandas DataFrame (2D Array)', level=3)
    p(doc, 'A 2-dimensional labeled data structure backed by NumPy arrays. Provides vectorized '
           'column operations via optimized C routines, far faster than Python-level loops.')
    p(doc, 'Why used: The scoring pipeline must compute 4 features for 500+ customers '
           'simultaneously. pandas groupby aggregation replaces 500 individual DB queries '
           'with one vectorized computation pass over a pre-loaded event DataFrame.')
    code(doc, '''\
# pipeline.py - vectorized feature engineering
df["Account_Age_Days"]    = (as_of.date() - df["signup_date"]).apply(lambda d: d.days)
df["Login_Frequency"]     = df["customer_id"].map(login_counts).fillna(0).astype(int)
df["Daily_Usage_Mins"]    = df["customer_id"].map(usage_avg).fillna(0.0)
df["Last_Support_Ticket"] = df["customer_id"].map(latest_ticket).apply(ticket_urgency_score)
''', 'Listing 5.1: Vectorized feature engineering on a pandas DataFrame')
    tbl(doc, ['Operation', 'pandas Method', 'Time Complexity'],
        [['Build DataFrame from DB result', 'pd.read_sql()', 'O(N)'],
         ['Group events by customer', 'groupby().size()', 'O(E log N)'],
         ['Map customer_id to values', 'Series.map()', 'O(N)'],
         ['Fill missing customers (no events)', 'fillna(0)', 'O(N)'],
         ['Access entire column', 'df["col_name"]', 'O(1) - pointer to NumPy array'],],
        widths=[Inches(1.8), Inches(2.2), Inches(1.8)], center_cols=set())
    p(doc, 'Example from project: For 500 customers with 2,000 login events, pandas computes '
           'Login_Frequency for all 500 simultaneously in approximately 3ms versus ~1,500ms '
           'for 500 individual SQL COUNT queries.')

    doc.add_heading('5.1.2 Python Dictionary (HashMap)', level=3)
    p(doc, 'A hash table mapping keys to values. CPython uses open addressing with a compact '
           'array, providing O(1) average-case get and set. Three uses in RetainAI:')
    bullets(doc, [
        'TTL Cache: Maps cache_key strings (e.g., "customer_detail:abc123") to (data, expiry_timestamp) tuples.',
        'SHAP Values: Each customer\'s prediction stores SHAP as {"Account_Age_Days": -0.002, "Login_Frequency": 0.063, ...} JSON.',
        'API Responses: All endpoints serialize ORM objects to Python dicts before returning JSON.',
    ])
    code(doc, '''\
# main.py - TTL cache using Python dictionary
_cache: dict = {}

def get_cached(key: str):
    if key in _cache:
        data, expiry = _cache[key]
        if time.time() < expiry:
            return data         # Cache HIT: O(1) hash lookup
        del _cache[key]         # Expired: evict entry
    return None                 # Cache MISS: caller queries database

def set_cached(key: str, data, ttl_seconds: int = 15):
    _cache[key] = (data, time.time() + ttl_seconds)   # O(1) insert
''', 'Listing 5.2: TTL cache implemented with Python Dictionary')
    p(doc, 'Space: O(K) where K = number of unique cache keys (~20 in practice). '
           'Time: O(1) for both get and set (hash table).')

    doc.add_heading('5.1.3 Python List (Dynamic Array)', level=3)
    p(doc, 'A dynamic array that automatically resizes. Uses ~1.125x over-allocation so '
           'amortized append is O(1). Used for: customer rosters, event collections, '
           'API response arrays, and bulk upsert row payloads.')
    code(doc, '''\
# main.py - list comprehension builds the bulk upsert payload
rows = [
    {"customer_id": cid, "churn_probability": float(prob),
     "shap_values": json.dumps(shap_dict), "scored_at": scored_at}
    for cid, prob, shap_dict
    in zip(df["customer_id"], probabilities, shap_dicts)
]
conn.execute(upsert_stmt.values(rows))   # single DB round trip for all N rows
''', 'Listing 5.3: List comprehension building bulk upsert payload')

    doc.add_heading('5.1.4 Python Set (Hash Set)', level=3)
    p(doc, 'An unordered collection of unique elements backed by a hash table. '
           'Membership testing is O(1) average. Used in batch email generation to '
           'deduplicate customers who already have unsent drafts:')
    code(doc, '''\
# main.py - generate_email_batch endpoint
already_drafted = {        # Set comprehension: O(D) to build
    row.customer_id
    for row in db.query(EmailDraft.customer_id)
        .filter(EmailDraft.customer_id.in_(candidate_ids),
                EmailDraft.status == "draft")
        .all()
}
# Now each check is O(1) instead of O(D) list scan
candidates = in_range[~in_range["customer_id"].isin(already_drafted)].head(7)
''', 'Listing 5.4: Set used for O(1) duplicate detection in batch email generation')

    doc.add_heading('5.1.5 threading.Lock (Mutex)', level=3)
    p(doc, 'A mutual exclusion primitive ensuring only one thread executes a critical section '
           'at a time. Used to prevent overlapping ML scoring passes when the pipeline takes '
           'longer than 15 seconds (e.g., during Neon DB cold-start).')
    code(doc, '''\
# pipeline.py
_scoring_lock = threading.Lock()

def run_scoring_pass():
    if not _scoring_lock.acquire(blocking=False):  # Non-blocking try
        logger.info("[pipeline] skipped - previous pass still running")
        return -1     # Skip this tick instead of overlapping
    try:
        return _do_scoring_pass()
    finally:
        _scoring_lock.release()   # Always released, even on exception
''', 'Listing 5.5: threading.Lock preventing concurrent scoring passes')

    doc.add_heading('5.2 Algorithms', level=2)
    doc.add_heading('5.2.1 Vectorized Feature Engineering', level=3)
    p(doc, 'Purpose: Transform raw event records into model-ready feature vectors for all '
           'customers in a single vectorized batch rather than per-customer loops.')
    code(doc, '''\
ALGORITHM: Batch_Feature_Engineering(roster, logins, usage, tickets, as_of)
INPUT:  roster   = DataFrame[N x 4]   customers with signup dates
        logins   = DataFrame[E1 x 2]  login events within 14-day window
        usage    = DataFrame[E2 x 3]  usage events within 7-day window
        tickets  = DataFrame[E3 x 3]  support tickets within 30-day window
        as_of    = datetime reference timestamp

OUTPUT: feature_df = DataFrame[N x 4] (Account_Age, Login_Freq, Daily_Usage, Support)

BEGIN
  df["Account_Age_Days"]    <- (as_of.date - df["signup_date"]).days     // O(N)
  login_counts              <- logins.groupby("customer_id").size()       // O(E1)
  df["Login_Frequency"]     <- df["customer_id"].map(login_counts).fillna(0)
  usage_avg                 <- usage.groupby("customer_id")["duration_secs"].mean() / 60  // O(E2)
  df["Daily_Usage_Mins"]    <- df["customer_id"].map(usage_avg).fillna(0.0)
  latest_ticket             <- tickets.drop_duplicates("customer_id", keep="first")
  df["Last_Support_Ticket"] <- df["customer_id"].map(latest_ticket).apply(urgency_score)
  RETURN df
END

Time Complexity:  O(N + E1 + E2 + E3) where E = total events in all windows
Space Complexity: O(N + E)
''', 'Pseudocode 5.1: Vectorized Feature Engineering Algorithm')

    doc.add_heading('5.2.2 SHAP TreeExplainer Attribution', level=3)
    p(doc, 'Purpose: Fairly distribute each prediction\'s output among input features using '
           'Shapley values from cooperative game theory.')
    code(doc, '''\
Customer: Alyssa Clark  |  Churn Score: 0.86
SHAP Attribution:
  Account_Age_Days      : -0.0017  (281 days old -> slightly lowers risk)
  Login_Frequency       : +0.0633  (only 2 logins in 14 days -> raises risk)
  Daily_Usage_Mins      : +0.3252  (11.7 min avg -> MAJOR risk driver)
  Last_Support_Ticket   : -0.0241  (ticket present -> slightly lowers risk)
  Base value E[f(X)]    :  ~0.50
  Sum of SHAP values    :  +0.36
  Final churn score     :   0.86  (verified)

Time Complexity:  O(N x T x D) where T=trees (100), D=features (4)
Space Complexity: O(N x D) for the SHAP value matrix
''', 'Example 5.1: Real SHAP attribution breakdown for a RetainAI customer')

    doc.add_heading('5.2.3 JWT Token Generation and Validation', level=3)
    p(doc, 'Purpose: Stateless authentication via cryptographically signed tokens, '
           'eliminating the need for server-side session storage.')
    code(doc, '''\
ALGORITHM: JWT_Generate(email, secret_key, expiry_hours=24)
BEGIN
  header    <- base64url({"alg": "HS256", "typ": "JWT"})
  payload   <- base64url({"sub": email, "exp": now + expiry_hours})
  signature <- HMAC_SHA256(header + "." + payload, secret_key)
  RETURN header + "." + payload + "." + base64url(signature)
END

ALGORITHM: JWT_Validate(token, secret_key)
BEGIN
  header, payload, sig <- token.split(".")
  expected             <- HMAC_SHA256(header + "." + payload, secret_key)
  IF expected != sig:       RAISE HTTP 401 Invalid Token
  IF payload["exp"] < now:  RAISE HTTP 401 Token Expired
  RETURN payload["sub"]   // the user email
END

Time Complexity:  O(|token|) for HMAC - effectively O(1)
Space Complexity: O(1) - no server-side session storage needed
''', 'Pseudocode 5.2: JWT Token Generation and Validation')

    doc.add_heading('5.2.4 Risk Tier Classification', level=3)
    code(doc, '''\
ALGORITHM: classify_risk(score, high_threshold=0.70, low_threshold=0.30)
BEGIN
  IF score >= high_threshold:     RETURN "HIGH RISK"    // Red indicator
  ELSE IF score >= low_threshold: RETURN "MEDIUM RISK"  // Amber indicator
  ELSE:                           RETURN "LOW RISK"     // Green indicator
END

Example:  score=0.86 -> HIGH RISK
          score=0.45 -> MEDIUM RISK
          score=0.18 -> LOW RISK

Time Complexity:  O(1) per customer, O(N) for full population
Space Complexity: O(1)
''', 'Pseudocode 5.3: Risk Tier Classification Algorithm')

    doc.add_heading('5.2.5 TTL Cache Lookup', level=3)
    code(doc, '''\
ALGORITHM: Cache_Get(key)
BEGIN
  IF key IN _cache:
    (data, expiry) <- _cache[key]
    IF current_time < expiry:
      RETURN data           // HIT: O(1) hash lookup
    ELSE:
      DELETE _cache[key]    // Evict stale entry
  RETURN None               // MISS: caller must query the database
END

ALGORITHM: Cache_Set(key, data, ttl_seconds)
BEGIN
  _cache[key] <- (data, current_time + ttl_seconds)   // O(1) insert
END

Time Complexity:  O(1) average for both get and set
Space Complexity: O(K) where K = active cache keys (~20)
''', 'Pseudocode 5.4: TTL Cache Lookup Algorithm')

    fig(doc, dpath('diag_ml_flowchart.png'), 'Figure 5.1: ML Scoring Pipeline Flowchart', Inches(3.5))
    doc.add_page_break()

    # ── CHAPTER 6 ─────────────────────────────────────────────────
    doc.add_heading('Chapter 6 - System Implementation', level=1)
    doc.add_heading('6.1 Project Modules', level=2)
    tbl(doc, ['Module / File', 'Location', 'Responsibility'],
        [['main.py',            'backend/',            '40+ REST endpoints, startup hook, APScheduler, cache, SMTP, alerts'],
         ['pipeline.py',        'backend/',            'Feature engineering, sklearn inference, SHAP, bulk DB upsert'],
         ['database.py',        'backend/',            'SQLAlchemy engine, 12 ORM models, init_all_tables(), plan seeding'],
         ['features.py',        'backend/',            'FEATURE_COLS constant, look-back window constants, ticket_urgency_score()'],
         ['realtime.py',        'backend/',            'Simulates live events; writes login/usage/ticket rows to DB continuously'],
         ['App.jsx',            'frontend/src/',       'Root component: routing, authentication state, page switching'],
         ['Dashboard.jsx',      'frontend/src/pages/', 'KPI tiles, PieChart, SHAP BarChart, ComposedChart, high-risk table'],
         ['CustomerDetail.jsx', 'frontend/src/pages/', 'Customer profile, SHAP bar chart, 14-day trend, history, notes'],
         ['EmailDrafts.jsx',    'frontend/src/pages/', 'AI email composer, draft list, batch generation panel'],
         ['api.js',             'frontend/src/',       'All Axios API call functions with automatic JWT header injection'],
         ['risk.js',            'frontend/src/',       'getRiskThresholds(), driverLabel() formatter, formatPercent()'],
         ['CustomerTable.jsx',  'frontend/src/components/', 'Tailwind-styled sortable customer table with risk indicators'],
         ['RiskMeter.jsx',      'frontend/src/components/', 'SVG-based semi-circular risk gauge component'],
         ['RiskBadge.jsx',      'frontend/src/components/', 'Colour-coded risk tier badge (High / Medium / Low)'],],
        widths=W3m, center_cols={0, 1})

    doc.add_heading('6.2 Frontend Implementation', level=2)
    p(doc, 'The frontend is a React 19 Single-Page Application built with Vite. All API calls '
           'are centralized in src/api.js using an axios instance that automatically injects '
           'the JWT Authorization header on every request. Key design patterns:')
    bullets(doc, [
        'Local State only: useState/useEffect per page component. No global state manager (Redux/Zustand) is needed due to simple data flow.',
        'Parallel Loading: CustomerDetail loads 4 API endpoints simultaneously via Promise.all(), reducing total load time to the maximum individual response time rather than their sum.',
        'Error Isolation: Each page independently handles its own errors. A failure on one page does not affect navigation to others.',
        'Tailwind CSS: All components use Tailwind utility classes. No inline styles remain in the production UI components.',
    ])
    code(doc, '''\
// api.js - Axios client with automatic JWT injection
const client = axios.create({ baseURL: "http://localhost:8000" });
client.interceptors.request.use((config) => {
    const token = localStorage.getItem("retainai_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
});

// CustomerDetail.jsx - parallel data loading
useEffect(() => {
    Promise.all([
        fetchCustomerDetail(customerId),   // GET /customers/{id}
        fetchCustomerHistory(customerId),  // GET /customer_history/{id}
        fetchRiskTrend(customerId, 14),    // GET /customers/{id}/risk_trend
        fetchCustomerNotes(customerId),    // GET /customers/{id}/notes
    ])
    .then(([detail, history, trend, notes]) => {
        setDetail(detail);
        setHistory(history);
        setTrend(trend.trend);
        setNotes(notes);
    })
    .catch(() => setError("Could not load this customer's data."));
}, [customerId]);
''', 'Listing 6.1: Axios API client and parallel data loading in CustomerDetail.jsx')

    doc.add_heading('6.3 Backend Implementation', level=2)
    p(doc, 'The backend is a FastAPI application. FastAPI uses Python type annotations and '
           'Pydantic models to automatically validate request bodies and serialize responses '
           'to JSON. The Depends() dependency injection system is used for authentication '
           'and DB session management throughout.')
    code(doc, '''\
# main.py - authenticated endpoint with caching and live DB fields
@app.get("/customers/{customer_id}")
def get_customer_detail(
    customer_id: str,
    current_user: str = Depends(get_current_user)   # JWT decoded here
):
    cached = cache.get_cached(f"customer_detail:{customer_id}")
    if cached:
        return cached    # O(1) cache hit - no DB query needed

    row = pd.read_sql(DETAIL_QUERY, engine, params={"cid": customer_id})
    if row.empty:
        raise HTTPException(status_code=404, detail="Customer not found")

    db = db_session()
    try:
        login_count  = db.query(LoginEvent).filter(...).count()
        usage_events = db.query(UsageEvent).filter(...).all()
        last_ticket  = db.query(SupportTicket).filter(...).first()
    finally:
        db.close()

    result = {
        "customer_id": row["customer_id"].iloc[0],
        "churn_risk_score": row["churn_probability"].iloc[0],
        "login_frequency_raw": login_count,
        "daily_usage_mins": round(avg_usage, 1),
        "last_support_ticket_raw": last_ticket.subject if last_ticket else None,
        "shap_explanations": json.loads(row["shap_values"].iloc[0] or "{}"),
    }
    cache.set_cached(f"customer_detail:{customer_id}", result, 15)
    return result
''', 'Listing 6.2: FastAPI endpoint with JWT auth, cache, and live activity fields')

    doc.add_heading('6.4 Database Implementation', level=2)
    p(doc, 'SQLAlchemy 2.0 is used as the ORM. The engine is configured with connection '
           'pooling and pool_pre_ping=True to handle Neon database cold-start reconnections. '
           'All 12 tables are defined as Python classes inheriting from a declarative Base. '
           'Foreign key constraints are enforced at the database level.')
    code(doc, '''\
# database.py - EmailDraft ORM model
class EmailDraft(Base):
    __tablename__ = "email_drafts"
    id          = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String,  ForeignKey("ml_customers.customer_id"), nullable=False)
    subject     = Column(String,  nullable=False, default="")
    body        = Column(Text,    nullable=False, default="")
    tone        = Column(String,  nullable=False, default="professional")
    length      = Column(String,  nullable=False, default="medium")
    status      = Column(String,  nullable=False, default="draft")   # draft | sent
    created_by  = Column(String,  nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    sent_at     = Column(DateTime, nullable=True)
''', 'Listing 6.3: EmailDraft SQLAlchemy ORM model')

    doc.add_heading('6.5 API Endpoints', level=2)
    tbl(doc, ['Method', 'Endpoint', 'Auth', 'Description'],
        [['POST', '/auth/signup',                   'None',  'Register new user (bcrypt hash, default Member role)'],
         ['POST', '/auth/login',                    'None',  'Return JWT token on valid email and password'],
         ['GET',  '/me',                            'JWT',   'Return current user profile and preferences'],
         ['GET',  '/customers',                     'JWT',   'List all or high-risk-only customers with owners'],
         ['GET',  '/customers/summary',             'JWT',   'KPI summary: counts, avg score, risk distribution'],
         ['GET',  '/customers/{id}',                'JWT',   'Full customer profile + SHAP + live activity KPIs'],
         ['GET',  '/customers/{id}/risk_trend',     'JWT',   '14-day historical churn risk scores array'],
         ['GET',  '/customers/export',              'JWT',   'Export customers as CSV download (streaming)'],
         ['GET',  '/customer_history/{id}',         'JWT',   'Logins, usage events, tickets, payment history'],
         ['POST', '/customers/{id}/notes',          'JWT',   'Add a CS note to a customer profile'],
         ['POST', '/emails/generate',               'JWT',   'Generate AI email via OpenAI (or fallback template)'],
         ['POST', '/emails/generate_batch',         'JWT',   'Batch generate drafts by risk range (cap: 7)'],
         ['GET',  '/emails/drafts',                 'JWT',   'List saved drafts, optionally filtered by customer'],
         ['POST', '/emails/drafts',                 'JWT',   'Save a new email draft manually'],
         ['PUT',  '/emails/drafts/{id}',            'JWT',   'Update draft subject, body, tone, or length'],
         ['DELETE','/emails/drafts/{id}',           'JWT',   'Delete a draft from the database'],
         ['POST', '/emails/drafts/{id}/send_test',  'JWT',   'Send test copy to the logged-in user email'],
         ['POST', '/emails/drafts/{id}/send',       'JWT',   'Send draft to customer via SMTP; mark as sent'],
         ['POST', '/alerts/high_risk/run',          'Admin', 'Trigger Slack and email alert for high-risk customers'],
         ['GET',  '/reports',                       'JWT',   'List all previously generated reports'],
         ['POST', '/reports/generate',              'JWT',   'Generate and save an analytics report snapshot'],
         ['GET',  '/reports/{id}/export',           'JWT',   'Download a report as CSV file'],
         ['GET',  '/billing/subscription',          'JWT',   'Get current plan, quota, and usage stats'],
         ['PUT',  '/billing/subscription',          'Admin', 'Change the active billing plan'],
         ['PUT',  '/admin/users/{email}/role',      'Admin', 'Change a user role to Admin or Member'],
         ['GET',  '/admin/users',                   'Admin', 'List all registered users'],
         ['GET',  '/integrations/status',           'JWT',   'Check status of OpenAI and SMTP integrations'],
         ['POST', '/admin/rescore',                 'Admin', 'Manually trigger the ML scoring pipeline'],],
        widths=W4e, center_cols={0, 2})

    doc.add_heading('6.6 Authentication and Authorization', level=2)
    fig(doc, dpath('diag_auth.png'), 'Figure 6.1: JWT Authentication Flow (detail)', Inches(4.8))
    code(doc, '''\
# main.py - JWT auth dependency
def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# main.py - Role-based admin dependency
def get_current_admin(current_user: str = Depends(get_current_user)) -> str:
    db = db_session()
    try:
        user = db.query(User).filter(User.email == current_user).first()
        if not user or user.role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return current_user
    finally:
        db.close()
''', 'Listing 6.4: JWT authentication and admin role authorization dependencies')

    doc.add_heading('6.7 Important Classes and Functions', level=2)
    tbl(doc, ['Name', 'Type', 'Module', 'Description'],
        [['run_scoring_pass()',       'Function', 'pipeline.py', 'Thread-safe entry point for the ML pipeline; returns rows scored or -1 if skipped'],
         ['_build_feature_frame()',  'Function', 'pipeline.py', 'Vectorized feature engineering for all N customers in one pass'],
         ['get_customer_trend()',    'Function', 'pipeline.py', 'Computes day-by-day historical risk scores for one customer over N days'],
         ['_generate_email_draft()', 'Function', 'main.py',    'Constructs OpenAI prompt from SHAP + profile; parses SUBJECT line and body'],
         ['_consume_ai_email_quota()','Function','main.py',    'Checks and deducts from billing plan quota before any OpenAI API call'],
         ['_send_smtp_email()',      'Function', 'main.py',    'Sends emails via smtplib.SMTP with STARTTLS; returns (ok, detail) tuple'],
         ['ticket_urgency_score()',  'Function', 'features.py','Converts ticket subject to 0-10 scalar; handles None and NaN safely'],
         ['CustomerPrediction',      'ORM Class','database.py','Stores churn_probability, shap_values JSON, top_driver, scored_at per customer'],
         ['EmailDraft',              'ORM Class','database.py','Stores subject, body, tone, length, status, sent_at per email draft'],
         ['SimpleTTLCache',          'Class',    'main.py',    'In-memory dictionary cache with per-key TTL expiry for hot endpoints'],],
        widths=[Inches(1.6), Inches(0.85), Inches(1.0), Inches(2.35)], center_cols={0, 1, 2})

    doc.add_heading('6.8 Data Processing', level=2)
    code(doc, '''\
# features.py - ticket_urgency_score (with NaN/None safety)
def ticket_urgency_score(text):
    """Convert a raw support-ticket subject to a 0-10 urgency scalar."""
    if text is None:
        return 0.0
    if isinstance(text, float) and math.isnan(text):
        return 0.0
    try:
        return max(0, min(10, int(float(text))))   # handles "7", "7.5", etc.
    except (ValueError, TypeError):
        return 5.0   # mid-urgency default for unrecognized text subjects
''', 'Listing 6.5: ticket_urgency_score() with complete edge-case handling')

    doc.add_heading('6.9 Error Handling', level=2)
    tbl(doc, ['Layer', 'Mechanism', 'Behavior on Failure'],
        [['FastAPI API layer',    'HTTPException with specific status codes',    '401 auth, 402 quota exceeded, 403 role, 404 not found, 502 SMTP/AI failure'],
         ['ML Pipeline',          'try/except around _do_scoring_pass()',         'Logs full traceback; scheduler continues ticking; returns 0 rows scored'],
         ['Frontend pages',        'Promise.catch() per page component',           'Shows user-readable error string; other pages and navigation unaffected'],
         ['DB Connections',        'pool_pre_ping=True + SQLAlchemy retry logic',  'Automatically tests stale connections; reconnects to Neon after cold start'],
         ['OpenAI API calls',      'try/except around chat.completions.create()',  'Falls back to template email; sets source = "fallback_template"'],
         ['SMTP email dispatch',   '_send_smtp_email() returns (ok, detail) tuple','Caller raises HTTP 502 with the actual SMTP error message as detail'],],
        widths=W3l, center_cols={0})

    doc.add_heading('6.10 Security Implementation', level=2)
    p(doc, '(Full security analysis in Chapter 9. Summary of implementations:)')
    bullets(doc, [
        'Password hashing: bcrypt via passlib with cost factor 12.',
        'Authentication: JWT HS256 tokens with 24-hour expiry injected via Depends().',
        'Authorization: Role-based get_current_admin() dependency for all admin routes.',
        'Input validation: Pydantic BaseModel on all POST and PUT request bodies.',
        'CORS: FastAPI CORSMiddleware restricting allowed origins.',
        'Secret management: All credentials in .env file excluded from version control.',
        'SQL injection prevention: Parameterized SQLAlchemy queries exclusively.',
    ])
    doc.add_page_break()

    # ── CHAPTER 7 ─────────────────────────────────────────────────
    doc.add_heading('Chapter 7 - Testing', level=1)
    doc.add_heading('7.1 Testing Strategy', level=2)
    p(doc, 'Testing was conducted using a layered approach. Unit tests target pure logic '
           'functions with no external dependencies. Integration tests verify API endpoints '
           'against the database using FastAPI\'s TestClient. System tests verify end-to-end '
           'workflows. User acceptance testing follows the complete CS agent workflow. '
           'The emphasis is on correctness, contract compliance, and workflow integrity '
           'rather than exhaustive combinatorial coverage.')

    doc.add_heading('7.2 Unit Testing', level=2)
    code(doc, '''\
# test_features.py - unit tests for ticket_urgency_score()
import pytest
from features import ticket_urgency_score

@pytest.mark.parametrize("input_val, expected", [
    (None,           0.0),     # None -> zero
    (float("nan"),   0.0),     # NaN -> zero
    ("7",            7),       # numeric string -> integer
    ("0",            0),       # zero string -> zero
    ("15",           10),      # above max -> clamped to 10
    ("Cannot login", 5.0),     # unrecognized text -> default 5.0
    (5.0,            5),       # float passthrough
])
def test_ticket_urgency_score(input_val, expected):
    assert ticket_urgency_score(input_val) == expected
''', 'Listing 7.1: Unit tests for ticket_urgency_score() using pytest.mark.parametrize')

    doc.add_heading('7.3 Integration Testing', level=2)
    code(doc, '''\
# test_api.py - integration tests using FastAPI TestClient
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def get_test_token():
    r = client.post("/auth/login",
                    data={"username": "test@example.com", "password": "testpass"})
    return r.json()["access_token"]

def test_customer_detail_has_required_fields():
    token = get_test_token()
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get(f"/customers/{TEST_CUSTOMER_ID}", headers=headers)
    assert r.status_code == 200
    body = r.json()
    for field in ["shap_explanations", "login_frequency_raw",
                  "daily_usage_mins", "last_support_ticket_raw",
                  "churn_risk_score", "customer_id"]:
        assert field in body, f"Missing field: {field}"
''', 'Listing 7.2: Integration test verifying customer detail endpoint response schema')

    doc.add_heading('7.4 System Testing - Test Case Table', level=2)
    tbl(doc, ['TC ID', 'Module', 'Test Input', 'Expected Result', 'Actual Result', 'Status'],
        [['TC-01', 'Auth',      'POST /auth/signup with valid email and password',                '201 Created, user in DB',             '201 Created',                  'PASS'],
         ['TC-02', 'Auth',      'POST /auth/login with correct credentials',                      '200 OK, JWT token in response',       '200 OK, token returned',       'PASS'],
         ['TC-03', 'Auth',      'POST /auth/login with wrong password',                           '401 Unauthorized',                    '401 Unauthorized',             'PASS'],
         ['TC-04', 'Auth',      'GET /customers with no Authorization header',                    '401 Unauthorized',                    '401 Unauthorized',             'PASS'],
         ['TC-05', 'Auth',      'GET /admin/users with Member-role JWT token',                    '403 Forbidden',                       '403 Forbidden',                'PASS'],
         ['TC-06', 'Customers', 'GET /customers?high_risk_only=true with valid token',            'List of customers with score > 0.70', 'Correctly filtered list',      'PASS'],
         ['TC-07', 'Customers', 'GET /customers/{valid_id} with valid token',                     'JSON with shap_explanations, login_frequency_raw, daily_usage_mins', 'All fields present', 'PASS'],
         ['TC-08', 'Customers', 'GET /customers/{unknown_uuid} with valid token',                 '404 Not Found',                       '404 Not Found',                'PASS'],
         ['TC-09', 'Customers', 'GET /customers/{id}/risk_trend?days=14',                         'Array of 14 {date, score} objects',   '14 data points returned',      'PASS'],
         ['TC-10', 'Dashboard', 'GET /customers/summary with valid token',                        'total_customers, high_risk_count, avg_risk_score, distributions', 'All fields present', 'PASS'],
         ['TC-11', 'Email',     'POST /emails/generate with valid customer_id',                   '200 OK with subject, body, source fields', 'source=fallback_template', 'PASS'],
         ['TC-12', 'Email',     'POST /emails/drafts with subject and body',                      '201 Created, draft in DB',            '201 Created',                  'PASS'],
         ['TC-13', 'Email',     'PUT /emails/drafts/{id} with updated body',                      '200 OK with updated draft returned',  '200 OK, updated correctly',    'PASS'],
         ['TC-14', 'Email',     'POST /emails/drafts/{id}/send_test with valid token',            'Test email to current user, 200 OK',  '200 OK, to = user email',      'PASS'],
         ['TC-15', 'Email',     'POST /emails/drafts/{id}/send on a draft already marked sent',   '400 Bad Request',                     '400 Bad Request',              'PASS'],
         ['TC-16', 'Email',     'DELETE /emails/drafts/{id} with valid token',                    '204 No Content, draft removed',       '204 No Content',               'PASS'],
         ['TC-17', 'Pipeline',  'ticket_urgency_score(None)',                                     '0.0',                                 '0.0',                          'PASS'],
         ['TC-18', 'Pipeline',  'ticket_urgency_score("15") - above maximum value',               '10 (clamped to maximum)',             '10',                           'PASS'],
         ['TC-19', 'Pipeline',  'Call run_scoring_pass() while a pass is already running',        'Second call returns -1 (skipped)',    'Returns -1',                   'PASS'],
         ['TC-20', 'Reports',   'POST /reports/generate with report_type=churn_overview',         'Report saved with result_json in DB', 'Report created successfully',  'PASS'],
         ['TC-21', 'Reports',   'GET /reports/{id}/export with valid report ID',                  'CSV file download as StreamingResponse', 'CSV file downloaded',        'PASS'],
         ['TC-22', 'Notes',     'POST /customers/{id}/notes with note text',                      'Note saved with author and created_at', 'Note persisted correctly',   'PASS'],
         ['TC-23', 'Billing',   'GET /billing/subscription with valid token',                     'Plan name, quota limit, and emails used this period', 'All fields returned', 'PASS'],
         ['TC-24', 'Settings',  'PUT /settings/app with new threshold value as Admin',            '200 OK, setting persisted in DB',     '200 OK, setting updated',      'PASS'],],
        widths=W6t, center_cols={0, 5})

    doc.add_heading('7.5 User Acceptance Testing', level=2)
    p(doc, 'A complete end-to-end UAT was performed by following the primary CS agent workflow:')
    numbered(doc, [
        'Opened the application at http://localhost:5173 — the login page rendered correctly with dark-mode styling.',
        'Registered a new account — automatically redirected to the dashboard.',
        'Dashboard displayed three KPI tiles, risk distribution chart, SHAP chart, and high-risk customer table with live data.',
        'Clicked a high-risk customer row — CustomerDetail loaded within ~200ms with SHAP chart, 14-day trend, and activity history.',
        'Clicked "Generate Retention Email" — the fallback template email was returned (no OpenAI key in the test environment).',
        'Edited the draft subject and body in the EmailDrafts composer — changes saved correctly.',
        'Clicked "Send Test Email" — a test email was received at the logged-in user address.',
        'Navigated to Reports — generated a Churn Overview report and downloaded it as a CSV file.',
        'All steps completed without errors. No broken layouts, missing data, or JavaScript exceptions were observed.',
    ])
    doc.add_page_break()

    # ── CHAPTER 8 ─────────────────────────────────────────────────
    doc.add_heading('Chapter 8 - Results and Discussion', level=1)
    doc.add_heading('8.1 System Output', level=2)
    p(doc, 'The fully deployed RetainAI system continuously produces the following outputs:')
    bullets(doc, [
        'Live Churn Risk Scores: A dynamically updated probability score for every customer, recalculated every 15 seconds.',
        'SHAP Explanations: A JSON feature-attribution breakdown for every prediction, showing which behaviours increase or decrease the risk score.',
        'AI Retention Emails: Personalized draft emails tailored to each customer\'s specific risk drivers, ready for human review before dispatch.',
        'Analytics Reports: Five report types exportable as CSV snapshots: churn overview, customer risk, revenue at risk, model performance, retention campaign.',
        'Alerts: Slack webhook and email notifications for customers crossing the configurable high-risk threshold.',
    ])

    doc.add_heading('8.2 Implemented Features', level=2)
    tbl(doc, ['Feature', 'Implementation Status', 'Technology Used'],
        [['JWT Login and Registration',           'Implemented',          'bcrypt + python-jose + FastAPI'],
         ['15-second ML scoring pipeline',        'Implemented',          'APScheduler + scikit-learn Random Forest'],
         ['SHAP feature attributions',            'Implemented',          'SHAP TreeExplainer + JSON storage'],
         ['Dashboard KPI tiles',                  'Implemented',          'React + Tailwind CSS + live API data'],
         ['Risk Distribution Pie Chart',          'Implemented',          'Recharts PieChart + live data'],
         ['SHAP Feature Importance Bar Chart',    'Implemented',          'Recharts BarChart + top_driver_breakdown'],
         ['14-day Risk Trend Chart',              'Implemented',          'Recharts LineChart + /risk_trend endpoint'],
         ['Customer Detail Profile Page',         'Implemented',          'React + 4 parallel API calls via Promise.all()'],
         ['AI Email Generation',                  'Implemented',          'OpenAI GPT-4o-mini + template fallback'],
         ['Batch Email Generation (cap 7)',        'Implemented',          'FastAPI endpoint + Python Set deduplication'],
         ['Email Dispatch via SMTP',              'Implemented',          'smtplib STARTTLS + Resend relay'],
         ['CS Notes per Customer',                'Implemented',          'Full CRUD REST endpoints'],
         ['Customer Owner Assignment',            'Implemented',          'Admin-only PUT endpoint'],
         ['Analytics Reports and CSV Export',     'Implemented',          '5 report types + StreamingResponse'],
         ['Team Management (Role Changes)',        'Implemented',          'Admin-only endpoint + ORM'],
         ['Billing Plan Enforcement and Quota',   'Implemented',          'Subscription + Plan ORM models'],
         ['High-Risk Slack and Email Alerts',     'Implemented',          'Slack webhook + smtplib'],
         ['In-Memory TTL Cache',                  'Implemented',          'Python dict + time.time()'],
         ['Multi-Tenancy',                        'Not Implemented',       'Planned as Future Enhancement'],
         ['Mobile Application',                   'Not Implemented',       'Planned as Future Enhancement'],],
        widths=W3f, center_cols={1})

    doc.add_heading('8.3 Results and Charts', level=2)
    fig(doc, dpath('fig_distribution.png'), 'Figure 8.3: Customer Risk Distribution (500 Customers)', Inches(4.0))
    fig(doc, dpath('fig_shap.png'), 'Figure 8.1: Global Feature Importance by Mean SHAP Value', Inches(5.2))

    doc.add_heading('8.4 Performance Discussion', level=2)
    fig(doc, dpath('fig_trend.png'), 'Figure 8.2: 14-Day Churn Risk Trend - Two Representative Customers', Inches(5.2))
    p(doc, 'The at-risk customer\'s score rises from 0.40 to 0.88 over 14 days, crossing the '
           '0.70 alert threshold by day 10. This provides the CS team a 4-day window to intervene '
           'before the customer reaches near-certain churn territory. The stable customer\'s score '
           'consistently remains below 0.25.')

    doc.add_heading('8.5 User Experience', level=2)
    p(doc, 'The dashboard uses a professional dark-mode design. Colour semantics are consistent: '
           'red for high-risk, amber for medium, green for low-risk and positive indicators. '
           'The SHAP chart uses red bars for risk-increasing features and green for '
           'risk-decreasing features, making the explanation immediately interpretable without '
           'technical training. Parallel API loading ensures the CustomerDetail page loads in '
           'under 200ms on a local connection.')

    doc.add_heading('8.6 Screenshots (Placeholders)', level=2)
    for fig_id, label in [
        ('8.4', 'Login Page - Dark-mode email and password form'),
        ('8.5', 'Dashboard - KPI tiles, PieChart, SHAP BarChart, ComposedChart, and high-risk table'),
        ('8.6', 'Customer Detail - Risk meter, SHAP bar chart, 14-day trend, and activity history'),
        ('8.7', 'Email Drafts - AI composer with tone and length controls, and draft list sidebar'),
        ('8.8', 'Reports Page - Report type selector, generated reports table, and CSV export'),
        ('8.9', 'Settings Page - Billing plan details, threshold slider, and SMTP configuration'),
    ]:
        doc.add_heading(f'Figure {fig_id}: {label}', level=3)
        ph = doc.add_paragraph('[INSERT SCREENSHOT HERE]')
        ph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in ph.runs: r.font.name = MONO; r.font.size = Pt(10); r.italic = True
        doc.add_paragraph()
    doc.add_page_break()

    # ── CHAPTER 9 ─────────────────────────────────────────────────
    doc.add_heading('Chapter 9 - Security and Performance', level=1)

    doc.add_heading('9.1 Authentication', level=2)
    p(doc, 'JWT tokens are signed using HMAC-SHA256 (HS256) with SECRET_KEY from environment '
           'variables. Each token encodes the user email as "sub" and an "exp" timestamp '
           '24 hours from issuance. Expired tokens return HTTP 401 automatically. '
           'The server is stateless - no session store is required.')

    doc.add_heading('9.2 Password Security', level=2)
    p(doc, 'Passwords are hashed using bcrypt via passlib. bcrypt: (1) automatically generates '
           'a unique random salt per password, preventing rainbow table attacks; '
           '(2) has a configurable cost factor (12), making brute-force computationally expensive; '
           '(3) is inherently slow by design, resistant to GPU-accelerated attacks. '
           'Plain-text passwords are never stored, logged, or returned in API responses.')

    doc.add_heading('9.3 Authorization (Role-Based Access Control)', level=2)
    p(doc, 'Two roles: Member (CS Agent) and Admin. All endpoints use get_current_user() '
           'for basic JWT validation. Admin endpoints additionally use get_current_admin(), '
           'which re-queries the users table to verify role = "admin". '
           'This prevents privilege escalation via crafted JWT claims.')

    doc.add_heading('9.4 Input Validation', level=2)
    p(doc, 'All POST and PUT request bodies are validated by Pydantic BaseModel classes '
           'before any business logic executes. This prevents type coercion errors, ensures '
           'required field presence, and enforces value constraints (e.g., min_risk < max_risk). '
           'Invalid payloads receive a 422 Unprocessable Entity response automatically.')

    doc.add_heading('9.5 Data Protection', level=2)
    bullets(doc, [
        'All credentials (SECRET_KEY, OPENAI_API_KEY, SMTP_PASSWORD, DATABASE_URL) are environment variables loaded from .env.',
        'The .env file is in .gitignore and never committed to version control.',
        'Neon PostgreSQL uses TLS-encrypted connections for all data in transit by default.',
        'CORS is configured via FastAPI CORSMiddleware restricting allowed origins.',
    ])

    doc.add_heading('9.6 SQL Injection Prevention', level=2)
    p(doc, 'SQLAlchemy parameterized queries are used exclusively throughout the codebase. '
           'All user-supplied values are passed as named bind parameters and properly escaped '
           'by the database driver. No raw string concatenation with user input is used '
           'in any SQL query.')

    doc.add_heading('9.7 Session Management', level=2)
    p(doc, 'Sessions are managed client-side via localStorage (key: "retainai_token"). '
           'The token is cleared on explicit logout. Token blacklisting (immediate revocation '
           'before the 24-hour expiry) is not implemented in the current version - '
           'this is documented as a Future Enhancement.')

    doc.add_heading('9.8 API Security', level=2)
    p(doc, 'The OAuth2PasswordBearer scheme passes tokens in the Authorization: Bearer header, '
           'not as cookies or URL parameters, reducing CSRF and URL-leakage risks. '
           'Rate limiting is not currently implemented and is marked as a Future Enhancement.')

    doc.add_heading('9.9 Performance Optimization', level=2)
    fig(doc, dpath('fig_latency.png'), 'Figure 9.1: API Endpoint Latency Benchmarks (P50 vs P95)', Inches(5.5))
    tbl(doc, ['Optimization', 'Technique Applied', 'Measured Impact'],
        [['Vectorized feature engineering',  'pandas groupby/merge instead of per-customer Python loops',    'O(N log N) vs O(N^2) per scoring pass'],
         ['Bulk database upsert',            'INSERT ON CONFLICT DO UPDATE for all N rows in one statement', 'N round trips reduced to 1 round trip'],
         ['In-memory TTL cache',             'Python dict cache with 15-second TTL for dashboard endpoints', '~80% DB query reduction under concurrent load'],
         ['Scoring thread lock',             'threading.Lock() prevents overlapping pipeline runs',          'Prevents race conditions and redundant computation'],
         ['Parallel API data loading',       'Promise.all() in CustomerDetail for 4 simultaneous requests',  'Total load time = max(individual) not sum(individual)'],
         ['DB connection pooling',           'SQLAlchemy QueuePool with pool_pre_ping=True',                 'Eliminates cold-start reconnection failures on Neon'],],
        widths=W3o, center_cols=set())

    doc.add_heading('9.10 Scalability', level=2)
    bullets(doc, [
        'API Layer: FastAPI is ASGI-compatible and can be horizontally scaled behind Nginx or any cloud load balancer. The API is fully stateless (JWT auth, external DB).',
        'ML Pipeline: The vectorized pipeline can scale to larger customer bases. For very large deployments, the roster can be sharded across parallel workers.',
        'Database: Neon PostgreSQL supports read replicas for read-heavy dashboard queries and PgBouncer for connection multiplexing.',
        'Cache: The in-memory dict cache can be replaced with Redis for multi-instance cache sharing without changing the cache interface.',
    ])
    doc.add_page_break()

    # ── CHAPTER 10 ────────────────────────────────────────────────
    doc.add_heading('Chapter 10 - Conclusion and Future Scope', level=1)

    doc.add_heading('10.1 Conclusion', level=2)
    p(doc, 'This project successfully demonstrates that a real-time, interpretable, and '
           'actionable customer churn prevention platform can be built as a full-stack '
           'web application within an academic project timeframe. RetainAI integrates a '
           'continuously updated ML scoring pipeline, SHAP-based explainability, and '
           'Generative AI email drafting into a single cohesive product backed by a '
           'production-quality REST API and a normalized relational database.')
    p(doc, 'The system closes the full feedback loop from data ingestion to intervention: '
           'raw behavioural events are written every few seconds, features are computed '
           'vectorially every 15 seconds, the model scores every customer, SHAP values '
           'explain each score, and the platform immediately offers the CS agent a '
           'personalized AI-drafted email addressing the exact issues driving that customer\'s '
           'risk. This end-to-end automation dramatically reduces time-to-action for '
           'customer success teams.')

    doc.add_heading('10.2 Project Achievements', level=2)
    numbered(doc, [
        'Built a real-time churn scoring engine that processes 500 customers in under 1.5 seconds on a 15-second schedule.',
        'Implemented SHAP TreeExplainer providing per-customer, per-feature attribution for every prediction in the pipeline.',
        'Integrated OpenAI GPT-4o-mini for personalized retention email generation with configurable tone and length.',
        'Delivered a professional dark-mode B2B dashboard with four interactive Recharts visualizations.',
        'Built a complete RBAC system with Admin and Member roles enforced at the API dependency level.',
        'Implemented billing plan enforcement with AI email quota tracking across 30-day billing periods.',
        'Designed a 12-table normalized PostgreSQL database with complete foreign key enforcement.',
        'Achieved sub-45ms P95 API latency for all core dashboard endpoints (excluding external AI calls).',
    ])

    doc.add_heading('10.3 Limitations', level=2)
    bullets(doc, [
        'Single-tenant: The system supports one organization. Multi-tenancy would require a complete architectural redesign with an Organization model layer.',
        'Static ML model: The model does not automatically retrain as new customer data accumulates. Manual retraining is needed for production accuracy maintenance.',
        'OpenAI dependency: AI email quality and availability depend on a paid external API. The fallback template is generic and not personalized.',
        'Neon free-tier cold starts: The database can experience 2-5 second reconnection delays after idle periods.',
        'No JWT revocation: Tokens cannot be invalidated before their 24-hour expiry without adding a server-side blacklist.',
        'Desktop-only UI: The dashboard is designed for 1280px+ screens. No mobile-responsive or native mobile application exists.',
    ])

    doc.add_heading('10.4 Future Scope', level=2)
    bullets(doc, [
        'Multi-tenancy: Add an Organisation model layer to support multiple SaaS customers from a single deployment.',
        'CRM Integration: Bidirectional sync with Salesforce and HubSpot to enrich feature data and automatically log CS interventions.',
        'Automated Model Retraining: Implement a scheduled pipeline that retrains on accumulated labelled data and hot-swaps the production model.',
        'A/B Email Testing: Multi-armed bandit framework to test different email templates and optimize open and reply rates.',
        'Mobile Application: React Native dashboard for CS agents working away from desktop.',
        'Token Blacklisting: Redis-backed revocation list for immediate session invalidation on logout or security events.',
        'Real Event Streaming: Replace the realtime.py simulator with a Kafka consumer for true production event ingestion.',
        'NPS Integration: Add Net Promoter Score survey responses as a fifth model feature to improve prediction accuracy.',
    ])

    doc.add_heading('10.5 Possible Improvements', level=2)
    bullets(doc, [
        'Replace in-memory TTL cache with Redis for cache sharing across horizontally scaled API instances.',
        'Add confidence intervals for predictions to help agents prioritize their outreach effectively.',
        'Implement email open and click-through tracking to measure retention campaign effectiveness.',
        'Add payment failure events as a sixth model feature.',
    ])

    doc.add_heading('10.6 Scalability', level=2)
    p(doc, 'The architecture supports straightforward horizontal scaling. The API tier is '
           'stateless (JWT auth, external DB, no server-local state) and can be deployed '
           'behind a load balancer with multiple replicas. The ML pipeline is independent '
           'and can be moved to a dedicated worker process or serverless function. '
           'PostgreSQL supports read replicas for read-heavy dashboard queries. '
           'These decisions ensure the system can scale from 500 to 50,000+ customers '
           'without fundamental architectural redesign.')
    doc.add_page_break()

    # ── REFERENCES ────────────────────────────────────────────────
    doc.add_heading('References', level=1)
    for r in [
        '[1] S. M. Lundberg and S.-I. Lee, "A Unified Approach to Interpreting Model Predictions," Advances in Neural Information Processing Systems (NeurIPS), vol. 30, 2017.',
        '[2] OpenAI, "GPT-4 Technical Report," arXiv preprint arXiv:2303.08774, 2023.',
        '[3] T. Chen and C. Guestrin, "XGBoost: A Scalable Tree Boosting System," Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining, 2016, pp. 785-794.',
        '[4] F. Pedregosa et al., "Scikit-learn: Machine Learning in Python," Journal of Machine Learning Research, vol. 12, pp. 2825-2830, 2011.',
        '[5] S. A. Neslin et al., "Defection Detection: Measuring and Understanding the Predictive Accuracy of Customer Churn Models," Journal of Marketing Research, vol. 43, no. 2, pp. 204-211, 2006.',
        '[6] M. T. Ribeiro, S. Singh, and C. Guestrin, "Why Should I Trust You?: Explaining the Predictions of Any Classifier," Proceedings of KDD 2016, pp. 1135-1144.',
        '[7] S. Ramirez, "FastAPI Framework Documentation," Tiangolo, 2024. [Online]. Available: https://fastapi.tiangolo.com',
        '[8] Meta Platforms Inc., "React Documentation," 2024. [Online]. Available: https://react.dev',
        '[9] Tailwind Labs Inc., "Tailwind CSS Documentation," 2024. [Online]. Available: https://tailwindcss.com',
        '[10] SQLAlchemy Authors, "SQLAlchemy 2.0 Documentation," 2024. [Online]. Available: https://www.sqlalchemy.org',
        '[11] Neon Inc., "Neon Serverless PostgreSQL Documentation," 2024. [Online]. Available: https://neon.tech/docs',
        '[12] T. Mike, "APScheduler - Advanced Python Scheduler Documentation," 2024. [Online]. Available: https://apscheduler.readthedocs.io',
        '[13] OWASP Foundation, "OWASP Top Ten Security Risks," 2021. [Online]. Available: https://owasp.org/www-project-top-ten/',
        '[14] Resend Inc., "Resend Email API Documentation," 2024. [Online]. Available: https://resend.com/docs',
    ]:
        rp = doc.add_paragraph(r)
        rp.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        rp.paragraph_format.space_after = Pt(4)
        for run in rp.runs: run.font.name = BODY; run.font.size = Pt(10)
    doc.add_page_break()

    # ── APPENDIX ──────────────────────────────────────────────────
    doc.add_heading('Appendix A - Key Source Code', level=1)
    doc.add_heading('A.1 Pipeline Feature Engineering (pipeline.py)', level=2)
    code(doc, '''\
def _build_feature_frame(roster, logins, usage, tickets, as_of=None):
    """Vectorized feature engineering for all N customers in one pass."""
    as_of = as_of or datetime.utcnow()
    df = roster.copy()
    df["Account_Age_Days"] = df["signup_date"].apply(
        lambda d: max(1, (as_of.date() - d).days))

    if not logins.empty:
        login_counts = logins.groupby("customer_id").size()
        df["Login_Frequency"] = df["customer_id"].map(login_counts).fillna(0).astype(int)
    else:
        df["Login_Frequency"] = 0

    if not usage.empty:
        usage_avg = usage.groupby("customer_id")["duration_secs"].mean() / 60
        df["Daily_Usage_Mins"] = df["customer_id"].map(usage_avg).fillna(0.0)
    else:
        df["Daily_Usage_Mins"] = 0.0

    if not tickets.empty:
        latest = tickets.drop_duplicates("customer_id", keep="first") \
                        .set_index("customer_id")["subject"]
        df["Last_Support_Ticket"] = df["customer_id"].map(latest).apply(ticket_urgency_score)
    else:
        df["Last_Support_Ticket"] = 0.0
    return df
''', 'Listing A.1: Feature engineering function from pipeline.py')

    doc.add_heading('A.2 Database Schema (Key Tables)', level=2)
    code(doc, '''\
-- Core entity
CREATE TABLE ml_customers (
    customer_id  VARCHAR  PRIMARY KEY,
    name         VARCHAR  NOT NULL,
    email        VARCHAR  NOT NULL UNIQUE,
    signup_date  DATE     NOT NULL
);

-- ML predictions (upserted every 15s)
CREATE TABLE customer_predictions (
    id                INTEGER PRIMARY KEY,
    customer_id       VARCHAR NOT NULL UNIQUE REFERENCES ml_customers(customer_id),
    churn_probability FLOAT   NOT NULL,
    top_driver        VARCHAR,
    shap_values       TEXT,
    scored_at         TIMESTAMP,
    model_version     VARCHAR
);

-- Email drafts
CREATE TABLE email_drafts (
    id          INTEGER PRIMARY KEY,
    customer_id VARCHAR NOT NULL REFERENCES ml_customers(customer_id),
    subject     VARCHAR NOT NULL DEFAULT \'\',
    body        TEXT    NOT NULL DEFAULT \'\',
    tone        VARCHAR NOT NULL DEFAULT \'professional\',
    length      VARCHAR NOT NULL DEFAULT \'medium\',
    status      VARCHAR NOT NULL DEFAULT \'draft\',
    created_by  VARCHAR,
    created_at  TIMESTAMP,
    sent_at     TIMESTAMP
);
''', 'Listing A.2: Core database table DDL')

    doc.add_heading('Appendix B - Missing Information Checklist', level=1)
    p(doc, 'The following items require the student to provide before final submission:')
    numbered(doc, [
        '[TO BE PROVIDED] Actual application screenshots to replace all [INSERT SCREENSHOT HERE] placeholders in Section 8.6.',
        '[TO BE PROVIDED] Student registration/roll number for the title page.',
        '[TO BE PROVIDED] Department declaration and certificate pages (typically provided by the university).',
        '[TO BE PROVIDED] Acknowledgements section with personal acknowledgements.',
        '[TO BE PROVIDED] Details of the training dataset used for the ML model (source, size, features).',
        '[TO BE PROVIDED] Name of internal examiner and external examiner for the project evaluation.',
    ])

    doc.add_heading('Appendix C - 20 Viva Questions with Answers', level=1)
    qas = [
        ('Q1: What is the purpose of RetainAI?',
         'RetainAI is a real-time customer churn prediction and mitigation platform for SaaS businesses. It identifies at-risk customers before they cancel using machine learning, explains each risk score via SHAP values, and automatically drafts personalized retention emails using OpenAI GPT-4o-mini.'),
        ('Q2: What machine learning algorithm does RetainAI use?',
         'A Random Forest Classifier from scikit-learn. It was chosen because it handles non-linear feature interactions, is robust to imbalanced datasets, and is directly compatible with SHAP TreeExplainer for fast, exact feature attribution without approximation.'),
        ('Q3: What are SHAP values and why are they used?',
         'SHAP (SHapley Additive exPlanations) values attribute the final prediction to each input feature using cooperative game theory. They are used because CS agents need to understand WHY a customer is flagged, not just that they are. Without interpretability, agents cannot craft effective interventions.'),
        ('Q4: What are the four model features and why were these windows chosen?',
         'Account_Age_Days (lifetime), Login_Frequency (14-day window - captures weekly engagement patterns), Daily_Usage_Mins (7-day window - captures recent engagement), and Last_Support_Ticket (30-day window - captures dissatisfaction signals). Window lengths were chosen based on literature (Burez & Van den Poel, 2009) showing that shorter windows capture leading indicators better.'),
        ('Q5: How is the scoring pipeline triggered and how often?',
         'APScheduler fires the run_scoring_pass() function every 15 seconds as a background thread within the FastAPI process. A threading.Lock() prevents overlapping runs if one pass takes longer than expected.'),
        ('Q6: Why is threading.Lock used and what problem does it solve?',
         'Without a lock, if a pipeline pass takes longer than 15 seconds (e.g., due to DB latency), a second scheduled pass would start concurrently. This would cause duplicate database writes and potential race conditions on shared data structures like the results list. The lock ensures only one pass runs at a time.'),
        ('Q7: How does JWT authentication work in the system?',
         'On login, the server verifies the password with bcrypt and signs a JWT using HMAC-SHA256 with a secret key. The token contains the user email as "sub" and a 24-hour expiry. Clients include this token in the Authorization: Bearer header. FastAPI\'s Depends(get_current_user) decodes and validates it on every protected request.'),
        ('Q8: Why is bcrypt used instead of SHA-256 for passwords?',
         'bcrypt is purpose-built for passwords. It automatically generates a random salt (preventing rainbow table attacks), has a configurable cost factor that keeps pace with hardware improvements, and is inherently slow by design. SHA-256 is too fast and can be brute-forced with GPUs. bcrypt makes brute-force computationally infeasible.'),
        ('Q9: What is the difference between the Admin and Member roles?',
         'Members (CS Agents) can view customers, generate and send emails, add notes, and generate reports. Admins additionally have access to team management, billing plan changes, customer owner assignment, high-risk alert triggering, and system settings configuration.'),
        ('Q10: How does AI email generation work step by step?',
         'The backend fetches the customer\'s profile and SHAP values. It constructs a structured prompt including the risk drivers in readable form, the desired tone and length. The prompt is sent to OpenAI GPT-4o-mini. The response is parsed for a SUBJECT line and body text. If OpenAI fails, a template-based fallback is returned with source="fallback_template".'),
        ('Q11: What is the in-memory TTL cache and why is it needed?',
         'It is a Python dictionary that stores API responses for 15 seconds, keyed by endpoint and parameters. It prevents redundant database queries when multiple CS agents load the dashboard simultaneously. Without it, 50 concurrent dashboard loads would trigger 50 identical DB queries per second.'),
        ('Q12: Why is a Set used in batch email generation?',
         'To check whether a customer already has an unsent draft in O(1) time. A set of already-drafted customer IDs is built once (O(D)), then each candidate is checked with "customer_id in already_drafted" at O(1). Using a list for this check would be O(D) per customer, making the total O(N x D) instead of O(N + D).'),
        ('Q13: What is the time complexity of the scoring pipeline?',
         'O(N + E) where N is the number of customers and E is the total number of events within the look-back windows. The dominant operation is the pandas groupby aggregation at O(E log N). Model inference is O(N x T x D) where T=100 trees and D=4 features, which is effectively O(N) for fixed T and D.'),
        ('Q14: How is the 14-day risk trend chart computed?',
         'The get_customer_trend() function in pipeline.py loads all events for one customer from a wide time window. It then iterates day by day, filtering events to each day\'s specific look-back window, runs feature engineering for that day\'s snapshot, and calls model.predict_proba(), building a {date, score} data point per day.'),
        ('Q15: How is the bulk upsert implemented and why is it better than individual updates?',
         'Using PostgreSQL\'s INSERT ... ON CONFLICT DO UPDATE (via SQLAlchemy\'s insert().on_conflict_do_update()). All 500 customers\' predictions are updated in a single SQL statement and one network round trip, compared to 500 individual UPDATE statements and 500 round trips. This reduces DB write time from ~1,500ms to ~50ms.'),
        ('Q16: What is pool_pre_ping=True and when is it needed?',
         'SQLAlchemy checks each connection from the pool with a lightweight SELECT 1 query before using it. If the connection is stale (Neon paused the DB after idle time), it automatically reconnects. Without this, stale connections cause OperationalError crashes on the first request after an idle period.'),
        ('Q17: How does RetainAI prevent SQL injection?',
         'By using SQLAlchemy parameterized queries exclusively. All user-supplied values are passed as named bind parameters. SQLAlchemy and the psycopg2 driver handle proper escaping at the driver level. No raw string concatenation with user input is used in any query anywhere in the codebase.'),
        ('Q18: What is the space complexity of the ML pipeline?',
         'O(N x F + E) where N=500 customers, F=4 features, giving a 2,000-float feature matrix. The SHAP matrix adds another O(N x F) = 2,000 floats. The event DataFrames are O(E). Total is dominated by O(E) during the event loading phase.'),
        ('Q19: What are the main limitations of RetainAI?',
         'Single-tenant (one organization), static ML model with no automatic retraining, dependency on paid OpenAI API for AI email quality, Neon free-tier cold-start delays, no JWT token revocation before expiry, and desktop-only UI with no mobile support.'),
        ('Q20: What would be the first improvement you would make if given more time?',
         'Automated ML model retraining. The current model is trained once and deployed statically. As customer behavior patterns evolve, prediction accuracy will degrade. A scheduled retraining pipeline that automatically labels churned customers, retrains the model monthly, evaluates on a holdout set, and hot-swaps the production model would make RetainAI genuinely production-grade.'),
    ]
    for q, a in qas:
        doc.add_heading(q, level=3)
        p(doc, a, size=10.5)
        doc.add_paragraph()

    out_path = 'RetainAI_Complete_Report_MCA_ChristUniversity.docx'
    doc.save(out_path)
    print(f"SUCCESS: {out_path} saved with all tables fully populated.")


if __name__ == '__main__':
    build()
