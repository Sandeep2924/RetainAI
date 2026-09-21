// The one bold moment on the dashboard: an actual radial gauge for the
// high-risk share, not just a bigger number in the same card chrome as
// everything else around it.
function RiskGauge({ ratio, size = 92 }) {
  const stroke = 8;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(1, ratio || 0));
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ flexShrink: 0 }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--bg-2)" strokeWidth={stroke} />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke="var(--risk-high)" strokeWidth={stroke} strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={c * (1 - clamped)}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
    </svg>
  );
}

export default function StatCard({ label, value, sublabel, accent, hero, gaugeRatio }) {
  if (hero) {
    return (
      <div
        style={{
          background: "linear-gradient(160deg, var(--bg-1) 55%, var(--risk-high-bg) 220%)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--glow-risk)",
          padding: "22px 26px",
          flex: "0 0 auto",
          minWidth: 300,
          display: "flex",
          alignItems: "center",
          gap: 22,
        }}
      >
        <div>
          <p style={{ fontSize: 13.5, color: "var(--text-secondary)", marginBottom: 12 }}>{label}</p>
          <p className="mono" style={{ fontSize: 52, fontWeight: 600, color: accent || "var(--text-primary)", lineHeight: 1 }}>
            {value}
          </p>
          {sublabel && <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 10 }}>{sublabel}</p>}
        </div>
        {gaugeRatio != null && <RiskGauge ratio={gaugeRatio} />}
      </div>
    );
  }

  return (
    <div
      style={{
        background: "var(--bg-1)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-md)",
        padding: "16px 18px",
        flex: 1,
        minWidth: 150,
      }}
    >
      <p style={{ fontSize: 12.5, color: "var(--text-secondary)", marginBottom: 8 }}>{label}</p>
      <p className="mono" style={{ fontSize: 24, fontWeight: 600, color: accent || "var(--text-primary)", lineHeight: 1 }}>
        {value}
      </p>
      {sublabel && <p style={{ fontSize: 11.5, color: "var(--text-muted)", marginTop: 6 }}>{sublabel}</p>}
    </div>
  );
}
