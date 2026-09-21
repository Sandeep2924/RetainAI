import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const client = axios.create({ baseURL: API_URL });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("retainai_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function setToken(token) {
  localStorage.setItem("retainai_token", token);
}

export function clearToken() {
  localStorage.removeItem("retainai_token");
}

export function getToken() {
  return localStorage.getItem("retainai_token");
}

export async function login(email, password) {
  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);
  const { data } = await client.post("/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}

export async function signup(email, password) {
  const { data } = await client.post("/signup", { email, password });
  return data;
}

export async function fetchMe() {
  const { data } = await client.get("/me");
  return data;
}

export async function updateMe(payload) {
  const { data } = await client.put("/me", payload);
  return data;
}

export async function changePassword(currentPassword, newPassword) {
  const { data } = await client.post("/me/change_password", {
    current_password: currentPassword, new_password: newPassword,
  });
  return data;
}

export async function fetchAppSettings() {
  const { data } = await client.get("/settings/app");
  return data;
}

export async function updateAppSettings(highRiskThreshold) {
  const { data } = await client.put("/settings/app", { high_risk_threshold: highRiskThreshold });
  return data;
}

export async function fetchIntegrationsStatus() {
  const { data } = await client.get("/integrations/status");
  return data;
}

export async function fetchSummary() {
  const { data } = await client.get("/customers/summary");
  return data;
}

export async function fetchCustomers(highRiskOnly = false) {
  const { data } = await client.get("/customers", {
    params: { high_risk_only: highRiskOnly },
  });
  return data.customers;
}

export async function fetchCustomerDetail(customerId) {
  const { data } = await client.get(`/customers/${customerId}`);
  return data;
}

export async function fetchCustomerNotes(customerId) {
  const { data } = await client.get(`/customers/${customerId}/notes`);
  return data.notes;
}

export async function addCustomerNote(customerId, text) {
  const { data } = await client.post(`/customers/${customerId}/notes`, { text });
  return data;
}

export async function assignOwner(customerId, ownerEmail) {
  const { data } = await client.put(`/customers/${customerId}/owner`, { owner_email: ownerEmail });
  return data;
}

export async function fetchRiskTrend(customerId, days = 14) {
  const { data } = await client.get(`/customers/${customerId}/risk_trend`, { params: { days } });
  return data.trend;
}

export async function runHighRiskAlert(threshold = 0.75) {
  const { data } = await client.post("/alerts/high_risk/run", null, { params: { threshold } });
  return data;
}

export async function downloadCustomersCsv(highRiskOnly = false) {
  const response = await client.get("/customers/export", {
    params: { high_risk_only: highRiskOnly },
    responseType: "blob",
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", highRiskOnly ? "high_risk_customers.csv" : "all_customers.csv");
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function fetchCustomerHistory(customerId) {
  const { data } = await client.get(`/customer_history/${customerId}`);
  return data;
}

export async function validatePredictionCsv(file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post("/predictions/validate", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function uploadPredictionCsv(file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post("/predictions/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function predictChurn(payload) {
  const { data } = await client.post("/predict", payload);
  return data;
}

export async function fetchRecentEvents() {
  const { data } = await client.get("/recent_events");
  return data.events;
}

export async function fetchTeam() {
  const { data } = await client.get("/admin/users");
  return data.users;
}

export async function updateUserRole(email, role) {
  const { data } = await client.put(`/admin/users/${encodeURIComponent(email)}/role`, { role });
  return data;
}

export async function generateReport(reportType, dateRangeStart, dateRangeEnd) {
  const { data } = await client.post("/reports/generate", {
    report_type: reportType,
    date_range_start: dateRangeStart || undefined,
    date_range_end: dateRangeEnd || undefined,
  });
  return data;
}

export async function fetchReports() {
  const { data } = await client.get("/reports");
  return data.reports;
}

export async function fetchReport(id) {
  const { data } = await client.get(`/reports/${id}`);
  return data;
}

export async function deleteReport(id) {
  await client.delete(`/reports/${id}`);
}

export async function downloadReportCsv(id, reportType) {
  const response = await client.get(`/reports/${id}/export`, { responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", `${reportType}_${id}.csv`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function generateEmailDraft(customerId, tone, length) {
  const { data } = await client.post("/emails/generate", { customer_id: customerId, tone, length });
  return data;
}

export async function generateEmailBatch(minRisk, maxRisk, tone, length, maxCustomers = 7) {
  const { data } = await client.post("/emails/generate_batch", {
    min_risk: minRisk, max_risk: maxRisk, tone, length, max_customers: maxCustomers,
  });
  return data;
}

export async function fetchPlans() {
  const { data } = await client.get("/billing/plans");
  return data.plans;
}

export async function fetchSubscription() {
  const { data } = await client.get("/billing/subscription");
  return data;
}

export async function updateSubscription(planId) {
  const { data } = await client.put("/billing/subscription", { plan_id: planId });
  return data;
}

export async function fetchEmailDrafts(customerId) {
  const { data } = await client.get("/emails/drafts", { params: customerId ? { customer_id: customerId } : {} });
  return data.drafts;
}

export async function createEmailDraft(payload) {
  const { data } = await client.post("/emails/drafts", payload);
  return data;
}

export async function updateEmailDraft(id, payload) {
  const { data } = await client.put(`/emails/drafts/${id}`, payload);
  return data;
}

export async function deleteEmailDraft(id) {
  await client.delete(`/emails/drafts/${id}`);
}

export async function sendTestEmailDraft(id) {
  const { data } = await client.post(`/emails/drafts/${id}/send_test`);
  return data;
}

export async function sendEmailDraft(id) {
  const { data } = await client.post(`/emails/drafts/${id}/send`);
  return data;
}

export default client;
