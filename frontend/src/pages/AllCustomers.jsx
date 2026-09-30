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
    <div className="flex flex-col gap-5 max-w-7xl mx-auto pb-10">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-white mb-1">All Customers</h2>
          <p className="text-xs sm:text-sm text-slate-400">
            {loading ? "Loading…" : `${filtered.length} of ${customers.length} customers`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5 w-full sm:w-auto">
          <button
            onClick={handleExport}
            disabled={exporting}
            className="flex-1 sm:flex-initial text-center px-3.5 py-2 rounded-lg border border-slate-700 hover:border-slate-600 bg-slate-800/60 hover:bg-slate-700/60 text-slate-200 text-xs sm:text-sm font-medium transition-colors disabled:opacity-50"
          >
            {exporting ? "Exporting…" : "Export CSV"}
          </button>
          <button
            onClick={onBack}
            className="flex-1 sm:flex-initial text-center px-3.5 py-2 rounded-lg border border-slate-700 hover:border-slate-600 bg-slate-800/60 hover:bg-slate-700/60 text-slate-200 text-xs sm:text-sm font-medium transition-colors"
          >
            Back to Dashboard
          </button>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search name or email…"
          className="flex-1 px-3.5 py-2.5 rounded-xl border border-slate-700 bg-slate-900/60 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
        />
        <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
          {[
            { key: "all", label: "All" },
            { key: "high", label: "High Risk" },
            { key: "mid", label: "Watch" },
            { key: "low", label: "Healthy" },
          ].map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-3 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all ${
                filter === f.key
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                  : "bg-slate-800/50 text-slate-400 border border-slate-700 hover:text-slate-200 hover:bg-slate-800"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-slate-800/40 backdrop-blur-sm border border-slate-700 p-3 sm:p-5 rounded-2xl">
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
