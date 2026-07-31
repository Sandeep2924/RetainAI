# RetainAI

**An Explainable, Real-Time Machine Learning Platform for Customer Churn Prediction and Automated Retention for SMEs/SaaS Businesses.**

## 📌 Project Overview
RetainAI is a multi-tenant, cloud-native platform designed to predict customer churn risk for small and mid-sized SaaS/SME businesses in near real-time. Unlike traditional batch-processing churn systems, RetainAI continuously streams customer activity, explains the *why* behind every risk score, and automates retention actions.

## 🚀 Core Features
*   **Real-time Event Ingestion:** Captures usage, billing, and support activity via an Apache Kafka streaming pipeline.
*   **Continuous Feature Engineering:** Computes rolling behavioral features (e.g., engagement decay, ticket backlog) continuously using Redis.
*   **Explainable ML (SHAP):** Predicts churn probability via XGBoost/LightGBM and provides human-readable SHAP feature attributions (explaining exactly what drove the score).
*   **Automated Retention:** Triggers automated, reason-aware interventions (e.g., discount offers, priority support) based on the risk drivers.
*   **Multi-Tenant Dashboard:** A full-stack React dashboard with live WebSocket updates, cohort analytics, and role-based access control (RBAC).

## 📄 Documentation
*   **Software Requirements Specification (SRS):** Detailed requirements, architecture, and system models can be found in `RetainAI_SRS.docx`.

## 🛠️ Tech Stack Architecture
*   **Event Streaming:** Apache Kafka
*   **Data Stores:** PostgreSQL (Multi-tenant data), Redis (Low-latency feature store)
*   **Machine Learning:** FastAPI, XGBoost/LightGBM, SHAP
*   **Frontend:** React, Recharts, WebSockets
*   **Infrastructure:** Docker, GitHub Actions (CI/CD), Prometheus/Grafana (Metrics), Terraform (IaC)

---
*Developed as part of MCA Specialization Project by Sandeep Kumar.*
