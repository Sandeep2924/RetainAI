import { ArrowLeft, FileText, CheckCircle2, AlertCircle, Scale } from "lucide-react";

export default function TermsConditions({ onBack }) {
  return (
    <div className="flex flex-col gap-6 max-w-4xl mx-auto pb-16 text-slate-200">
      <div className="flex items-center justify-between border-b border-slate-800 pb-5">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-cyan-950/60 border border-cyan-800/60 rounded-lg text-cyan-400">
            <FileText className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">Terms and Conditions</h1>
            <p className="text-xs sm:text-sm text-slate-400">
              Last Updated: November 7, 2026 | RetainAI Master Services Agreement
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
            <CheckCircle2 className="w-4 h-4 text-cyan-400" />
            1. Acceptance of Terms
          </h2>
          <p>
            By accessing, creating an account on, or interacting with the RetainAI platform, your organization ("Customer") agrees to be bound by these Terms and Conditions. If you do not agree with any provision of these terms, you must discontinue access immediately.
          </p>
        </section>

        <section className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 sm:p-6 space-y-3">
          <h2 className="text-base font-semibold text-white mb-2 flex items-center gap-2">
            <Scale className="w-4 h-4 text-cyan-400" />
            2. Scope of Service & Operational Licensure
          </h2>
          <p>
            RetainAI provides continuous customer churn probability assessment, real-time activity ingestion, explainable risk factors via SHAP analytics, and automated retention workflow drafting.
          </p>
          <ul className="list-disc pl-5 space-y-2 text-slate-300">
            <li>
              <strong className="text-white">Authorized Users:</strong> Customer may grant platform access only to authorized personnel. Each user must maintain discrete login credentials and safeguard session tokens.
            </li>
            <li>
              <strong className="text-white">Account Verification:</strong> New account registrations require email OTP verification and explicit administrator approval prior to accessing production customer data.
            </li>
            <li>
              <strong className="text-white">Acceptable Use:</strong> Customer shall not use the service for unauthorized crawling, load flooding, reverse engineering model architectures, or transmitting malicious code.
            </li>
          </ul>
        </section>

        <section className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 sm:p-6 space-y-3">
          <h2 className="text-base font-semibold text-white mb-2 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-cyan-400" />
            3. Predictive Modeling and Retention Disclaimer
          </h2>
          <p>
            RetainAI generates churn probabilities and driver attributions based on statistical machine learning models trained on historical usage and ticket indicators. All scores, categorizations, and generated email drafts are decision-support resources designed to assist customer success teams.
          </p>
          <p>
            Predictions do not constitute contractual guarantees regarding customer behavior or renewal decisions. Customer teams retain sole operational discretion regarding communications sent to their end users.
          </p>
        </section>

        <section className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 sm:p-6 space-y-3">
          <h2 className="text-base font-semibold text-white mb-2">4. Service Availability and Maintenance</h2>
          <p>
            RetainAI strives to maintain 99.9% uptime for core API ingestion and scoring endpoints. Routine maintenance windows are announced in advance. RetainAI shall not be liable for transient interruptions caused by third-party upstream providers (cloud compute regions, external SMTP servers, or upstream DNS providers).
          </p>
        </section>

        <section className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 sm:p-6 space-y-3">
          <h2 className="text-base font-semibold text-white mb-2">5. Intellectual Property Rights</h2>
          <p>
            RetainAI retains all title, proprietary algorithms, model training code, and interface designs. Customer retains sole ownership and title to all raw business telemetry and customer database records uploaded or synchronized to the Platform.
          </p>
        </section>

        <section className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 sm:p-6">
          <h2 className="text-base font-semibold text-white mb-2">6. Inquiries and Legal Notice</h2>
          <p>
            Official legal notifications and inquiries regarding service contracts should be addressed to{" "}
            <a href="mailto:legal@retain.in" className="text-cyan-400 hover:text-cyan-300 underline font-mono">
              legal@retain.in
            </a>
            .
          </p>
        </section>
      </div>
    </div>
  );
}
