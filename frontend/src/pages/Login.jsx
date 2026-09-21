import { useState } from "react";
import { login, signup, setToken } from "../api";

export default function Login({ onAuthed }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "signup") {
        await signup(email, password);
      }
      const data = await login(email, password);
      setToken(data.access_token);
      onAuthed({ email, role: data.role });
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Couldn't sign in. Check your details and try again."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* A faint decaying signal line — the one visual idea for this page,
          echoing what the product actually does (watching a metric trend
          down) instead of a decorative pattern with no connection to it. */}
      <svg
        aria-hidden="true"
        width="100%" height="100%"
        viewBox="0 0 1000 600"
        preserveAspectRatio="xMidYMid slice"
        style={{ position: "absolute", inset: 0, opacity: 0.5 }}
      >
        <path
          d="M -50 220 C 120 180, 200 300, 340 260 S 520 140, 640 220 S 820 380, 1050 300"
          fill="none" stroke="var(--accent-dim)" strokeWidth="2"
        />
        <path
          d="M -50 340 C 150 300, 260 420, 420 380 S 600 260, 760 340 S 900 460, 1050 400"
          fill="none" stroke="var(--border)" strokeWidth="1.5"
        />
      </svg>

      <div
        style={{
          position: "relative",
          width: 360,
          background: "var(--bg-1)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          padding: "32px 28px",
        }}
      >
        <h1 style={{ fontSize: 22, marginBottom: 4 }}>RetainAI</h1>
        <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 28 }}>
          Churn intelligence for your customer base
        </p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
              Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              style={inputStyle}
            />
          </div>
          <div>
            <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
              Password
            </label>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              style={inputStyle}
            />
          </div>

          {error && (
            <p style={{ fontSize: 13, color: "var(--risk-high)" }}>{error}</p>
          )}

          <button type="submit" disabled={busy} style={submitStyle}>
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 20, textAlign: "center" }}>
          {mode === "login" ? "New here?" : "Already have an account?"}{" "}
          <button
            onClick={() => setMode(mode === "login" ? "signup" : "login")}
            style={{ background: "none", border: "none", color: "var(--accent)", fontSize: 13, padding: 0 }}
          >
            {mode === "login" ? "Create an account" : "Sign in"}
          </button>
        </p>
      </div>
    </div>
  );
}

const inputStyle = {
  width: "100%",
  padding: "10px 12px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border)",
  background: "var(--bg-2)",
  color: "var(--text-primary)",
  fontSize: 14,
  outline: "none",
};

const submitStyle = {
  padding: "10px 12px",
  borderRadius: "var(--radius-sm)",
  border: "none",
  background: "var(--accent)",
  color: "#0b0f1a",
  fontSize: 14,
  fontWeight: 600,
  marginTop: 6,
};
