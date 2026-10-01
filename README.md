# 🛡️ RetainAI — Predictive Customer Retention & Churn Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-5.0+-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon_Cloud-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://neon.tech)
[![Scikit-Learn](https://img.shields.io/badge/scikit_learn-ML_Model-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)](https://scikit-learn.org)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT_Powered-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com)

> **RetainAI** is an enterprise-grade AI customer retention and churn intelligence platform designed for B2B SaaS businesses. It predicts account cancellation risks in real time, explains the underlying drivers using **SHAP (SHapley Additive exPlanations)**, and generates tailored recovery campaigns with **Generative AI** before revenue is lost.

---

## 📌 Table of Contents

- [The Problem We Solve](#-the-problem-we-solve)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Account Verification & Approval Workflow](#-account-verification--approval-workflow)
- [Technology Stack](#-technology-stack)
- [Getting Started (Local Development)](#-getting-started-local-development)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#1-backend-setup)
  - [Frontend Setup](#2-frontend-setup)
- [Environment Configuration](#-environment-configuration)
- [Production Deployment](#-production-deployment)
  - [Frontend on Vercel](#frontend-on-vercel)
  - [Backend on Render](#backend-on-render)
- [Core API Reference](#-core-api-reference)
- [License](#-license)

---

## 💡 The Problem We Solve

In modern subscription businesses, acquiring new customers costs **5x to 7x more** than retaining existing ones. Customer Success (CS) teams often face these critical challenges:

1. **Lagging Indicators:** Knowing a customer cancelled when they submit a cancellation ticket is too late.
2. **Telemetry Overload:** Thousands of daily login events, feature clicks, and support tickets sit siloed and unmonitored.
3. **Lack of Explainability:** Black-box ML models output risk numbers without explaining *why* an account is at risk.
4. **Outreach Bottlenecks:** Crafting tailored retention emails for hundreds of accounts takes dozens of hours each week.

**RetainAI solves this end-to-end:**
- Aggregates behavioral telemetry continuously into meaningful customer health indicators.
- Employs calibrated Machine Learning classification to compute accurate **Churn Probability Scores**.
- Deconstructs risk factors transparently via **SHAP driver analytics**.
- Automatically drafts personalized, context-aware retention emails powered by **GPT-4o-mini**.

---

## ✨ Key Features

### 1. 🔮 Real-Time Machine Learning Churn Scoring
- Evaluates moving-average login frequencies, daily active minutes, support ticket urgency, payment failures, and account age.
- High-performance, vectorized scoring pass processes 500+ customer accounts in under **0.3 seconds**.
- Configurable risk threshold bands: **Low**, **Medium**, **High**, and **Critical**.

### 2. 🔍 Explainable AI with SHAP
- Clear feature attribution breakdowns for every customer account.
- Tells Customer Success agents exactly what is hurting health (e.g. *"72% drop in weekly login frequency"* or *"3 unaddressed high-priority support tickets"*).

### 3. ✉️ AI-Powered Retention Email Generator
- Generates context-aware customer recovery drafts informed by the account's specific SHAP risk drivers.
- Configurable tone (empathetic, urgent, executive, collaborative) and length.
- Built-in draft review, manual editing, and 1-click test email dispatch.

### 4. 🔒 Enterprise Security & 2-Step Approval Workflow
- **Step 1:** Account creation with password and confirm password validation.
- **Step 2:** Secure 6-digit email OTP verification.
- **Admin Approval Gate:** Once email is verified, an approval request with 1-click **Approve** and **Reject** buttons is sent to the organization administrator.
- Accounts are activated only when **both** email verification and admin approval are confirmed.

### 5. 📊 Executive Churn & Revenue Analytics
- **Historical Risk Trends:** Trailing 7-month cohort churn tracking.
- **Engagement Correlation:** Scatter plot correlating login activity with churn probabilities.
- **Cohort Health Matrix:** Radar chart benchmarking at-risk cohorts against healthy baselines.
- **ARR Impact Breakdown:** Visualizes preserved ARR vs at-risk ARR by quarter.
- Automated scheduled reporting with direct **Excel (.xlsx)** and **CSV** data exports.

---

## 🏗️ System Architecture

```mermaid
graph TD
    subgraph Client [Client Application]
        UI[React 19 + Tailwind CSS]
        Charts[Recharts Interactive Dashboards]
    end

    subgraph Server [FastAPI Backend]
        API[RESTful Endpoints & Auth]
        Scorer[Vectorized Batch Scorer]
        LLM[OpenAI Retention Drafter]
        Mailer[SMTP Email Dispatcher]
    end

    subgraph Data [Storage & ML Layer]
        DB[(Neon PostgreSQL)]
        Model[Scikit-Learn Churn Classifier]
        SHAP[SHAP TreeExplainer]
    end

    UI <-->|JSON / JWT Bearer| API
    API <-->|SQLAlchemy ORM| DB
    Scorer -->|Read Activity Events| DB
    Scorer -->|Feed Features| Model
    Model -->|Decompose Drivers| SHAP
    SHAP -->|Upsert Risk Scores| DB
    API -->|Prompt with SHAP Drivers| LLM
    API -->|OTP & Approval Alerts| Mailer
```

---

## 🔐 Account Verification & Approval Workflow

```mermaid
sequenceDiagram
    autonumber
    actor User as New User
    participant App as RetainAI Frontend
    participant API as FastAPI Backend
    participant DB as Neon Postgres
    participant SMTP as Gmail SMTP
    actor Admin as Administrator

    User->>App: Step 1: Submit Email & Password (with Confirm Password)
    App->>API: POST /signup
    API->>DB: Create User (is_verified=False, is_approved=False)
    API->>SMTP: Send 6-digit OTP code to user
    App->>User: Display Step 2: Verification Code Screen

    User->>App: Step 2: Enter 6-digit OTP Code
    App->>API: POST /verify-email
    API->>DB: Set is_verified = True
    API->>SMTP: Send Approval Request Email to Admin (sandeepkumar9837146@gmail.com)
    API-->>App: Return status: "Awaiting Admin Approval"
    App-->>User: Display "Awaiting Admin Approval" status card

    Note over User,Admin: User cannot log in until approved (403 Forbidden)

    Admin->>SMTP: Opens email & clicks [Approve Account]
    SMTP->>API: GET /admin/approve-account?token=...&action=approve
    API->>DB: Set is_approved = True
    API->>SMTP: Send "Account Approved!" celebration email to user
    API-->>Admin: Show "Account Approved" Confirmation Page

    User->>App: Log in with credentials
    App->>API: POST /login
    API-->>App: 200 OK + JWT Access Token
    App-->>User: Full Dashboard Access Granted 🚀
```

---

## 💻 Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 19, Vite, Tailwind CSS, Lucide Icons, Recharts, Axios |
| **Backend** | Python 3.11, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2.0, APScheduler |
| **Machine Learning** | Scikit-Learn, SHAP, Pandas, NumPy, Joblib |
| **Generative AI** | OpenAI API (GPT-4o-mini) |
| **Database** | Neon Serverless PostgreSQL |
| **Authentication** | OAuth2 Password Bearer, JWT (HS256), Passlib / Bcrypt |
| **Mailing System** | Gmail SMTP / Resend API |
| **Deployment** | Vercel (Frontend), Render (Backend / Docker) |

---

## 🚀 Getting Started (Local Development)

### Prerequisites

- **Python**: `>= 3.11`
- **Node.js**: `>= 18.0.0` and **npm**
- **Git**
- A **PostgreSQL** database (e.g., [Neon Cloud](https://neon.tech))
- (Optional) **OpenAI API Key** for AI email generation

---

### 1. Backend Setup

```bash
# Navigate to the backend directory
cd backend

# Create and activate a Python virtual environment
python -m venv venv

# On Windows:
venv\Scripts\activate
# On Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create your .env configuration
cp .env.example .env
```

Edit `backend/.env` with your credentials:
```env
PORT=8001
ENV=development
DATABASE_URL=postgresql://user:password@host/neondb?sslmode=require
SECRET_KEY=your_super_secret_key_at_least_32_characters_long
ADMIN_EMAILS=sandeepkumar9837146@gmail.com
ADMIN_APPROVAL_EMAIL=sandeepkumar9837146@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password
SMTP_FROM=your_email@gmail.com
FRONTEND_URL=http://localhost:5173
BACKEND_URL=http://localhost:8001
OPENAI_API_KEY=sk-...
```

Initialize tables and train the baseline model:
```bash
# Seed initial tables and run schema migrations
python -c "import sys; sys.path.insert(0, 'backend'); from database import init_all_tables; init_all_tables()"

# Start the FastAPI backend server on port 8001
python main.py
```

---

### 2. Frontend Setup

In a new terminal:
```bash
# Navigate to the frontend directory
cd frontend

# Install npm dependencies
npm install

# Start the Vite development server
npm run dev
```

Visit **[http://localhost:5173](http://localhost:5173)** in your browser!

---

## ⚙️ Environment Configuration

### Backend (`backend/.env`)

| Variable | Description | Example |
|---|---|---|
| `PORT` | Local backend listen port | `8001` |
| `DATABASE_URL` | Neon / PostgreSQL connection string | `postgresql://user:pass@host/db?sslmode=require` |
| `SECRET_KEY` | JWT signing secret (>= 32 chars) | `your_secret_key_here` |
| `SMTP_HOST` | Outgoing SMTP host | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port (STARTTLS) | `587` |
| `SMTP_USER` | SMTP username | `your_email@gmail.com` |
| `SMTP_PASSWORD` | SMTP password or Google App Password | `abcd efgh ijkl mnop` |
| `SMTP_FROM` | Sender email address | `your_email@gmail.com` |
| `ADMIN_APPROVAL_EMAIL` | Email receiving approval requests | `sandeepkumar9837146@gmail.com` |
| `ADMIN_EMAILS` | Comma-separated admin email list | `sandeepkumar9837146@gmail.com` |
| `FRONTEND_URL` | Base URL of frontend application | `http://localhost:5173` |
| `BACKEND_URL` | Base URL of backend API server | `http://localhost:8001` |
| `OPENAI_API_KEY` | OpenAI API key for retention drafts | `sk-...` |

### Frontend (`frontend/.env` / Vercel Environment Variables)

| Variable | Description | Example |
|---|---|---|
| `VITE_API_URL` | Public URL of the backend API | `https://your-backend.onrender.com` |

---

## 🌐 Production Deployment

### Frontend on Vercel
1. Import your GitHub repository into [Vercel](https://vercel.com).
2. Set Root Directory to `./` (or `frontend`).
3. Add Environment Variable:
   - `VITE_API_URL` = `https://your-backend-app.onrender.com`
4. Deploy! Vercel handles automated builds via [`vercel.json`](vercel.json).

### Backend on Render
1. Create a Web Service on [Render](https://render.com) using the included [`render.yaml`](render.yaml) blueprint.
2. Fill in the environment variables (`DATABASE_URL`, `SMTP_*`, `ADMIN_APPROVAL_EMAIL`, `OPENAI_API_KEY`).
3. Set `ALLOWED_ORIGINS` to include your Vercel domain: `https://retain-ai-olive.vercel.app,http://localhost:5173`.

---

## 📡 Core API Reference

| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/signup` | Step 1: Create account with password & confirm password | Public |
| `POST` | `/verify-email` | Step 2: Verify 6-digit OTP code & alert admin | Public |
| `GET` | `/admin/approve-account` | 1-Click Approve/Reject action link for admin | Secure Token |
| `POST` | `/login` | Authenticate user & issue JWT bearer token | Public |
| `GET` | `/me` | Get currently authenticated profile | Authenticated |
| `GET` | `/customers/summary` | Global portfolio health & risk counts | Authenticated |
| `GET` | `/customers/{id}` | Customer detail with SHAP risk attribution | Authenticated |
| `POST` | `/emails/generate` | Generate AI retention draft via OpenAI | Authenticated |
| `GET` | `/admin/users` | List organization team members and approval statuses | Admin |
| `POST` | `/admin/users/{email}/approve` | In-app admin approval for pending user | Admin |
| `POST` | `/admin/users/{email}/reject` | In-app admin rejection and account removal | Admin |

---

## 📄 License

This project is licensed under the **MIT License**.
Developed with ❤️ by the **RetainAI Team**.
