import { useEffect, useMemo, useState } from "react";
import { fetchCustomers, downloadCustomersCsv } from "../api";
import CustomerTable from "../components/CustomerTable";

export default function AllCustomers({ onSelectCustomer, onBack }) {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchCustomers(false)
      .then((data) => {
        if (!cancelled) setCustomers(data);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load customers. Is the backend running?");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    let list = customers;
    if (filter === "high") list = list.filter((c) => c.churn_risk_score >= 0.66);
    if (filter === "mid") list = list.filter((c) => c.churn_risk_score >= 0.33 && c.churn_risk_score < 0.66);
    if (filter === "low") list = list.filter((c) => c.churn_risk_score < 0.33);
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      list = list.filter(
        (c) => c.name.toLowerCase().includes(q) || c.email.toLowerCase().includes(q)
      );
    }
    return list;
  }, [customers, query, filter]);

  async function handleExport() {
    setExporting(true);
    try {
      await downloadCustomersCsv(filter === "high");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h2 style={{ fontSize: 22, marginBottom: 4 }}>All customers</h2>
          <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            {loading ? "Loading…" : `${filtered.length} of ${customers.length} customers`}
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button
            onClick={handleExport}
            disabled={exporting}
            style={{
              background: "none",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)",
              color: "var(--text-primary)",
              fontSize: 13,
              padding: "8px 14px",
            }}
          >
            {exporting ? "Exporting…" : "Export CSV"}
          </button>
          <button
            onClick={onBack}
            style={{
              background: "none",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)",
              color: "var(--text-primary)",
              fontSize: 13,
              padding: "8px 14px",
            }}
          >
            Back to dashboard
          </button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search name or email"
          style={{
            flex: "1 1 240px",
            padding: "9px 12px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border)",
            background: "var(--bg-1)",
            color: "var(--text-primary)",
            fontSize: 14,
            outline: "none",
          }}
        />
        {[
          { key: "all", label: "All" },
          { key: "high", label: "High risk" },
          { key: "mid", label: "Watch" },
          { key: "low", label: "Healthy" },
        ].map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            style={{
              padding: "9px 14px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border)",
              background: filter === f.key ? "var(--bg-2)" : "transparent",
              color: filter === f.key ? "var(--text-primary)" : "var(--text-secondary)",
              fontSize: 13,
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div
        style={{
          background: "var(--bg-1)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-md)",
          padding: 20,
        }}
      >
        {error ? (
          <p style={{ color: "var(--risk-high)" }}>{error}</p>
        ) : loading ? (
          <p style={{ color: "var(--text-secondary)" }}>Loading customers…</p>
        ) : (
          <CustomerTable customers={filtered} onSelect={onSelectCustomer} />
        )}
      </div>
    </div>
  );
}
