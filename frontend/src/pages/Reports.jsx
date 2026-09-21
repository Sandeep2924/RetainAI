import { useEffect, useState } from "react";
import { generateReport, fetchReports, fetchReport, deleteReport, downloadReportCsv } from "../api";

const REPORT_TYPES = [
  { key: "churn_overview", label: "Churn Overview" },
  { key: "customer_risk", label: "Customer Risk Report" },
  { key: "revenue_at_risk", label: "Revenue at Risk" },
  { key: "model_performance", label: "ML Model Performance" },
  { key: "retention_campaign", label: "Retention Campaign Report" },
];

const btnStyle = {
  padding: "8px 14px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border)",
  background: "transparent",
  color: "var(--text-primary)",
  fontSize: 13,
  cursor: "pointer",
};
const primaryBtnStyle = { ...btnStyle, border: "none", background: "var(--accent)", color: "#0b0f1a", fontWeight: 600 };
const cardStyle = { background: "var(--bg-1)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: 20 };
const inputStyle = {
  padding: "9px 10px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)",
  background: "var(--bg-2)", color: "var(--text-primary)", fontSize: 13, outline: "none",
};

export default function Reports({ onBack }) {
  const [reportType, setReportType] = useState(REPORT_TYPES[0].key);
  const [dateStart, setDateStart] = useState("");
  const [dateEnd, setDateEnd] = useState("");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const [history, setHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(true);

  const [activeReport, setActiveReport] = useState(null);
  const [loadingActive, setLoadingActive] = useState(false);

  useEffect(() => {
    loadHistory();
  }, []);

  function loadHistory() {
    setLoadingHistory(true);
    fetchReports()
      .then(setHistory)
      .catch(() => setError("Couldn't load report history."))
      .finally(() => setLoadingHistory(false));
  }

  async function handleGenerate() {
    setGenerating(true);
    setError("");
    try {
      const report = await generateReport(reportType, dateStart, dateEnd);
      setActiveReport(report);
      setHistory((prev) => [
        { id: report.id, report_type: report.report_type, name: report.name, status: report.status,
          created_by: report.created_by, created_at: report.created_at,
          date_range_start: report.date_range_start, date_range_end: report.date_range_end },
        ...prev,
      ]);
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't generate that report.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleOpen(id) {
    setLoadingActive(true);
    setError("");
    try {
      const report = await fetchReport(id);
      setActiveReport(report);
    } catch {
      setError("Couldn't load that report.");
    } finally {
      setLoadingActive(false);
    }
  }

  async function handleDelete(id) {
    try {
      await deleteReport(id);
      setHistory((prev) => prev.filter((r) => r.id !== id));
      if (activeReport?.id === id) setActiveReport(null);
    } catch {
      setError("Couldn't delete that report.");
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h2 style={{ fontSize: 22, marginBottom: 4 }}>Reports</h2>
          <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            Generated from live data — each report is a snapshot at the time you ran it.
          </p>
        </div>
        <button onClick={onBack} style={btnStyle}>Back to dashboard</button>
      </div>

      {error && <p style={{ color: "var(--risk-high)", fontSize: 13 }}>{error}</p>}

      <div style={cardStyle}>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <select value={reportType} onChange={(e) => setReportType(e.target.value)} style={inputStyle}>
            {REPORT_TYPES.map((t) => (
              <option key={t.key} value={t.key}>{t.label}</option>
            ))}
          </select>
          <label style={{ fontSize: 12, color: "var(--text-muted)" }}>
            From{" "}
            <input type="date" value={dateStart} onChange={(e) => setDateStart(e.target.value)} style={inputStyle} />
          </label>
          <label style={{ fontSize: 12, color: "var(--text-muted)" }}>
            To{" "}
            <input type="date" value={dateEnd} onChange={(e) => setDateEnd(e.target.value)} style={inputStyle} />
          </label>
          <button onClick={handleGenerate} disabled={generating} style={primaryBtnStyle}>
            {generating ? "Generating…" : "Generate report"}
          </button>
        </div>
        <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 10 }}>
          Date range applies to customer signup date (Churn Overview, Customer Risk, Revenue at Risk) or email-draft
          creation date (Retention Campaign). Model Performance always reflects the currently trained model.
        </p>
      </div>

      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        <div style={{ ...cardStyle, flex: "1 1 260px" }}>
          <h3 style={{ fontSize: 14, marginBottom: 12, color: "var(--text-secondary)" }}>History</h3>
          {loadingHistory ? (
            <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>Loading…</p>
          ) : history.length === 0 ? (
            <p style={{ fontSize: 13, color: "var(--text-muted)" }}>No reports generated yet.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {history.map((r) => (
                <div
                  key={r.id}
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-sm)",
                    padding: "10px 12px",
                    background: activeReport?.id === r.id ? "var(--bg-2)" : "transparent",
                  }}
                >
                  <div onClick={() => handleOpen(r.id)} style={{ cursor: "pointer" }}>
                    <p style={{ fontSize: 13, fontWeight: 500 }}>{r.name}</p>
                    <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                      {new Date(r.created_at).toLocaleString()} ·{" "}
                      <span style={{ color: r.status === "completed" ? "var(--text-muted)" : "var(--risk-high)" }}>
                        {r.status}
                      </span>
                    </p>
                  </div>
                  <button onClick={() => handleDelete(r.id)} style={{ ...btnStyle, fontSize: 11, padding: "4px 8px", marginTop: 8 }}>
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ ...cardStyle, flex: "2 1 480px" }}>
          {loadingActive ? (
            <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>Loading report…</p>
          ) : !activeReport ? (
            <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
              Generate a report above, or select one from history to view it here.
            </p>
          ) : (
            <ReportView report={activeReport} />
          )}
        </div>
      </div>
    </div>
  );
}

function ReportView({ report }) {
  const r = report.result || {};
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
        <div>
          <h3 style={{ fontSize: 16 }}>{report.name}</h3>
          <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
            Generated {new Date(report.created_at).toLocaleString()} by {report.created_by}
            {report.date_range_start ? ` · ${report.date_range_start} to ${report.date_range_end || "now"}` : ""}
          </p>
        </div>
        <button onClick={() => downloadReportCsv(report.id, report.report_type)} style={btnStyle}>
          Export CSV
        </button>
      </div>

      {report.report_type === "churn_overview" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Stats items={[
            ["Total customers", r.total_customers],
            ["Avg churn score", r.avg_churn_score != null ? `${Math.round(r.avg_churn_score * 100)}%` : "—"],
            ["High-risk count", r.high_risk_count],
          ]} />
          <BreakdownTable title="Risk distribution" data={r.risk_distribution} />
          <BreakdownTable title="Top driver breakdown" data={r.top_driver_breakdown} />
        </div>
      )}

      {report.report_type === "customer_risk" && (
        <CustomerTable
          rows={r.customers}
          columns={[
            ["customer_id", "ID"], ["name", "Name"], ["email", "Email"],
            ["risk_tier", "Tier"], ["top_driver", "Top driver"], ["owner_email", "Owner"],
          ]}
          scoreKey="churn_risk_score"
        />
      )}

      {report.report_type === "revenue_at_risk" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Stats items={[
            ["Total estimated MRR", `$${(r.total_estimated_mrr ?? 0).toLocaleString()}`],
            ["MRR at risk", `$${(r.estimated_mrr_at_risk ?? 0).toLocaleString()}`],
          ]} />
          <p style={{ fontSize: 11, color: "var(--text-muted)", fontStyle: "italic" }}>{r.assumption}</p>
          <CustomerTable
            rows={r.customers}
            columns={[["customer_id", "ID"], ["name", "Name"], ["estimated_mrr", "Est. MRR"]]}
            scoreKey="churn_risk_score"
          />
        </div>
      )}

      {report.report_type === "model_performance" && (
        r.available === false ? (
          <p style={{ fontSize: 13, color: "var(--text-muted)" }}>{r.reason}</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <Stats items={[
              ["Model version", r.model_version],
              ["ROC-AUC", r.roc_auc],
              ["Precision", r.precision],
              ["Recall", r.recall],
              ["Training rows", r.training_row_count],
              ["Trained at", r.trained_at ? new Date(r.trained_at).toLocaleString() : "—"],
            ]} />
            <p style={{ fontSize: 11, color: "var(--text-muted)", fontStyle: "italic" }}>{r.note}</p>
          </div>
        )
      )}

      {report.report_type === "retention_campaign" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Stats items={[["Total drafts", r.total_drafts], ["Sent", r.sent_count]]} />
          <BreakdownTable title="Tone breakdown" data={r.tone_breakdown} />
          <div>
            <h4 style={{ fontSize: 13, marginBottom: 8, color: "var(--text-secondary)" }}>Sent emails</h4>
            {!r.sent_emails || r.sent_emails.length === 0 ? (
              <p style={{ fontSize: 13, color: "var(--text-muted)" }}>None sent in this range.</p>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ textAlign: "left", color: "var(--text-muted)", fontSize: 12 }}>
                    <th style={{ padding: "0 10px 8px", fontWeight: 500 }}>Customer</th>
                    <th style={{ padding: "0 10px 8px", fontWeight: 500 }}>Subject</th>
                    <th style={{ padding: "0 10px 8px", fontWeight: 500 }}>Tone</th>
                    <th style={{ padding: "0 10px 8px", fontWeight: 500 }}>Sent at</th>
                    <th style={{ padding: "0 10px 8px", fontWeight: 500 }}>Current risk</th>
                  </tr>
                </thead>
                <tbody>
                  {r.sent_emails.map((e, i) => (
                    <tr key={i} style={{ borderTop: "1px solid var(--border)" }}>
                      <td style={{ padding: "8px 10px" }}>{e.customer_id}</td>
                      <td style={{ padding: "8px 10px" }}>{e.subject}</td>
                      <td style={{ padding: "8px 10px" }}>{e.tone}</td>
                      <td style={{ padding: "8px 10px", color: "var(--text-secondary)" }}>
                        {e.sent_at ? new Date(e.sent_at).toLocaleDateString() : "—"}
                      </td>
                      <td style={{ padding: "8px 10px", color: "var(--text-secondary)" }}>
                        {e.current_churn_risk_score != null ? `${Math.round(e.current_churn_risk_score * 100)}%` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Stats({ items }) {
  return (
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
      {items.map(([label, value]) => (
        <div
          key={label}
          style={{ background: "var(--bg-2)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "10px 14px", flex: "1 1 140px" }}
        >
          <p style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4 }}>{label}</p>
          <p style={{ fontSize: 15, fontWeight: 600 }}>{value ?? "—"}</p>
        </div>
      ))}
    </div>
  );
}

function BreakdownTable({ title, data }) {
  const entries = Object.entries(data || {});
  return (
    <div>
      <h4 style={{ fontSize: 13, marginBottom: 8, color: "var(--text-secondary)" }}>{title}</h4>
      {entries.length === 0 ? (
        <p style={{ fontSize: 13, color: "var(--text-muted)" }}>No data.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {entries.map(([key, value]) => (
            <div key={key} style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
              <span style={{ color: "var(--text-secondary)" }}>{key}</span>
              <span>{value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CustomerTable({ rows, columns, scoreKey }) {
  if (!rows || rows.length === 0) {
    return <p style={{ fontSize: 13, color: "var(--text-muted)" }}>No customers in this range.</p>;
  }
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ textAlign: "left", color: "var(--text-muted)", fontSize: 12 }}>
            {columns.map(([, label]) => (
              <th key={label} style={{ padding: "0 10px 8px", fontWeight: 500 }}>{label}</th>
            ))}
            {scoreKey && <th style={{ padding: "0 10px 8px", fontWeight: 500 }}>Risk</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{ borderTop: "1px solid var(--border)" }}>
              {columns.map(([key]) => (
                <td key={key} style={{ padding: "8px 10px", color: "var(--text-secondary)" }}>{String(row[key] ?? "—")}</td>
              ))}
              {scoreKey && (
                <td style={{ padding: "8px 10px" }}>{Math.round((row[scoreKey] || 0) * 100)}%</td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
