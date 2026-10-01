import { useEffect, useState } from "react";
import { fetchTeam, updateUserRole, approveUser, rejectUser } from "../api";

export default function Team({ onBack, currentUserEmail }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyEmail, setBusyEmail] = useState(null);

  useEffect(() => {
    load();
  }, []);

  function load() {
    setLoading(true);
    setError("");
    fetchTeam()
      .then(setUsers)
      .catch(() => setError("Couldn't load team members. Is the backend running?"))
      .finally(() => setLoading(false));
  }

  async function handleApprove(u) {
    setBusyEmail(u.email);
    setError("");
    try {
      await approveUser(u.email);
      setUsers((prev) =>
        prev.map((item) => (item.email === u.email ? { ...item, is_approved: true } : item))
      );
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't approve user.");
    } finally {
      setBusyEmail(null);
    }
  }

  async function handleReject(u) {
    if (!window.confirm(`Are you sure you want to reject and remove ${u.email}?`)) {
      return;
    }
    setBusyEmail(u.email);
    setError("");
    try {
      await rejectUser(u.email);
      setUsers((prev) => prev.filter((item) => item.email !== u.email));
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't reject user.");
    } finally {
      setBusyEmail(null);
    }
  }

  async function handleRoleToggle(user) {
    const nextRole = user.role === "admin" ? "member" : "admin";
    const isSelf = user.email.toLowerCase() === (currentUserEmail || "").toLowerCase();
    if (isSelf && nextRole !== "admin") {
      setError("You can't demote yourself.");
      return;
    }
    setBusyEmail(user.email);
    setError("");
    try {
      await updateUserRole(user.email, nextRole);
      setUsers((prev) =>
        prev.map((u) => (u.email === user.email ? { ...u, role: nextRole } : u))
      );
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't update that user's role.");
    } finally {
      setBusyEmail(null);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ fontSize: 22, marginBottom: 4 }}>Team</h2>
          <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            {loading ? "Loading…" : `${users.length} teammate${users.length === 1 ? "" : "s"}`}
          </p>
        </div>
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

      <div
        style={{
          background: "var(--bg-1)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-md)",
          padding: "16px 14px",
          overflow: "hidden",
        }}
      >
        {error && (
          <p style={{ color: "var(--risk-high)", fontSize: 13, marginBottom: 14 }}>{error}</p>
        )}

        {loading ? (
          <p style={{ color: "var(--text-secondary)" }}>Loading team…</p>
        ) : users.length === 0 ? (
          <p style={{ color: "var(--text-secondary)" }}>No teammates yet.</p>
        ) : (
          <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch" }}>
            <table style={{ width: "100%", minWidth: 460, borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ textAlign: "left", color: "var(--text-muted)", fontSize: 12 }}>
                <th style={{ padding: "8px 10px", fontWeight: 500 }}>Name</th>
                <th style={{ padding: "8px 10px", fontWeight: 500 }}>Email</th>
                <th style={{ padding: "8px 10px", fontWeight: 500 }}>Role</th>
                <th style={{ padding: "8px 10px", fontWeight: 500 }}>Status</th>
                <th style={{ padding: "8px 10px", fontWeight: 500, textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isSelf = u.email.toLowerCase() === (currentUserEmail || "").toLowerCase();
                const isApproved = u.is_approved !== false;
                const isVerified = u.is_verified !== false;
                return (
                  <tr key={u.email} style={{ borderTop: "1px solid var(--border)" }}>
                    <td style={{ padding: "10px" }}>{u.name || "—"}</td>
                    <td style={{ padding: "10px", wordBreak: "break-all" }}>
                      {u.email}
                      {isSelf && (
                        <span style={{ color: "var(--text-muted)", fontSize: 12 }}> (you)</span>
                      )}
                    </td>
                    <td style={{ padding: "10px" }}>
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 600,
                          textTransform: "uppercase",
                          letterSpacing: "0.03em",
                          color: u.role === "admin" ? "var(--accent)" : "var(--text-muted)",
                        }}
                      >
                        {u.role}
                      </span>
                    </td>
                    <td style={{ padding: "10px" }}>
                      {!isVerified ? (
                        <span style={{ fontSize: 11, padding: "2px 8px", background: "rgba(100, 116, 139, 0.2)", color: "#94a3b8", borderRadius: 10 }}>
                          Unverified
                        </span>
                      ) : !isApproved ? (
                        <span style={{ fontSize: 11, padding: "2px 8px", background: "rgba(245, 158, 11, 0.15)", color: "#f59e0b", borderRadius: 10, fontWeight: 600 }}>
                          Pending Approval
                        </span>
                      ) : (
                        <span style={{ fontSize: 11, padding: "2px 8px", background: "rgba(16, 185, 129, 0.15)", color: "#34d399", borderRadius: 10, fontWeight: 600 }}>
                          Active
                        </span>
                      )}
                    </td>
                    <td style={{ padding: "10px", textAlign: "right" }}>
                      <div style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
                        {!isApproved && (
                          <>
                            <button
                              onClick={() => handleApprove(u)}
                              disabled={busyEmail === u.email}
                              style={{
                                background: "#059669",
                                border: "none",
                                borderRadius: "var(--radius-sm)",
                                color: "#ffffff",
                                fontSize: 12,
                                fontWeight: 600,
                                padding: "5px 10px",
                                cursor: "pointer",
                                opacity: busyEmail === u.email ? 0.6 : 1,
                              }}
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => handleReject(u)}
                              disabled={busyEmail === u.email}
                              style={{
                                background: "rgba(239, 68, 68, 0.15)",
                                border: "1px solid rgba(239, 68, 68, 0.3)",
                                borderRadius: "var(--radius-sm)",
                                color: "#f87171",
                                fontSize: 12,
                                padding: "5px 10px",
                                cursor: "pointer",
                                opacity: busyEmail === u.email ? 0.6 : 1,
                              }}
                            >
                              Reject
                            </button>
                          </>
                        )}
                        <button
                          onClick={() => handleRoleToggle(u)}
                          disabled={busyEmail === u.email || (isSelf && u.role === "admin")}
                          title={isSelf && u.role === "admin" ? "You can't demote yourself" : ""}
                          style={{
                            background: "none",
                            border: "1px solid var(--border)",
                            borderRadius: "var(--radius-sm)",
                            color: "var(--text-primary)",
                            fontSize: 12,
                            padding: "5px 10px",
                            cursor: "pointer",
                            opacity: busyEmail === u.email ? 0.6 : 1,
                          }}
                        >
                          {busyEmail === u.email
                            ? "Updating…"
                            : u.role === "admin"
                            ? "Make member"
                            : "Make admin"}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        )}
      </div>
    </div>
  );
}
