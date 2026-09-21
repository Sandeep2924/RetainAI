import { useEffect, useState } from "react";
import {
  fetchMe, updateMe, changePassword, fetchAppSettings, updateAppSettings, fetchIntegrationsStatus,
  fetchPlans, fetchSubscription, updateSubscription,
} from "../api";
import { setRiskThresholds } from "../risk";

const TABS = ["General", "Notifications", "AI Model", "Billing", "Security", "Integrations"];

const btnStyle = {
  padding: "8px 14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)",
  background: "transparent", color: "var(--text-primary)", fontSize: 13, cursor: "pointer",
};
const primaryBtnStyle = { ...btnStyle, border: "none", background: "var(--accent)", color: "#0b0f1a", fontWeight: 600 };
const cardStyle = { background: "var(--bg-1)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: 20 };
const inputStyle = {
  padding: "9px 10px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)",
  background: "var(--bg-2)", color: "var(--text-primary)", fontSize: 13, outline: "none", width: "100%",
};
const labelStyle = { fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 4 };

export default function Settings({ onBack, isAdmin }) {
  const [tab, setTab] = useState("General");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h2 style={{ fontSize: 22 }}>Settings</h2>
        <button onClick={onBack} style={btnStyle}>Back to dashboard</button>
      </div>

      <div style={{ display: "flex", gap: 8, borderBottom: "1px solid var(--border)", paddingBottom: 4 }}>
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              ...btnStyle,
              border: "none",
              background: tab === t ? "var(--bg-1)" : "transparent",
              color: tab === t ? "var(--accent)" : "var(--text-secondary)",
              fontWeight: tab === t ? 600 : 400,
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "General" && <GeneralTab />}
      {tab === "Notifications" && <NotificationsTab />}
      {tab === "AI Model" && <AIModelTab isAdmin={isAdmin} />}
      {tab === "Billing" && <BillingTab isAdmin={isAdmin} />}
      {tab === "Security" && <SecurityTab />}
      {tab === "Integrations" && <IntegrationsTab />}
    </div>
  );
}

function useNotice() {
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  function ok(msg) { setNotice(msg); setError(""); }
  function fail(msg) { setError(msg); setNotice(""); }
  return { notice, error, ok, fail };
}

function Banner({ notice, error }) {
  if (!notice && !error) return null;
  return (
    <p style={{ fontSize: 13, color: error ? "var(--risk-high)" : "var(--accent)", marginBottom: 12 }}>
      {error || notice}
    </p>
  );
}

function GeneralTab() {
  const [me, setMe] = useState(null);
  const [form, setForm] = useState({ name: "", job_title: "", company_name: "", avatar_url: "" });
  const [saving, setSaving] = useState(false);
  const { notice, error, ok, fail } = useNotice();

  useEffect(() => {
    fetchMe()
      .then((data) => {
        setMe(data);
        setForm({ name: data.name, job_title: data.job_title, company_name: data.company_name, avatar_url: data.avatar_url });
      })
      .catch(() => fail("Couldn't load your profile."));
  }, []);

  async function handleSave() {
    if (!me) return;
    setSaving(true);
    try {
      await updateMe({ ...form, preferences: me.preferences || {} });
      ok("Saved.");
    } catch (err) {
      fail(err.response?.data?.detail || "Couldn't save changes.");
    } finally {
      setSaving(false);
    }
  }

  if (!me) return <div style={cardStyle}><Banner notice={notice} error={error} /><p style={{ fontSize: 13, color: "var(--text-secondary)" }}>Loading…</p></div>;

  return (
    <div style={cardStyle}>
      <Banner notice={notice} error={error} />
      <p style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 16 }}>Signed in as {me.email} · role: {me.role}</p>
      <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 420 }}>
        <div>
          <label style={labelStyle}>Name</label>
          <input style={inputStyle} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div>
          <label style={labelStyle}>Job title</label>
          <input style={inputStyle} value={form.job_title} onChange={(e) => setForm({ ...form, job_title: e.target.value })} />
        </div>
        <div>
          <label style={labelStyle}>Company name</label>
          <input style={inputStyle} value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} />
        </div>
        <button onClick={handleSave} disabled={saving} style={{ ...primaryBtnStyle, alignSelf: "flex-start" }}>
          {saving ? "Saving…" : "Save changes"}
        </button>
      </div>
    </div>
  );
}

const NOTIFICATION_OPTIONS = [
  ["email_alerts", "Email alerts", "General account and activity emails."],
  ["high_risk_alerts", "High-risk alerts", "Notify me when a customer crosses the high-risk threshold."],
  ["daily_summary", "Daily summary", "A daily digest of churn risk changes."],
  ["weekly_report", "Weekly report", "A weekly rollup emailed to me automatically."],
];

function NotificationsTab() {
  const [me, setMe] = useState(null);
  const [prefs, setPrefs] = useState({});
  const [saving, setSaving] = useState(false);
  const { notice, error, ok, fail } = useNotice();

  useEffect(() => {
    fetchMe()
      .then((data) => {
        setMe(data);
        setPrefs(data.preferences || {});
      })
      .catch(() => fail("Couldn't load your notification preferences."));
  }, []);

  async function toggle(key) {
    const next = { ...prefs, [key]: !prefs[key] };
    setPrefs(next);
    setSaving(true);
    try {
      await updateMe({
        name: me.name, job_title: me.job_title, company_name: me.company_name,
        avatar_url: me.avatar_url, preferences: next,
      });
      ok("Saved.");
    } catch (err) {
      setPrefs(prefs); // revert on failure
      fail(err.response?.data?.detail || "Couldn't save that preference.");
    } finally {
      setSaving(false);
    }
  }

  if (!me) return <div style={cardStyle}><Banner notice={notice} error={error} /><p style={{ fontSize: 13, color: "var(--text-secondary)" }}>Loading…</p></div>;

  return (
    <div style={cardStyle}>
      <Banner notice={notice} error={error} />
      <div style={{ display: "flex", flexDirection: "column", gap: 14, maxWidth: 480 }}>
        {NOTIFICATION_OPTIONS.map(([key, label, desc]) => (
          <label key={key} style={{ display: "flex", gap: 12, alignItems: "flex-start", cursor: "pointer" }}>
            <input type="checkbox" checked={!!prefs[key]} disabled={saving} onChange={() => toggle(key)} style={{ marginTop: 3 }} />
            <span>
              <span style={{ fontSize: 13, fontWeight: 500, display: "block" }}>{label}</span>
              <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{desc}</span>
            </span>
          </label>
        ))}
      </div>
      <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 16 }}>
        These control what you'd receive — actual delivery depends on SMTP being configured (see Integrations tab).
      </p>
    </div>
  );
}

function AIModelTab({ isAdmin }) {
  const [settings, setSettings] = useState(null);
  const [threshold, setThreshold] = useState(70);
  const [saving, setSaving] = useState(false);
  const { notice, error, ok, fail } = useNotice();

  useEffect(() => {
    fetchAppSettings()
      .then((data) => {
        setSettings(data);
        setThreshold(Math.round(data.high_risk_threshold * 100));
      })
      .catch(() => fail("Couldn't load AI model settings."));
  }, []);

  async function handleSave() {
    setSaving(true);
    try {
      const data = await updateAppSettings(threshold / 100);
      setRiskThresholds(data.high_risk_threshold);
      ok("Saved — takes effect immediately across the dashboard.");
      setSettings((prev) => ({ ...prev, high_risk_threshold: data.high_risk_threshold }));
    } catch (err) {
      fail(err.response?.data?.detail || "Couldn't save this setting.");
    } finally {
      setSaving(false);
    }
  }

  if (!settings) return <div style={cardStyle}><Banner notice={notice} error={error} /><p style={{ fontSize: 13, color: "var(--text-secondary)" }}>Loading…</p></div>;

  return (
    <div style={cardStyle}>
      <Banner notice={notice} error={error} />
      <div style={{ maxWidth: 420 }}>
        <label style={labelStyle}>High-risk threshold ({threshold}%)</label>
        <input
          type="range" min={10} max={95} value={threshold} disabled={!isAdmin}
          onChange={(e) => setThreshold(Number(e.target.value))}
          style={{ width: "100%" }}
        />
        <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 6 }}>
          Customers scoring above this are flagged "high risk" on the dashboard and are who
          "Send high-risk alert" targets. Default is {Math.round(settings.default_high_risk_threshold * 100)}%.
        </p>
        {isAdmin ? (
          <button onClick={handleSave} disabled={saving} style={{ ...primaryBtnStyle, marginTop: 12 }}>
            {saving ? "Saving…" : "Save"}
          </button>
        ) : (
          <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 12 }}>Only admins can change this.</p>
        )}
        <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 16 }}>
          Scoring runs every {settings.scoring_interval_seconds}s (set at server start — not editable here).
        </p>
      </div>
    </div>
  );
}

function SecurityTab() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const { notice, error, ok, fail } = useNotice();

  async function handleSubmit(e) {
    e.preventDefault();
    if (newPassword.length < 8) {
      fail("New password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      fail("New password and confirmation don't match.");
      return;
    }
    setSaving(true);
    try {
      await changePassword(currentPassword, newPassword);
      ok("Password changed.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      fail(err.response?.data?.detail || "Couldn't change your password.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={cardStyle}>
      <Banner notice={notice} error={error} />
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 360 }}>
        <div>
          <label style={labelStyle}>Current password</label>
          <input type="password" style={inputStyle} value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>New password</label>
          <input type="password" style={inputStyle} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
        </div>
        <div>
          <label style={labelStyle}>Confirm new password</label>
          <input type="password" style={inputStyle} value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
        </div>
        <button type="submit" disabled={saving} style={{ ...primaryBtnStyle, alignSelf: "flex-start" }}>
          {saving ? "Changing…" : "Change password"}
        </button>
      </form>
    </div>
  );
}

function money(cents) {
  if (!cents) return "Contact sales";
  return `$${(cents / 100).toLocaleString()}/mo`;
}

function UsageBar({ label, used, max }) {
  const pct = max ? Math.min(100, Math.round((used / max) * 100)) : 0;
  const near = pct >= 90;
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>
        <span>{label}</span>
        <span className="mono">{used} / {max}</span>
      </div>
      <div style={{ height: 8, borderRadius: "var(--radius-sm)", background: "var(--bg-2)", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: near ? "var(--risk-high)" : "var(--accent)" }} />
      </div>
    </div>
  );
}

function BillingTab({ isAdmin }) {
  const [sub, setSub] = useState(null);
  const [plans, setPlans] = useState([]);
  const [switching, setSwitching] = useState(false);
  const { notice, error, ok, fail } = useNotice();

  useEffect(() => {
    load();
  }, []);

  function load() {
    Promise.all([fetchSubscription(), fetchPlans()])
      .then(([subData, planList]) => {
        setSub(subData);
        setPlans(planList);
      })
      .catch(() => fail("Couldn't load billing information."));
  }

  async function handleSwitch(planId) {
    setSwitching(true);
    try {
      await updateSubscription(planId);
      ok("Plan updated.");
      load();
    } catch (err) {
      fail(err.response?.data?.detail || "Couldn't switch plans.");
    } finally {
      setSwitching(false);
    }
  }

  if (!sub) return <div style={cardStyle}><Banner notice={notice} error={error} /><p style={{ fontSize: 13, color: "var(--text-secondary)" }}>Loading…</p></div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={cardStyle}>
        <Banner notice={notice} error={error} />
        <p style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 16 }}>
          One subscription covers this whole deployment — plans aren't per-person, they're shared account limits.
          There's no live payment processor connected yet; switching plans here only changes which limits apply.
        </p>
        <div style={{ maxWidth: 420 }}>
          <p style={{ fontSize: 14, fontWeight: 600, marginBottom: 2 }}>{sub.plan_name}</p>
          <p style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 16 }}>
            {money(sub.price_cents_monthly)} · renews {sub.current_period_end ? new Date(sub.current_period_end).toLocaleDateString() : "—"}
          </p>
          <UsageBar label="Team seats" used={sub.seats_used} max={sub.max_seats} />
          <UsageBar label="Tracked customers" used={sub.tracked_customers} max={sub.max_tracked_customers} />
          <UsageBar label="AI emails this period" used={sub.ai_emails_used_this_period} max={sub.ai_email_quota_monthly} />
        </div>
      </div>

      <div style={cardStyle}>
        <h3 style={{ fontSize: 14, marginBottom: 12, color: "var(--text-secondary)" }}>Available plans</h3>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {plans.map((p) => (
            <div
              key={p.id}
              style={{
                flex: "1 1 180px", border: `1px solid ${p.id === sub.plan_id ? "var(--accent)" : "var(--border)"}`,
                borderRadius: "var(--radius-sm)", padding: 14, background: "var(--bg-2)",
              }}
            >
              <p style={{ fontSize: 13, fontWeight: 600 }}>{p.name}</p>
              <p style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>{money(p.price_cents_monthly)}</p>
              <p style={{ fontSize: 11, color: "var(--text-secondary)" }}>{p.max_seats.toLocaleString()} seats</p>
              <p style={{ fontSize: 11, color: "var(--text-secondary)" }}>{p.max_tracked_customers.toLocaleString()} customers</p>
              <p style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 10 }}>{p.ai_email_quota_monthly.toLocaleString()} AI emails/mo</p>
              {p.id === sub.plan_id ? (
                <p style={{ fontSize: 11, color: "var(--accent)", fontWeight: 600 }}>Current plan</p>
              ) : isAdmin ? (
                <button onClick={() => handleSwitch(p.id)} disabled={switching} style={{ ...btnStyle, fontSize: 11, padding: "5px 10px" }}>
                  Switch
                </button>
              ) : (
                <p style={{ fontSize: 11, color: "var(--text-muted)" }}>Admin only</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function IntegrationsTab() {
  const [status, setStatus] = useState(null);
  const { notice, error, fail } = useNotice();

  useEffect(() => {
    fetchIntegrationsStatus().then(setStatus).catch(() => fail("Couldn't load integration status."));
  }, []);

  const rows = status
    ? [
        ["OpenAI (email generation)", status.openai, "OPENAI_API_KEY"],
        ["Slack (high-risk alerts)", status.slack, "SLACK_WEBHOOK_URL"],
        ["SMTP (email sending)", status.smtp, "SMTP_HOST / SMTP_USER / SMTP_PASSWORD"],
      ]
    : [];

  return (
    <div style={cardStyle}>
      <Banner notice={notice} error={error} />
      <p style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 16 }}>
        Status only — credentials are configured server-side via environment variables and are never exposed here.
      </p>
      {!status ? (
        <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>Loading…</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 480 }}>
          {rows.map(([label, connected, envVar]) => (
            <div key={label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderTop: "1px solid var(--border)" }}>
              <div>
                <p style={{ fontSize: 13 }}>{label}</p>
                <p style={{ fontSize: 11, color: "var(--text-muted)" }}>{envVar}</p>
              </div>
              <span style={{ fontSize: 12, fontWeight: 600, color: connected ? "var(--accent)" : "var(--text-muted)" }}>
                {connected ? "Connected" : "Not configured"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
