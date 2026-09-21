import { useRef, useState } from "react";
import { validatePredictionCsv, uploadPredictionCsv, predictChurn } from "../api";

const btnStyle = {
  padding: "8px 14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)",
  background: "transparent", color: "var(--text-primary)", fontSize: 13, cursor: "pointer",
};
const primaryBtnStyle = { ...btnStyle, border: "none", background: "var(--accent)", color: "#0b0f1a", fontWeight: 600 };
const cardStyle = { background: "var(--bg-1)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: 20 };
const inputStyle = {
  padding: "9px 10px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)",
  background: "var(--bg-2)", color: "var(--text-primary)", fontSize: 13, outline: "none", width: "100%",
};

const REQUIRED_COLS = ["customer_id", "Account_Age_Days", "Login_Frequency", "Daily_Usage_Mins", "Last_Support_Ticket"];

const RISK_COLOR = {
  Low: "var(--text-muted)", Medium: "var(--accent)", High: "var(--risk-high, #e07b39)", Critical: "var(--risk-high, #d94f4f)",
};

export default function Predictions({ onBack }) {
  const fileInputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [validating, setValidating] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState(null);

  async function handleFileChange(e) {
    const f = e.target.files?.[0];
    setError("");
    setResults(null);
    setPreview(null);
    setFile(f || null);
    if (!f) return;
    setValidating(true);
    try {
      const data = await validatePredictionCsv(f);
      setPreview(data);
    } catch (err) {
      setError(err.response?.data?.detail || "That file didn't pass validation.");
    } finally {
      setValidating(false);
    }
  }

  async function handleRun() {
    if (!file) return;
    setRunning(true);
    setError("");
    try {
      const data = await uploadPredictionCsv(file);
      setResults(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Prediction run failed.");
    } finally {
      setRunning(false);
    }
  }

  function handleDownload() {
    if (!results) return;
    const header = ["customer_id", "name", "churn_probability", "risk_level", "confidence", "top_driver"];
    const rows = results.results.map((r) => header.map((h) => r[h]).join(","));
    const csv = [header.join(","), ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "prediction_results.csv");
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  }

  function reset() {
    setFile(null);
    setPreview(null);
    setResults(null);
    setError("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h2 style={{ fontSize: 22, marginBottom: 4 }}>Predictions</h2>
          <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            Upload a CSV to score a batch of customers with the live model — doesn't touch your tracked
            customer roster, just a one-off run.
          </p>
        </div>
        <button onClick={onBack} style={btnStyle}>Back to dashboard</button>
      </div>

      {error && <p style={{ color: "var(--risk-high)", fontSize: 13 }}>{error}</p>}

      <div style={cardStyle}>
        <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 10 }}>
          Required columns: {REQUIRED_COLS.map((c) => <code key={c} style={{ marginRight: 6 }}>{c}</code>)}
          <br />
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
            <code>Last_Support_Ticket</code> can be a 0–10 number or free-text (e.g. the ticket subject) —
            text is scored for urgency automatically. Max 5MB / 5,000 rows.
          </span>
        </p>

        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <input ref={fileInputRef} type="file" accept=".csv" onChange={handleFileChange} style={{ fontSize: 13 }} />
          {file && (
            <button onClick={reset} style={btnStyle}>Clear</button>
          )}
        </div>

        {validating && <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 10 }}>Validating…</p>}

        {preview && (
          <div style={{ marginTop: 16 }}>
            <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 8 }}>
              {preview.row_count} row(s) validated. Preview:
            </p>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ textAlign: "left", color: "var(--text-muted)" }}>
                    {preview.columns.map((c) => (
                      <th key={c} style={{ padding: "0 10px 6px", fontWeight: 500 }}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.preview.map((row, i) => (
                    <tr key={i} style={{ borderTop: "1px solid var(--border)" }}>
                      {preview.columns.map((c) => (
                        <td key={c} style={{ padding: "6px 10px", color: "var(--text-secondary)" }}>{String(row[c])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button onClick={handleRun} disabled={running} style={{ ...primaryBtnStyle, marginTop: 14 }}>
              {running ? "Running prediction…" : `Run prediction on ${preview.row_count} row(s)`}
            </button>
          </div>
        )}
      </div>

      {results && (
        <div style={cardStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <p style={{ fontSize: 14, color: "var(--text-secondary)" }}>
              {results.row_count} result(s) · model {results.model_version}
            </p>
            <button onClick={handleDownload} style={btnStyle}>Download CSV</button>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ textAlign: "left", color: "var(--text-muted)", fontSize: 12 }}>
                  <th style={{ padding: "0 10px 8px", fontWeight: 500 }}>Customer</th>
                  <th style={{ padding: "0 10px 8px", fontWeight: 500 }}>Churn probability</th>
                  <th style={{ padding: "0 10px 8px", fontWeight: 500 }}>Risk level</th>
                  <th style={{ padding: "0 10px 8px", fontWeight: 500 }}>Confidence</th>
                  <th style={{ padding: "0 10px 8px", fontWeight: 500 }}>Top driver</th>
                </tr>
              </thead>
              <tbody>
                {results.results.map((r) => (
                  <tr key={r.customer_id} style={{ borderTop: "1px solid var(--border)" }}>
                    <td style={{ padding: "8px 10px" }}>{r.name || r.customer_id}</td>
                    <td style={{ padding: "8px 10px" }}>{Math.round(r.churn_probability * 100)}%</td>
                    <td style={{ padding: "8px 10px", color: RISK_COLOR[r.risk_level] || "var(--text-primary)", fontWeight: 600 }}>
                      {r.risk_level}
                    </td>
                    <td style={{ padding: "8px 10px", color: "var(--text-secondary)" }}>{r.confidence}%</td>
                    <td style={{ padding: "8px 10px", color: "var(--text-secondary)" }}>{r.top_driver}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <QuickPredictForm />
    </div>
  );
}

function QuickPredictForm() {
  const [form, setForm] = useState({
    customer_id: "", account_age_days: "", login_frequency: "", daily_usage_mins: "", last_support_ticket: "",
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setResult(null);
    if (!form.customer_id) {
      setError("Customer ID is required.");
      return;
    }
    setLoading(true);
    try {
      const data = await predictChurn({
        customer_id: form.customer_id,
        account_age_days: Number(form.account_age_days) || 0,
        login_frequency: Number(form.login_frequency) || 0,
        daily_usage_mins: Number(form.daily_usage_mins) || 0,
        last_support_ticket: form.last_support_ticket,
      });
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't run that prediction.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={cardStyle}>
      <h3 style={{ fontSize: 14, marginBottom: 12, color: "var(--text-secondary)" }}>Quick single-customer check</h3>
      <form onSubmit={handleSubmit} style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
        <Field label="Customer ID" value={form.customer_id} onChange={(v) => update("customer_id", v)} />
        <Field label="Account age (days)" type="number" value={form.account_age_days} onChange={(v) => update("account_age_days", v)} />
        <Field label="Logins (30d)" type="number" value={form.login_frequency} onChange={(v) => update("login_frequency", v)} />
        <Field label="Avg daily usage (mins)" type="number" value={form.daily_usage_mins} onChange={(v) => update("daily_usage_mins", v)} />
        <Field label="Last ticket (text or 0-10)" value={form.last_support_ticket} onChange={(v) => update("last_support_ticket", v)} wide />
        <button type="submit" disabled={loading} style={primaryBtnStyle}>
          {loading ? "Scoring…" : "Score"}
        </button>
      </form>
      {error && <p style={{ color: "var(--risk-high)", fontSize: 13, marginTop: 10 }}>{error}</p>}
      {result && (
        <p style={{ fontSize: 13, marginTop: 10 }}>
          <strong>{Math.round(result.churn_risk_score * 100)}%</strong> churn risk
          {result.high_risk ? " (high risk)" : ""} — top driver: {result.top_driver}
        </p>
      )}
    </div>
  );
}

function Field({ label, value, onChange, type = "text", wide = false }) {
  return (
    <label style={{ fontSize: 12, color: "var(--text-muted)", flex: wide ? "2 1 220px" : "1 1 140px" }}>
      {label}
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} style={{ ...inputStyle, marginTop: 4 }} />
    </label>
  );
}
