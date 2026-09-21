export default function Sidebar({ view, setView, email, role, onLogout }) {
  const items = [
    { key: "dashboard", label: "Dashboard" },
    { key: "customers", label: "All customers" },
    { key: "predictions", label: "Predictions" },
    { key: "emails", label: "Email drafts" },
    { key: "reports", label: "Reports" },
    { key: "settings", label: "Settings" },
    ...(role === "admin" ? [{ key: "team", label: "Team" }] : []),
  ];

  return (
    <div
      style={{
        width: 216,
        flexShrink: 0,
        background: "var(--bg-1)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        padding: "22px 0",
      }}
    >
      <div style={{ padding: "0 20px", marginBottom: 32, display: "flex", alignItems: "center", gap: 8 }}>
        <span
          aria-hidden="true"
          className="live-dot"
          style={{
            width: 8, height: 8, borderRadius: "50%",
            background: "var(--accent)", flexShrink: 0,
            boxShadow: "0 0 0 3px var(--accent-dim)",
          }}
        />
        <div>
          <h1 style={{ fontSize: 17, letterSpacing: "-0.01em" }}>RetainAI</h1>
          <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 1 }}>
            Risk console
          </p>
        </div>
      </div>

      <nav style={{ display: "flex", flexDirection: "column" }}>
        {items.map((item) => {
          const active = view === item.key;
          return (
            <button
              key={item.key}
              onClick={() => setView(item.key)}
              style={{
                position: "relative",
                textAlign: "left",
                padding: "9px 20px 9px 17px",
                border: "none",
                borderLeft: active ? "3px solid var(--accent)" : "3px solid transparent",
                background: active ? "var(--bg-2)" : "transparent",
                color: active ? "var(--text-primary)" : "var(--text-secondary)",
                fontSize: 13.5,
                fontWeight: active ? 600 : 400,
              }}
            >
              {item.label}
            </button>
          );
        })}
      </nav>

      <div style={{ marginTop: "auto", padding: "16px 20px 0", borderTop: "1px solid var(--border)" }}>
        <p style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 14, wordBreak: "break-all" }}>
          {email}
        </p>
        {role && (
          <p style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11.5, color: "var(--text-muted)", marginTop: 3, marginBottom: 12 }}>
            <span
              aria-hidden="true"
              style={{
                width: 6, height: 6, borderRadius: "50%",
                background: role === "admin" ? "var(--accent)" : "var(--border-strong)",
              }}
            />
            {role === "admin" ? "Admin" : "Member"}
          </p>
        )}
        <button
          onClick={onLogout}
          style={{
            width: "100%",
            padding: "8px 12px",
            marginTop: role ? 0 : 12,
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border)",
            background: "transparent",
            color: "var(--text-secondary)",
            fontSize: 13,
          }}
        >
          Sign out
        </button>
      </div>
    </div>
  );
}
