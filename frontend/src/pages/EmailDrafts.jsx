import { useEffect, useMemo, useState } from "react";
import {
  fetchCustomers,
  fetchEmailDrafts,
  generateEmailDraft,
  generateEmailBatch,
  createEmailDraft,
  updateEmailDraft,
  deleteEmailDraft,
  sendTestEmailDraft,
  sendEmailDraft,
} from "../api";
import { ChevronDown, Mail, Send, Loader2, Save, Trash2, Edit3, Settings } from 'lucide-react';

const TONES = ["professional", "friendly", "empathetic", "urgent"];
const LENGTHS = ["short", "medium", "long"];

export default function EmailDrafts({ onBack, initialCustomerId }) {
  const [customers, setCustomers] = useState([]);
  const [customerId, setCustomerId] = useState(initialCustomerId || "");
  const [tone, setTone] = useState("professional");
  const [length, setLength] = useState("medium");

  const [activeDraftId, setActiveDraftId] = useState(null);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [status, setStatus] = useState("draft");

  const [drafts, setDrafts] = useState([]);
  const [loadingDrafts, setLoadingDrafts] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendingTest, setSendingTest] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    fetchCustomers(false)
      .then(setCustomers)
      .catch(() => setError("Couldn't load customers. Is the backend running?"));
  }, []);

  useEffect(() => {
    loadDrafts();
  }, [customerId]);

  function loadDrafts() {
    setLoadingDrafts(true);
    fetchEmailDrafts(customerId || undefined)
      .then(setDrafts)
      .catch(() => setError("Couldn't load drafts."))
      .finally(() => setLoadingDrafts(false));
  }

  function resetComposer() {
    setActiveDraftId(null);
    setSubject("");
    setBody("");
    setStatus("draft");
    setNotice("");
  }

  function loadDraftIntoComposer(d) {
    setActiveDraftId(d.id);
    setCustomerId(d.customer_id);
    setSubject(d.subject);
    setBody(d.body);
    setTone(d.tone);
    setLength(d.length);
    setStatus(d.status);
    setNotice("");
    setError("");
  }

  async function handleGenerate() {
    if (!customerId) {
      setError("Pick a customer first.");
      return;
    }
    setGenerating(true);
    setError("");
    setNotice("");
    try {
      const result = await generateEmailDraft(customerId, tone, length);
      setSubject(result.subject);
      setBody(result.body);
      setStatus("draft");
      setNotice(
        result.source === "openai"
          ? "Generated with AI."
          : "AI generation unavailable right now — used a fallback template instead."
      );
    } catch {
      setError("Couldn't generate a draft. Is OPENAI_API_KEY configured on the backend?");
    } finally {
      setGenerating(false);
    }
  }

  async function handleSave() {
    if (!customerId || !subject.trim() || !body.trim()) {
      setError("A customer, subject, and body are all required before saving.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (activeDraftId) {
        const updated = await updateEmailDraft(activeDraftId, { subject, body, tone, length });
        setDrafts((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
      } else {
        const created = await createEmailDraft({ customer_id: customerId, subject, body, tone, length });
        setActiveDraftId(created.id);
        setDrafts((prev) => [created, ...prev]);
      }
      setNotice("Saved.");
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't save this draft.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSendTest() {
    if (!activeDraftId) {
      setError("Save the draft before sending a test.");
      return;
    }
    setSendingTest(true);
    setError("");
    setNotice("");
    try {
      const result = await sendTestEmailDraft(activeDraftId);
      setNotice(`Test email sent to ${result.to}.`);
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't send a test email.");
    } finally {
      setSendingTest(false);
    }
  }

  async function handleSend() {
    if (!activeDraftId) {
      setError("Save the draft before sending it.");
      return;
    }
    setSending(true);
    setError("");
    setNotice("");
    try {
      const result = await sendEmailDraft(activeDraftId);
      setNotice(`Sent to ${result.to}.`);
      setStatus("sent");
      setDrafts((prev) => prev.map((d) => (d.id === activeDraftId ? { ...d, status: "sent" } : d)));
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't send this email.");
    } finally {
      setSending(false);
    }
  }

  async function handleDelete(id) {
    try {
      await deleteEmailDraft(id);
      setDrafts((prev) => prev.filter((d) => d.id !== id));
      if (activeDraftId === id) resetComposer();
    } catch {
      setError("Couldn't delete that draft.");
    }
  }

  const selectedCustomerName = useMemo(
    () => customers.find((c) => c.customer_id === customerId)?.name,
    [customers, customerId]
  );

  const isSent = status === "sent";

  return (
    <div className="text-slate-200 font-sans selection:bg-cyan-900 pb-10 max-w-7xl mx-auto space-y-6">
      <header className="flex flex-col md:flex-row items-start md:items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <div className="bg-cyan-500/10 p-2 rounded-lg border border-cyan-500/20">
            <Mail className="w-8 h-8 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight">Email Drafts</h1>
            <p className="text-slate-400 text-sm mt-1">AI-assisted retention emails, saved and sent per customer.</p>
          </div>
        </div>
        <button
          onClick={onBack}
          className="mt-4 md:mt-0 flex items-center gap-2 text-slate-400 hover:text-white transition-colors px-4 py-2 border border-slate-700 rounded-lg hover:bg-slate-800/50"
        >
          Back to Dashboard
        </button>
      </header>

      {error && <div className="bg-rose-500/10 border border-rose-500/30 text-rose-400 px-4 py-3 rounded-lg text-sm">{error}</div>}
      {notice && !error && <div className="bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 px-4 py-3 rounded-lg text-sm">{notice}</div>}

      <BatchGeneratePanel onGenerated={loadDrafts} />

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Composer */}
        <div className="flex-[2] bg-slate-800/50 backdrop-blur-sm border border-slate-700 p-6 rounded-2xl flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={customerId}
              onChange={(e) => {
                resetComposer();
                setCustomerId(e.target.value);
              }}
              disabled={isSent}
              className="bg-slate-900/50 border border-slate-700 text-slate-200 text-sm rounded-lg focus:ring-cyan-500 focus:border-cyan-500 block w-full md:w-auto p-2.5 outline-none transition-all disabled:opacity-50"
            >
              <option value="">Select a customer…</option>
              {customers.map((c) => (
                <option key={c.customer_id} value={c.customer_id}>
                  {c.name} — {Math.round(c.churn_risk_score * 100)}% risk
                </option>
              ))}
            </select>
            <select
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              disabled={isSent}
              className="bg-slate-900/50 border border-slate-700 text-slate-200 text-sm rounded-lg focus:ring-cyan-500 focus:border-cyan-500 block p-2.5 outline-none transition-all disabled:opacity-50"
            >
              {TONES.map((t) => (
                <option key={t} value={t}>
                  {t[0].toUpperCase() + t.slice(1)}
                </option>
              ))}
            </select>
            <select
              value={length}
              onChange={(e) => setLength(e.target.value)}
              disabled={isSent}
              className="bg-slate-900/50 border border-slate-700 text-slate-200 text-sm rounded-lg focus:ring-cyan-500 focus:border-cyan-500 block p-2.5 outline-none transition-all disabled:opacity-50"
            >
              {LENGTHS.map((l) => (
                <option key={l} value={l}>
                  {l[0].toUpperCase() + l.slice(1)}
                </option>
              ))}
            </select>
            <button
              onClick={handleGenerate}
              disabled={generating || isSent}
              className="flex items-center gap-2 bg-cyan-600 hover:bg-cyan-500 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors border border-cyan-500 shadow-lg shadow-cyan-900/20 disabled:opacity-50 disabled:shadow-none"
            >
              {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Settings className="w-4 h-4" />}
              {generating ? "Generating…" : activeDraftId ? "Regenerate with AI" : "Generate with AI"}
            </button>
          </div>

          <input
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Subject"
            disabled={isSent}
            className="bg-slate-900/50 border border-slate-700 text-slate-200 text-sm rounded-lg focus:ring-cyan-500 focus:border-cyan-500 block w-full p-3 outline-none transition-all disabled:opacity-50"
          />
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Email body — generate with AI, or write your own."
            rows={14}
            disabled={isSent}
            className="bg-slate-900/50 border border-slate-700 text-slate-200 text-sm rounded-lg focus:ring-cyan-500 focus:border-cyan-500 block w-full p-3 outline-none transition-all resize-y min-h-[200px] leading-relaxed disabled:opacity-50"
          />

          <div className="flex flex-wrap items-center gap-3 mt-2">
            {!isSent && (
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-2 border border-slate-600 hover:bg-slate-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                <Save className="w-4 h-4" />
                {saving ? "Saving…" : activeDraftId ? "Save changes" : "Save draft"}
              </button>
            )}
            <button
              onClick={handleSendTest}
              disabled={sendingTest || !activeDraftId}
              className="flex items-center gap-2 border border-slate-600 hover:bg-slate-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
              {sendingTest ? "Sending test…" : "Send test email"}
            </button>
            {!isSent && (
              <button
                onClick={handleSend}
                disabled={sending || !activeDraftId}
                className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors border border-emerald-500 shadow-lg shadow-emerald-900/20 disabled:opacity-50 disabled:shadow-none"
              >
                <Send className="w-4 h-4" />
                {sending ? "Sending…" : "Send"}
              </button>
            )}
            {activeDraftId && (
              <button
                onClick={resetComposer}
                className="flex items-center gap-2 border border-slate-700 hover:bg-slate-800 text-slate-400 hover:text-white px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ml-auto"
              >
                <Edit3 className="w-4 h-4" />
                New draft
              </button>
            )}
          </div>
          {selectedCustomerName && (
            <p className="text-xs text-slate-500 mt-2">
              Composing for {selectedCustomerName}
              {isSent ? " — this draft has been sent and is now read-only." : ""}
            </p>
          )}
        </div>

        {/* Draft list */}
        <div className="flex-1 bg-slate-800/50 backdrop-blur-sm border border-slate-700 p-6 rounded-2xl">
          <h3 className="text-sm font-semibold text-slate-300 mb-4 uppercase tracking-wider">
            {customerId ? "Drafts for this customer" : "All drafts"}
          </h3>
          {loadingDrafts ? (
            <div className="flex items-center justify-center p-8 text-slate-400">
              <Loader2 className="w-6 h-6 animate-spin" />
            </div>
          ) : drafts.length === 0 ? (
            <div className="bg-slate-900/20 border border-slate-700/50 border-dashed rounded-xl p-8 text-center text-slate-500 text-sm">
              No drafts yet.
            </div>
          ) : (
            <div className="flex flex-col gap-3 max-h-[600px] overflow-y-auto pr-2 scrollbar-thin">
              {drafts.map((d) => (
                <div
                  key={d.id}
                  className={`border rounded-xl p-4 transition-colors relative group ${
                    d.id === activeDraftId
                      ? "border-cyan-500/50 bg-cyan-900/10"
                      : "border-slate-700 bg-slate-900/30 hover:border-slate-600 hover:bg-slate-800/50"
                  }`}
                >
                  <div
                    onClick={() => loadDraftIntoComposer(d)}
                    className="cursor-pointer"
                  >
                    <p className="text-sm font-medium text-slate-200 mb-1 truncate pr-8">{d.subject || "(no subject)"}</p>
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <span className="truncate max-w-[120px]">{d.customer_id}</span>
                      <span>·</span>
                      <span className={d.status === "sent" ? "text-emerald-400 font-medium" : "text-amber-400 font-medium"}>
                        {d.status}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(d.id)}
                    className="absolute top-4 right-4 p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-md opacity-0 group-hover:opacity-100 transition-all"
                    title="Delete draft"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function BatchGeneratePanel({ onGenerated }) {
  const [open, setOpen] = useState(false);
  const [minRisk, setMinRisk] = useState(70);
  const [maxRisk, setMaxRisk] = useState(90);
  const [tone, setTone] = useState("professional");
  const [length, setLength] = useState("medium");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function handleRun() {
    if (minRisk >= maxRisk) {
      setError("The low end of the range has to be below the high end.");
      return;
    }
    setRunning(true);
    setError("");
    setResult(null);
    try {
      const data = await generateEmailBatch(minRisk / 100, maxRisk / 100, tone, length, 7);
      setResult(data);
      onGenerated();
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't generate this batch.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 p-6 rounded-2xl">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-slate-200 hover:text-white font-medium text-sm transition-colors focus:outline-none w-full"
      >
        <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
        Generate a batch by risk range
      </button>
      
      {open && (
        <div className="mt-4 pt-4 border-t border-slate-700/50">
          <p className="text-sm text-slate-400 mb-6 max-w-3xl leading-relaxed">
            Drafts (doesn't send) one email per customer in the range, capped at 7 so each batch stays small enough
            to actually review. Customers who already have an unsent draft are skipped, so it's safe to re-run.
          </p>
          <div className="flex flex-wrap items-end gap-4">
            <label className="flex flex-col gap-2 text-xs text-slate-400 font-medium">
              Risk from
              <div className="flex items-center gap-2">
                <input
                  type="number" min={0} max={100} value={minRisk}
                  onChange={(e) => setMinRisk(Number(e.target.value))}
                  className="bg-slate-900/50 border border-slate-700 text-slate-200 text-sm rounded-lg focus:ring-cyan-500 focus:border-cyan-500 block w-20 p-2.5 outline-none transition-all text-center"
                />
                <span className="text-slate-500">%</span>
              </div>
            </label>
            <label className="flex flex-col gap-2 text-xs text-slate-400 font-medium">
              to
              <div className="flex items-center gap-2">
                <input
                  type="number" min={0} max={100} value={maxRisk}
                  onChange={(e) => setMaxRisk(Number(e.target.value))}
                  className="bg-slate-900/50 border border-slate-700 text-slate-200 text-sm rounded-lg focus:ring-cyan-500 focus:border-cyan-500 block w-20 p-2.5 outline-none transition-all text-center"
                />
                <span className="text-slate-500">%</span>
              </div>
            </label>
            <div className="flex flex-col gap-2">
              <span className="text-xs text-slate-400 font-medium">Tone</span>
              <select 
                value={tone} 
                onChange={(e) => setTone(e.target.value)}
                className="bg-slate-900/50 border border-slate-700 text-slate-200 text-sm rounded-lg focus:ring-cyan-500 focus:border-cyan-500 block p-2.5 outline-none transition-all"
              >
                {TONES.map((t) => <option key={t} value={t}>{t[0].toUpperCase() + t.slice(1)}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-xs text-slate-400 font-medium">Length</span>
              <select 
                value={length} 
                onChange={(e) => setLength(e.target.value)}
                className="bg-slate-900/50 border border-slate-700 text-slate-200 text-sm rounded-lg focus:ring-cyan-500 focus:border-cyan-500 block p-2.5 outline-none transition-all"
              >
                {LENGTHS.map((l) => <option key={l} value={l}>{l[0].toUpperCase() + l.slice(1)}</option>)}
              </select>
            </div>
            <button 
              onClick={handleRun} 
              disabled={running} 
              className="flex items-center gap-2 bg-cyan-600 hover:bg-cyan-500 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors border border-cyan-500 shadow-lg shadow-cyan-900/20 disabled:opacity-50 h-[42px]"
            >
              {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Settings className="w-4 h-4" />}
              {running ? "Generating batch…" : "Generate batch"}
            </button>
          </div>
          {error && <div className="mt-4 bg-rose-500/10 border border-rose-500/30 text-rose-400 px-4 py-3 rounded-lg text-sm">{error}</div>}
          {result && (
            <div className="mt-4 bg-slate-900/50 border border-slate-700 px-4 py-3 rounded-lg text-sm text-slate-300">
              <span className="text-white font-medium">Drafted {result.generated}</span>, skipped {result.skipped} (already had a draft, or past the cap).
              {result.message && <span className="block mt-1 text-slate-400 italic">{result.message}</span>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
