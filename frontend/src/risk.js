// Mirrors the backend's admin-configurable high-risk threshold (see
// GET /settings/app) so badges, meters, and every chart agree with the KPI
// count instead of each hardcoding their own cutoff. App.jsx calls
// setRiskThresholds() once at load, after fetching /settings/app.
let HIGH_RISK_THRESHOLD = 0.7;
let MEDIUM_RISK_THRESHOLD = 0.35;

export function setRiskThresholds(highRiskThreshold) {
  HIGH_RISK_THRESHOLD = highRiskThreshold;
  MEDIUM_RISK_THRESHOLD = highRiskThreshold / 2;
}

export function riskLevel(score) {
  if (score >= HIGH_RISK_THRESHOLD) return "high";
  if (score >= MEDIUM_RISK_THRESHOLD) return "mid";
  return "low";
}

export const riskColor = {
  high: "var(--risk-high)",
  mid: "var(--risk-mid)",
  low: "var(--risk-low)",
};

export const riskBg = {
  high: "var(--risk-high-bg)",
  mid: "var(--risk-mid-bg)",
  low: "var(--risk-low-bg)",
};

export const riskLabel = {
  high: "High risk",
  mid: "Watch",
  low: "Healthy",
};

export function formatPercent(score) {
  return `${Math.round(score * 100)}%`;
}

export function driverLabel(key) {
  const map = {
    Account_Age_Days: "Account age",
    Login_Frequency: "Login frequency",
    Daily_Usage_Mins: "Daily usage",
    Last_Support_Ticket: "Support ticket urgency",
  };
  return map[key] || key;
}
