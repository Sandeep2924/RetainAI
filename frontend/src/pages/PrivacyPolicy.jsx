import { ArrowLeft, ShieldCheck, Lock, Database, Eye } from "lucide-react";

export default function PrivacyPolicy({ onBack }) {
  return (
    <div className="flex flex-col gap-6 max-w-4xl mx-auto pb-16 text-slate-200">
      <div className="flex items-center justify-between border-b border-slate-800 pb-5">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-cyan-950/60 border border-cyan-800/60 rounded-lg text-cyan-400">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">Privacy Policy</h1>
            <p className="text-xs sm:text-sm text-slate-400">
              Effective Date: November 7, 2026 | RetainAI Platform
            </p>
          </div>
        </div>
        {onBack && (
          <button
            onClick={onBack}
            className="flex items-center gap-2 px-3.5 py-2 text-xs sm:text-sm font-medium text-slate-300 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
        )}
      </div>

      <div className="space-y-8 text-sm leading-relaxed text-slate-300">
        <section className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 sm:p-6">
          <h2 className="text-base font-semibold text-white mb-2 flex items-center gap-2">
            <Lock className="w-4 h-4 text-cyan-400" />
            1. Commitment to Enterprise Data Protection
          </h2>
          <p>
            RetainAI ("we", "our", or "the Platform") operates a customer retention intelligence engine designed for B2B software organizations. We treat all ingested customer telemetry, model features, and organizational credentials as strictly confidential. RetainAI does not sell, lease, or broker customer data to any third party under any circumstances.
          </p>
        </section>

        <section className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 sm:p-6 space-y-3">
          <h2 className="text-base font-semibold text-white mb-2 flex items-center gap-2">
            <Database className="w-4 h-4 text-cyan-400" />
            2. Categories of Information Processed
          </h2>
          <p>
            The Platform collects and processes information solely required to calculate churn risk metrics and generate proactive customer engagement workflows:
          </p>
          <ul className="list-disc pl-5 space-y-2 text-slate-300">
            <li>
              <strong className="text-white">Account Authentication Data:</strong> User business email addresses, salted and hashed passwords (Argon2 / PBKDF2), role specifications, and multi-factor session tokens.
            </li>
            <li>
              <strong className="text-white">Customer Account Telemetry:</strong> Account age, login frequency, average daily session minutes, billing status, support ticket counts, and urgent keyword metadata required for ML feature calculation.
            </li>
            <li>
              <strong className="text-white">Churn Predictions and Model Explainability:</strong> Computed churn probability scores, SHAP driver attributions, risk classification tiers, and historical score trajectories.
            </li>
            <li>
              <strong className="text-white">Retention Communication Drafts:</strong> Customer success email templates, draft versions, internal notes, and team assignment records.
            </li>
          </ul>
        </section>

        <section className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 sm:p-6 space-y-3">
          <h2 className="text-base font-semibold text-white mb-2 flex items-center gap-2">
            <Eye className="w-4 h-4 text-cyan-400" />
            3. Machine Learning Inference & Third-Party Processing
          </h2>
          <p>
            RetainAI uses local XGBoost and Random Forest predictive models executing inside isolated application runtime containers. Feature arrays are transformed in memory and scored deterministically.
          </p>
          <p>
            When automated retention draft generation is enabled via OpenAI integration, only the selected customer contact name and anonymized retention risk drivers are transmitted over TLS 1.3 to generate draft text. In accordance with enterprise zero-data-retention standards, customer data transmitted through enterprise API endpoints is not used to train or fine-tune public foundation models.
          </p>
        </section>

        <section className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 sm:p-6 space-y-3">
          <h2 className="text-base font-semibold text-white mb-2">4. Data Storage and Security Controls</h2>
          <p>
            All persistent operational records are stored in enterprise PostgreSQL databases utilizing encrypted volume storage at rest (AES-256) and TLS encryption in transit. Role-based access control (RBAC) ensures that only verified and administrator-approved team members can access customer records and trigger predictive analyses.
          </p>
        </section>

        <section className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 sm:p-6 space-y-3">
          <h2 className="text-base font-semibold text-white mb-2">5. Data Subject Rights & Deletion</h2>
          <p>
            Users and client organizations retain full control over their data. In accordance with applicable data privacy regulations (including GDPR and CCPA), authorized account administrators may request a comprehensive export of all customer records or execute complete data purging by contacting security@retain.in.
          </p>
        </section>

        <section className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 sm:p-6">
          <h2 className="text-base font-semibold text-white mb-2">6. Inquiries and Compliance Contact</h2>
          <p>
            For questions concerning this Privacy Policy or platform compliance protocols, contact our security and legal team at{" "}
            <a href="mailto:security@retain.in" className="text-cyan-400 hover:text-cyan-300 underline font-mono">
              security@retain.in
            </a>
            .
          </p>
        </section>
      </div>
    </div>
  );
}
