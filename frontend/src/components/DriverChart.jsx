import { driverLabel } from "../risk";

// Deliberately hand-rolled to match RiskDistributionChart's bar-and-legend
// language exactly, rather than a recharts BarChart with its own axis/
// tooltip chrome sitting right next to it — two dashboard charts that look
// like they came from different libraries was the actual "graphs differ
// from each other" problem.
const SHADE = ["var(--accent)", "#5c8f88", "#4d7a74", "#3f6560", "#33534e"];

export default function DriverChart({ breakdown }) {
  const data = Object.entries(breakdown)
    .map(([key, value]) => ({ name: driverLabel(key), count: value }))
    .sort((a, b) => b.count - a.count);
  const total = data.reduce((sum, d) => sum + d.count, 0);

  if (total === 0) {
    return <p style={{ fontSize: 13, color: "var(--text-muted)" }}>No scored customers yet.</p>;
  }

  return (
    <div>
      <div style={{ display: "flex", height: 14, borderRadius: "var(--radius-sm)", overflow: "hidden", background: "var(--bg-2)" }}>
        {data.map((d, i) => {
          const pct = (d.count / total) * 100;
          if (pct === 0) return null;
          return (
            <div
              key={d.name}
              title={`${d.name}: ${d.count}`}
              style={{ width: `${pct}%`, background: SHADE[i % SHADE.length], minWidth: d.count > 0 ? 2 : 0 }}
            />
          );
        })}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 18 }}>
        {data.map((d, i) => (
          <div key={d.name} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span
                aria-hidden="true"
                style={{ width: 8, height: 8, borderRadius: 2, background: SHADE[i % SHADE.length], flexShrink: 0 }}
              />
              <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>{d.name}</span>
            </div>
            <span className="mono" style={{ fontSize: 13, color: "var(--text-primary)" }}>{d.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
