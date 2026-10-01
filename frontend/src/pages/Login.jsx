import { useState, useEffect } from "react";
import { login, signup, verifyEmail, resendVerification, setToken } from "../api";

export default function Login({ onAuthed }) {
  const params = new URLSearchParams(window.location.search);
  const pathIsVerify = window.location.pathname.toLowerCase().includes("verify");
  const queryIsVerify = params.get("mode") === "verify" || params.has("verify") || params.has("code");
  const isPendingApprovalParam = params.get("pending_approval") === "true";

  const [mode, setMode] = useState(
    isPendingApprovalParam
      ? "pending_approval"
      : pathIsVerify || queryIsVerify
      ? "verify"
      : "login"
  );
  const [email, setEmail] = useState(params.get("email") || "");
  const [password, setPassword] = useState("");
  const [verificationCode, setVerificationCode] = useState(params.get("code") || "");
  const [error, setError] = useState("");
  const [infoNotice, setInfoNotice] = useState(
    pathIsVerify || queryIsVerify ? "Enter your email address and 6-digit verification code below." : ""
  );
  const [debugCode, setDebugCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [resending, setResending] = useState(false);

  useEffect(() => {
    const urlEmail = params.get("email");
    const urlCode = params.get("code");
    const isPending = params.get("pending_approval") === "true";

    if (isPending) {
      setMode("pending_approval");
      if (urlEmail) setEmail(urlEmail);
      return;
    }

    if (urlEmail && urlCode && urlCode.trim().length === 6) {
      setBusy(true);
      setInfoNotice("Verifying your account from verification link…");
      verifyEmail(urlEmail.trim(), urlCode.trim())
        .then((data) => {
          if (data.requires_approval || !data.access_token) {
            setMode("pending_approval");
            setInfoNotice(data.message || "Email verified! Awaiting administrator approval.");
            setBusy(false);
          } else {
            setToken(data.access_token);
            onAuthed({ email: urlEmail.trim(), role: data.role });
          }
        })
        .catch((err) => {
          setError(err.response?.data?.detail || "Invalid or expired verification link.");
          setBusy(false);
        });
    }
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setInfoNotice("");
    setBusy(true);
    try {
      if (mode === "signup") {
        const signupData = await signup(email, password);
        if (signupData.requires_verification) {
          setMode("verify");
          setInfoNotice(signupData.notice || signupData.message || `Verification code sent to ${email}`);
          if (signupData.debug_code) {
            setDebugCode(signupData.debug_code);
          }
          window.history.pushState({}, "", "/verify");
          return;
        }
      }
      const data = await login(email, password);
      setToken(data.access_token);
      onAuthed({ email, role: data.role });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(
        detail || "Couldn't process your request. Check your details and try again."
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleVerify(e) {
    e.preventDefault();
    if (!email.trim()) {
      setError("Please enter your account email address.");
      return;
    }
    if (!verificationCode.trim()) {
      setError("Please enter the 6-digit verification code.");
      return;
    }
    setError("");
    setInfoNotice("");
    setBusy(true);
    try {
      const data = await verifyEmail(email.trim(), verificationCode.trim());
      if (data.requires_approval || !data.access_token) {
        setMode("pending_approval");
        setInfoNotice(data.message || "Email verified! Awaiting administrator approval.");
      } else {
        setToken(data.access_token);
        onAuthed({ email: email.trim(), role: data.role });
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Invalid or expired verification code.");
    } finally {
      setBusy(false);
    }
  }

  async function handleResendCode() {
    if (!email.trim()) {
      setError("Email address is required to resend verification code.");
      return;
    }
    setError("");
    setResending(true);
    try {
      const res = await resendVerification(email.trim());
      setInfoNotice(res.notice || res.message || `A new verification code was sent to ${email}`);
      if (res.debug_code) {
        setDebugCode(res.debug_code);
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't resend code. Please try again.");
    } finally {
      setResending(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        overflow: "hidden",
        padding: "16px",
        boxSizing: "border-box",
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
        style={{ position: "absolute", inset: 0, opacity: 0.5, pointerEvents: "none" }}
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
          width: "100%",
          maxWidth: 400,
          background: "var(--bg-1)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          padding: "30px 24px",
          boxSizing: "border-box",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
          <h1 style={{ fontSize: 22, margin: 0 }}>RetainAI</h1>
          {mode === "verify" && (
            <span style={{ fontSize: 11, padding: "2px 8px", background: "rgba(6, 182, 212, 0.15)", color: "var(--accent)", borderRadius: 12, border: "1px solid rgba(6, 182, 212, 0.3)" }}>
              Email Verification
            </span>
          )}
          {mode === "pending_approval" && (
            <span style={{ fontSize: 11, padding: "2px 8px", background: "rgba(245, 158, 11, 0.15)", color: "#f59e0b", borderRadius: 12, border: "1px solid rgba(245, 158, 11, 0.3)" }}>
              Awaiting Approval
            </span>
          )}
        </div>
        <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 24 }}>
          {mode === "pending_approval"
            ? "Your account request is waiting for administrator approval"
            : mode === "verify"
            ? (email ? `Enter the 6-digit code sent to ${email}` : "Enter your email address and verification code")
            : "Churn intelligence for your customer base"}
        </p>

        {mode === "pending_approval" ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 16, textAlign: "center" }}>
            <div style={{
              width: 52, height: 52, borderRadius: "50%",
              background: "rgba(16, 185, 129, 0.15)", border: "1px solid rgba(16, 185, 129, 0.4)",
              color: "#34d399", fontSize: 24, display: "flex", alignItems: "center", justifyContent: "center",
              margin: "0 auto 4px"
            }}>
              ✓
            </div>
            <div>
              <h3 style={{ margin: "0 0 6px 0", fontSize: 17, color: "var(--text-primary)" }}>
                Email Verified Successfully!
              </h3>
              <span style={{
                display: "inline-block", background: "rgba(14, 116, 144, 0.2)",
                color: "#38bdf8", padding: "3px 10px", borderRadius: 9999,
                fontSize: 11, fontWeight: 700, letterSpacing: 0.5, textTransform: "uppercase"
              }}>
                Awaiting Admin Approval
              </span>
            </div>
            <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6, margin: 0 }}>
              Your email address <strong style={{ color: "var(--accent)" }}>{email}</strong> has been confirmed.
              An approval request was sent to the administrator (<strong style={{ color: "#e2e8f0" }}>sandeepkumar9837146@gmail.com</strong>).
            </p>
            <div style={{
              background: "var(--bg-2)", border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)", padding: "12px 14px", fontSize: 12,
              color: "var(--text-muted)", textAlign: "left", lineHeight: 1.5
            }}>
              📧 You will receive an email confirmation at <strong>{email}</strong> once your account has been approved. You can then return to sign in.
            </div>
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setError("");
                setInfoNotice("");
                window.history.pushState({}, "", "/");
              }}
              style={submitStyle}
            >
              Back to Sign in
            </button>
          </div>
        ) : mode === "verify" ? (
          <form onSubmit={handleVerify} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
                Email Address
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
                6-Digit Verification Code
              </label>
              <input
                type="text"
                required
                maxLength={6}
                autoFocus={!!email}
                value={verificationCode}
                onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, ""))}
                placeholder="123456"
                style={{
                  ...inputStyle,
                  textAlign: "center",
                  fontSize: 22,
                  letterSpacing: 6,
                  fontFamily: "monospace",
                  fontWeight: 700,
                }}
              />
            </div>

            {infoNotice && (
              <div style={{ padding: "8px 12px", background: "rgba(6, 182, 212, 0.12)", border: "1px solid rgba(6, 182, 212, 0.35)", borderRadius: "var(--radius-sm)", fontSize: 12, color: "#a5f3fc" }}>
                {infoNotice}
              </div>
            )}

            {debugCode && (
              <div style={{ padding: "8px 12px", background: "rgba(245, 158, 11, 0.12)", border: "1px solid rgba(245, 158, 11, 0.35)", borderRadius: "var(--radius-sm)", fontSize: 12, color: "#fcd34d", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span>Code: <strong>{debugCode}</strong></span>
                <button
                  type="button"
                  onClick={() => setVerificationCode(debugCode)}
                  style={{ background: "none", border: "none", color: "#38bdf8", cursor: "pointer", fontSize: 11, textDecoration: "underline" }}
                >
                  Fill Code
                </button>
              </div>
            )}

            {error && (
              <p style={{ fontSize: 13, color: "var(--risk-high)", margin: 0 }}>{error}</p>
            )}

            <button type="submit" disabled={busy} style={submitStyle}>
              {busy ? "Verifying…" : "Verify & Activate Account"}
            </button>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 10, fontSize: 12 }}>
              <button
                type="button"
                onClick={handleResendCode}
                disabled={resending}
                style={{ background: "none", border: "none", color: "var(--accent)", padding: 0, cursor: "pointer", textDecoration: "underline" }}
              >
                {resending ? "Sending new code…" : "Resend code"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode("login");
                  setError("");
                  setInfoNotice("");
                  window.history.pushState({}, "", "/");
                }}
                style={{ background: "none", border: "none", color: "var(--text-muted)", padding: 0, cursor: "pointer" }}
              >
                Back to Sign in
              </button>
            </div>
          </form>
        ) : (
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
              <div>
                <p style={{ fontSize: 13, color: "var(--risk-high)", margin: "0 0 6px 0" }}>{error}</p>
                {error.toLowerCase().includes("not verified") && (
                  <button
                    type="button"
                    onClick={() => { setMode("verify"); setError(""); }}
                    style={{ background: "none", border: "none", color: "var(--accent)", fontSize: 12, cursor: "pointer", textDecoration: "underline", padding: 0 }}
                  >
                    Enter verification code now &rarr;
                  </button>
                )}
              </div>
            )}

            <button type="submit" disabled={busy} style={submitStyle}>
              {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>
        )}

        {mode !== "verify" && mode !== "pending_approval" && (
          <div style={{ marginTop: 20, textAlign: "center", display: "flex", flexDirection: "column", gap: 8 }}>
            <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0 }}>
              {mode === "login" ? "New here?" : "Already have an account?"}{" "}
              <button
                type="button"
                onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(""); }}
                style={{ background: "none", border: "none", color: "var(--accent)", fontSize: 13, padding: 0, cursor: "pointer" }}
              >
                {mode === "login" ? "Create an account" : "Sign in"}
              </button>
            </p>
            <button
              type="button"
              onClick={() => {
                setMode("verify");
                setError("");
                setInfoNotice("Enter your account email and 6-digit code to verify.");
                window.history.pushState({}, "", "/verify");
              }}
              style={{ background: "none", border: "none", color: "#38bdf8", fontSize: 12, padding: 0, cursor: "pointer", textDecoration: "underline" }}
            >
              Have a verification code? Verify account &rarr;
            </button>
          </div>
        )}

        <div
          style={{
            marginTop: 18,
            padding: "10px 12px",
            background: "rgba(14, 116, 144, 0.12)",
            border: "1px solid rgba(14, 116, 144, 0.35)",
            borderRadius: "var(--radius-sm)",
            fontSize: 12,
            color: "var(--text-secondary)",
            display: "flex",
            flexDirection: "column",
            gap: 4,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "#a5f3fc", fontWeight: 600 }}>Demo Account</span>
            <button
              type="button"
              onClick={() => {
                setEmail("test@retain.in");
                setPassword("password123");
                setError("");
              }}
              style={{
                background: "none",
                border: "none",
                color: "#38bdf8",
                fontSize: 12,
                cursor: "pointer",
                padding: 0,
                textDecoration: "underline",
              }}
            >
              Fill Credentials
            </button>
          </div>
          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
            Email: <code style={{ color: "#e2e8f0" }}>test@retain.in</code> &bull; Password: <code style={{ color: "#e2e8f0" }}>password123</code>
          </span>
        </div>
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
