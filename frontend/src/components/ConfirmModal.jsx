import { useEffect } from "react";
import { AlertTriangle, X } from "lucide-react";

export default function ConfirmModal({
  isOpen,
  title = "Confirm Action",
  message = "Are you sure you want to proceed?",
  confirmText = "Confirm",
  cancelText = "Cancel",
  variant = "danger", // "danger" | "warning" | "primary"
  busy = false,
  onConfirm,
  onCancel,
}) {
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === "Escape" && isOpen && !busy) {
        onCancel();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, busy, onCancel]);

  if (!isOpen) return null;

  const isDanger = variant === "danger";

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "16px",
        backgroundColor: "rgba(2, 6, 23, 0.75)",
        backdropFilter: "blur(4px)",
        WebkitBackdropFilter: "blur(4px)",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !busy) onCancel();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        style={{
          width: "100%",
          maxWidth: "460px",
          backgroundColor: "#0f172a",
          border: `1px solid ${isDanger ? "rgba(239, 68, 68, 0.35)" : "rgba(6, 182, 212, 0.35)"}`,
          borderRadius: "16px",
          padding: "24px",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.6)",
          color: "#f8fafc",
          animation: "modalFadeIn 0.18s cubic-bezier(0.16, 1, 0.3, 1)",
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: "10px",
              backgroundColor: isDanger ? "rgba(239, 68, 68, 0.15)" : "rgba(6, 182, 212, 0.15)",
              color: isDanger ? "#ef4444" : "#06b6d4",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <AlertTriangle style={{ width: 22, height: 22 }} />
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <h3 style={{ margin: "0 0 6px 0", fontSize: "17px", fontWeight: 600, color: "#f8fafc" }}>
              {title}
            </h3>
            <p style={{ margin: 0, fontSize: "13px", lineHeight: "1.5", color: "#94a3b8" }}>
              {message}
            </p>
          </div>

          <button
            onClick={onCancel}
            disabled={busy}
            style={{
              background: "none",
              border: "none",
              color: "#64748b",
              cursor: "pointer",
              padding: 4,
              borderRadius: 6,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
            title="Close"
          >
            <X style={{ width: 18, height: 18 }} />
          </button>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "10px",
            marginTop: "24px",
          }}
        >
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            style={{
              background: "transparent",
              border: "1px solid #334155",
              color: "#cbd5e1",
              borderRadius: "8px",
              padding: "8px 16px",
              fontSize: "13px",
              fontWeight: 500,
              cursor: "pointer",
              opacity: busy ? 0.6 : 1,
            }}
          >
            {cancelText}
          </button>

          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            style={{
              background: isDanger ? "#dc2626" : "#0891b2",
              border: "none",
              color: "#ffffff",
              borderRadius: "8px",
              padding: "8px 18px",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
              boxShadow: isDanger
                ? "0 4px 12px rgba(220, 38, 38, 0.35)"
                : "0 4px 12px rgba(8, 145, 178, 0.35)",
              opacity: busy ? 0.6 : 1,
            }}
          >
            {busy ? "Processing…" : confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
