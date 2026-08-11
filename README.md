# RetainAI

**An Explainable, Real-Time Machine Learning Platform for Customer Churn Prediction and Automated Retention for SMEs/SaaS Businesses.**

## 📌 Project Overview
RetainAI is a multi-tenant, cloud-native platform designed to predict customer churn risk for small and mid-sized SaaS/SME businesses in near real-time. Unlike traditional batch-processing churn systems, RetainAI continuously streams customer activity, explains the *why* behind every risk score, and automates retention actions.

## 🚀 Core Features
*   **Real-time Event Ingestion:** Captures usage, billing, and support activity via an Apache Kafka streaming pipeline.
*   **Continuous Feature Engineering:** Computes rolling behavioral features (e.g., engagement decay, ticket backlog) continuously using Redis.
*   **Explainable ML (SHAP):** Predicts churn probability via XGBoost/LightGBM and provides human-readable SHAP feature attributions (explaining exactly what drove the score).
*   **Agentic AI (OpenAI LLM):** An autonomous agent that reads the ML diagnostic reasoning and generates highly personalized retention strategies and dynamic emails to prevent churn.
*   **Automated Retention:** Triggers automated, reason-aware interventions (e.g., booking optimization sessions, priority support) based on the risk drivers.
*   **Multi-Tenant Dashboard:** A full-stack React dashboard with live streaming updates, cohort analytics, and search filtering.

## 📄 Documentation
*   **Architecture & PRD:** Detailed requirements and system models can be found in `architecture.md` and `prd.md`.

## 🛠️ Tech Stack Architecture
*   **Event Streaming:** Apache Kafka
*   **Data Stores:** PostgreSQL (Multi-tenant data), Redis (Low-latency feature store)
*   **Machine Learning:** FastAPI, XGBoost/LightGBM, SHAP
*   **Frontend:** React, Recharts, WebSockets
*   **Infrastructure:** Docker, GitHub Actions (CI/CD), Prometheus/Grafana (Metrics), Terraform (IaC)

---
*Developed as part of MCA Specialization Project by Sandeep Kumar.*
