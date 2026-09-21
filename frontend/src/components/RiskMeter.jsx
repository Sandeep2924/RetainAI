import { riskLevel, riskColor, formatPercent } from "../risk";

export default function RiskMeter({ score, width = 88 }) {
  const level = riskLevel(score);
  const color = riskColor[level];
  const pct = Math.round(score * 100);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div
        style={{
          width,
          height: 6,
          borderRadius: 3,
          background: "var(--bg-2)",
          overflow: "hidden",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: color,
            borderRadius: 3,
            transition: "width 0.4s ease",
          }}
        />
      </div>
      <span
        className="mono"
        style={{ fontSize: 13, color, fontWeight: 600, minWidth: 34 }}
      >
        {formatPercent(score)}
      </span>
    </div>
  );
}
