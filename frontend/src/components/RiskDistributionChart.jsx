const TIER_COLOR = { low: "var(--risk-low)", medium: "var(--risk-mid)", high: "var(--risk-high)" };

// Bucket labels now come from the backend with dynamic percentages, e.g.
// "high (70-100%)" when the admin sets the threshold to 70% — so this reads
// the tier off the first word instead of matching a fixed string.
function tierOf(label) {
  return label.split(" ")[0];
}

export default function RiskDistributionChart({ distribution }) {
  const entries = Object.entries(distribution);
  const total = entries.reduce((sum, [, count]) => sum + count, 0);

  if (total === 0) {
    return <p style={{ fontSize: 13, color: "var(--text-muted)" }}>No scored customers yet.</p>;
  }

  return (
    <div>
      <div
        style={{
          display: "flex", height: 14, borderRadius: "var(--radius-sm)",
          overflow: "hidden", background: "var(--bg-2)",
        }}
      >
        {entries.map(([label, count]) => {
          const pct = (count / total) * 100;
          if (pct === 0) return null;
          return (
            <div
              key={label}
              title={`${label}: ${count}`}
              style={{ width: `${pct}%`, background: TIER_COLOR[tierOf(label)], minWidth: count > 0 ? 2 : 0 }}
            />
          );
        })}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 18 }}>
        {entries.map(([label, count]) => {
          const tier = tierOf(label);
          const rangeText = label.slice(label.indexOf("(") + 1, label.indexOf(")"));
          return (
            <div key={label} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span
                  aria-hidden="true"
                  style={{ width: 8, height: 8, borderRadius: 2, background: TIER_COLOR[tier], flexShrink: 0 }}
                />
                <span style={{ fontSize: 13, color: "var(--text-secondary)", textTransform: "capitalize" }}>
                  {tier}
                </span>
                <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{rangeText}</span>
              </div>
              <span className="mono" style={{ fontSize: 13, color: "var(--text-primary)" }}>{count}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
