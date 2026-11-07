import { useState } from "react";
import { HelpCircle, X, Mail, ShieldCheck, ExternalLink, ChevronRight, MessageSquare } from "lucide-react";
import CopyButton from "./CopyButton";

export default function SupportWidget({ currentUserEmail }) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedTopic, setSelectedTopic] = useState(null);

  const topics = [
    {
      id: "scoring",
      title: "How Churn Scoring Works",
      detail:
        "RetainAI runs automated scoring passes using a Random Forest classifier. It processes login frequency (14-day window), daily usage minutes (7-day window), and urgent support tickets (30-day window) to compute real-time churn risk percentages.",
    },
    {
      id: "shap",
      title: "Understanding SHAP Drivers",
      detail:
        "SHAP (SHapley Additive exPlanations) breaks down the exact positive and negative factors contributing to each customer's risk score, so Customer Success teams know what is hurting health without guessing.",
    },
    {
      id: "emails",
      title: "AI Retention Campaigns",
      detail:
        "Go to the 'Retention Emails' tab, pick any customer, configure the desired tone (professional, friendly, empathetic, urgent) and length, then click 'Generate with AI' to draft personalized retention messages.",
    },
    {
      id: "approval",
      title: "Registration & Admin Approvals",
      detail:
        "All new accounts require 2-step email OTP verification followed by admin approval before access is unlocked. Admins can approve or reject pending requests directly from the 'Team' page.",
    },
  ];

  return (
    <>
      {/* Floating Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        title="RetainAI Help & Support"
        aria-label="Help & Support"
        style={{
          position: "fixed",
          bottom: "24px",
          right: "24px",
          zIndex: 40,
          display: "flex",
          alignItems: "center",
          gap: "8px",
          backgroundColor: isOpen ? "#0891b2" : "#0f172a",
          border: "1px solid rgba(6, 182, 212, 0.45)",
          color: "#f8fafc",
          padding: "10px 16px",
          borderRadius: "8px",
          cursor: "pointer",
          boxShadow: "0 8px 24px rgba(0, 0, 0, 0.5)",
          transition: "all 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
        }}
        onMouseEnter={(e) => {
          if (!isOpen) e.currentTarget.style.backgroundColor = "#1e293b";
          e.currentTarget.style.transform = "translateY(-2px)";
        }}
        onMouseLeave={(e) => {
          if (!isOpen) e.currentTarget.style.backgroundColor = "#0f172a";
          e.currentTarget.style.transform = "translateY(0)";
        }}
      >
        <span
          style={{
            display: "inline-block",
            width: 8,
            height: 8,
            borderRadius: "50%",
            backgroundColor: "#10b981",
            boxShadow: "0 0 8px #10b981",
          }}
        />
        {isOpen ? (
          <X style={{ width: 18, height: 18 }} />
        ) : (
          <HelpCircle style={{ width: 18, height: 18, color: "#38bdf8" }} />
        )}
        <span style={{ fontSize: "13px", fontWeight: 600 }}>Help</span>
      </button>

      {/* Floating Support Modal / Drawer */}
      {isOpen && (
        <div
          role="dialog"
          aria-label="RetainAI Support"
          style={{
            position: "fixed",
            bottom: "80px",
            right: "24px",
            width: "380px",
            maxWidth: "calc(100vw - 36px)",
            maxHeight: "540px",
            backgroundColor: "#0f172a",
            border: "1px solid #334155",
            borderRadius: "16px",
            boxShadow: "0 24px 48px rgba(0, 0, 0, 0.75)",
            zIndex: 45,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            color: "#f8fafc",
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: "16px 20px",
              background: "linear-gradient(135deg, rgba(6, 182, 212, 0.15) 0%, rgba(15, 23, 42, 0.9) 100%)",
              borderBottom: "1px solid #1e293b",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: "8px",
                  background: "rgba(6, 182, 212, 0.2)",
                  color: "#38bdf8",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <ShieldCheck style={{ width: 18, height: 18 }} />
              </div>
              <div>
                <h4 style={{ margin: 0, fontSize: "14px", fontWeight: 600 }}>RetainAI Support</h4>
                <p style={{ margin: 0, fontSize: "11px", color: "#34d399", display: "flex", alignItems: "center", gap: 4 }}>
                  <span>●</span> All Systems Operational
                </p>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", padding: 4 }}
              title="Close"
            >
              <X style={{ width: 16, height: 16 }} />
            </button>
          </div>

          {/* Scrollable Content */}
          <div style={{ padding: "16px 20px", overflowY: "auto", display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <span style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.05em", color: "#64748b", fontWeight: 700 }}>
                Quick Assistance
              </span>
              <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
                {topics.map((t) => {
                  const isExpanded = selectedTopic === t.id;
                  return (
                    <div
                      key={t.id}
                      style={{
                        borderRadius: "8px",
                        border: "1px solid #1e293b",
                        backgroundColor: isExpanded ? "rgba(30, 41, 59, 0.6)" : "rgba(15, 23, 42, 0.6)",
                        overflow: "hidden",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <button
                        type="button"
                        onClick={() => setSelectedTopic(isExpanded ? null : t.id)}
                        style={{
                          width: "100%",
                          padding: "10px 12px",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          background: "none",
                          border: "none",
                          color: isExpanded ? "#38bdf8" : "#e2e8f0",
                          fontSize: "12px",
                          fontWeight: 500,
                          textAlign: "left",
                          cursor: "pointer",
                        }}
                      >
                        <span>{t.title}</span>
                        <ChevronRight
                          style={{
                            width: 14,
                            height: 14,
                            transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
                            transition: "transform 0.15s ease",
                            color: "#64748b",
                          }}
                        />
                      </button>
                      {isExpanded && (
                        <div style={{ padding: "0 12px 10px 12px", fontSize: "12px", color: "#94a3b8", lineHeight: 1.5 }}>
                          {t.detail}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Direct Admin Contact Card */}
            <div
              style={{
                borderRadius: "10px",
                backgroundColor: "rgba(30, 41, 59, 0.4)",
                border: "1px solid #334155",
                padding: "14px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontSize: "12px", fontWeight: 600, color: "#f8fafc" }}>Administrator Contact</span>
                <CopyButton text="sandeepkumar9837146@gmail.com" label="Copy" size={12} />
              </div>
              <p style={{ margin: "0 0 10px 0", fontSize: "12px", color: "#94a3b8", wordBreak: "break-all" }}>
                sandeepkumar9837146@gmail.com
              </p>
              <a
                href="mailto:sandeepkumar9837146@gmail.com?subject=RetainAI%20Support%20Inquiry"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 6,
                  width: "100%",
                  padding: "9px 12px",
                  borderRadius: "8px",
                  backgroundColor: "#0891b2",
                  color: "#ffffff",
                  fontSize: "12px",
                  fontWeight: 600,
                  textDecoration: "none",
                  textAlign: "center",
                }}
              >
                <Mail style={{ width: 14, height: 14 }} />
                <span>Send Support Email</span>
              </a>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
