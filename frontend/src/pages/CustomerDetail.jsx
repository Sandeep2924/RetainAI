import { useEffect, useState } from "react";
import {
  fetchCustomerDetail,
  fetchCustomerHistory,
  fetchCustomerNotes,
  addCustomerNote,
  assignOwner,
  fetchRiskTrend,
} from "../api";
import RiskMeter from "../components/RiskMeter";
import RiskBadge from "../components/RiskBadge";
import { driverLabel } from "../risk";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, Cell,
  LineChart, Line, CartesianGrid,
} from "recharts";
import { ArrowLeft, Mail, UserPlus, Clock, Activity, LogIn, LifeBuoy, FileText, Send, Calendar, DollarSign, MousePointer2 } from 'lucide-react';

export default function CustomerDetail({ customerId, onBack, isAdmin, onGenerateEmail }) {
  const [detail, setDetail] = useState(null);
  const [history, setHistory] = useState(null);
  const [trend, setTrend] = useState(null);
  const [notes, setNotes] = useState([]);
  const [noteText, setNoteText] = useState("");
  const [addingNote, setAddingNote] = useState(false);
  const [ownerInput, setOwnerInput] = useState("");
  const [savingOwner, setSavingOwner] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      fetchCustomerDetail(customerId),
      fetchCustomerHistory(customerId),
      fetchRiskTrend(customerId, 14),
      fetchCustomerNotes(customerId),
    ])
      .then(([d, h, t, n]) => {
        if (!cancelled) {
          setDetail(d);
          setHistory(h);
          setTrend(t);
          setNotes(n);
          setOwnerInput(d.owner_email || "");
        }
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load this customer's data.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [customerId]);

  async function handleAddNote() {
    if (!noteText.trim()) return;
    setAddingNote(true);
    try {
      const created = await addCustomerNote(customerId, noteText.trim());
      setNotes((prev) => [created, ...prev]);
      setNoteText("");
    } finally {
      setAddingNote(false);
    }
  }

  async function handleSaveOwner() {
    if (!ownerInput.trim()) return;
    setSavingOwner(true);
    try {
      await assignOwner(customerId, ownerInput.trim());
      setDetail((prev) => ({ ...prev, owner_email: ownerInput.trim() }));
    } finally {
      setSavingOwner(false);
    }
  }

  if (loading) return <p className="text-slate-400">Loading customer profile…</p>;
  if (error) return <p className="text-rose-500">{error}</p>;
  if (!detail) return null;

  const shapData = Object.entries(detail.shap_explanations || {})
    .map(([key, value]) => ({ name: driverLabel(key), value }))
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value));

  const maxAbs = Math.max(...shapData.map(d => Math.abs(d.value)), 0.05);
  const shapDomain = [-maxAbs, maxAbs];

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-slate-800 border border-slate-700 p-3 rounded-lg shadow-xl text-sm">
          <p className="text-slate-200 font-semibold mb-2">{label}</p>
          {payload.map((entry, index) => (
            <div key={index} className="flex items-center gap-2 mb-1">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: entry.color || entry.fill || entry.stroke }} />
              <span className="text-slate-300">
                {entry.name}: <span className="font-medium text-white">{typeof entry.value === 'number' ? entry.value.toFixed(2) : entry.value}</span>
              </span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="text-slate-200 font-sans selection:bg-cyan-900 pb-10 max-w-7xl mx-auto space-y-6">
      
      {/* Header Actions */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors px-3 py-2 -ml-3 rounded-lg hover:bg-slate-800/50"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </button>

        {onGenerateEmail && (
          <button
            onClick={() => onGenerateEmail(customerId)}
            className="flex items-center gap-2 bg-cyan-600 hover:bg-cyan-500 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors border border-cyan-500 shadow-lg shadow-cyan-900/20"
          >
            <Mail className="w-4 h-4" />
            Generate Retention Email
          </button>
        )}
      </div>

      {/* Main Profile Card */}
      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 p-6 md:p-8 rounded-2xl flex flex-col lg:flex-row justify-between gap-8">
        <div>
          <div className="flex items-center gap-4 mb-2">
            <h2 className="text-2xl md:text-3xl font-bold text-white">{detail.name}</h2>
            <RiskBadge score={detail.churn_risk_score} />
          </div>
          <p className="text-slate-400 mb-6 flex items-center gap-2">
            <Mail className="w-4 h-4" /> {detail.email}
            <span className="mx-2 opacity-30">|</span>
            <span className="font-mono text-xs opacity-70">{detail.customer_id}</span>
          </p>

          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 bg-slate-900/50 p-4 rounded-xl border border-slate-700/50">
            <UserPlus className="w-5 h-5 text-slate-500" />
            {isAdmin ? (
              <div className="flex items-center gap-3 w-full sm:w-auto">
                <input
                  value={ownerInput}
                  onChange={(e) => setOwnerInput(e.target.value)}
                  placeholder="Assign owner email"
                  className="bg-slate-800 border border-slate-600 text-slate-200 text-sm rounded-lg focus:ring-cyan-500 focus:border-cyan-500 block w-full sm:w-64 p-2.5 outline-none transition-all"
                />
                <button
                  onClick={handleSaveOwner}
                  disabled={savingOwner || !ownerInput.trim() || ownerInput === detail.owner_email}
                  className="px-4 py-2.5 text-sm font-medium text-white bg-slate-700 border border-slate-600 rounded-lg hover:bg-slate-600 transition-colors disabled:opacity-50"
                >
                  {savingOwner ? "Saving…" : "Assign"}
                </button>
              </div>
            ) : (
              <div className="text-sm">
                <span className="text-slate-400 block mb-1">Account Owner</span>
                <span className="font-medium text-slate-200">{detail.owner_email || <span className="text-slate-500 italic">Unassigned</span>}</span>
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col items-start lg:items-end min-w-[200px]">
          <h3 className="text-sm font-medium text-slate-400 mb-3">Live Churn Risk Score</h3>
          <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-700/50 w-full lg:w-auto flex flex-col items-center">
            <RiskMeter score={detail.churn_risk_score} width={160} />
            <p className="text-center mt-3 text-2xl font-bold text-white">
              {(detail.churn_risk_score * 100).toFixed(1)}%
            </p>
          </div>
        </div>
      </div>

      {/* KPI Tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <InfoTile icon={Clock} label="Account Age" value={`${detail.account_age_days} days`} />
        <InfoTile icon={Activity} label="Daily Usage" value={`${detail.daily_usage_mins} min`} />
        <InfoTile icon={LogIn} label="Login Freq" value={detail.login_frequency_raw} />
        <InfoTile icon={LifeBuoy} label="Last Ticket" value={detail.last_support_ticket_raw || "None on file"} />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* SHAP Drivers */}
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 p-6 rounded-2xl flex flex-col">
          <div className="mb-6">
            <h3 className="text-lg font-semibold text-white">What's driving this score?</h3>
            <p className="text-xs text-slate-400 mt-1">Red pushes risk up, green pulls it down.</p>
          </div>
          <div className="flex-1 min-h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={shapData}
                layout="vertical"
                margin={{ top: 0, right: 20, left: 0, bottom: 0 }}
              >
                <XAxis type="number" hide domain={shapDomain} />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={150}
                  tick={{ fill: "#94a3b8", fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <RechartsTooltip content={<CustomTooltip />} cursor={{ fill: '#334155', opacity: 0.3 }} />
                <Bar dataKey="value" name="Impact" radius={[0, 4, 4, 0]} barSize={16}>
                  {shapData.map((entry, i) => (
                    <Cell key={i} fill={entry.value >= 0 ? "#ef4444" : "#10b981"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Risk Trend */}
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 p-6 rounded-2xl flex flex-col">
          <h3 className="text-lg font-semibold text-white mb-6">Risk Trend (Last 14 Days)</h3>
          <div className="flex-1 min-h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid stroke="#334155" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                  axisLine={{ stroke: "#475569" }}
                  tickLine={false}
                  tickFormatter={(d) => d.slice(5)}
                  dy={10}
                />
                <YAxis
                  domain={[0, 1]}
                  tickFormatter={(v) => `${Math.round(v * 100)}%`}
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <RechartsTooltip content={<CustomTooltip />} />
                <Line 
                  type="monotone" 
                  dataKey="churn_risk_score" 
                  name="Risk Score"
                  stroke="#3b82f6" 
                  strokeWidth={3} 
                  dot={{ r: 4, fill: '#0f172a', stroke: '#3b82f6', strokeWidth: 2 }}
                  activeDot={{ r: 6, fill: '#3b82f6' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* CS Notes */}
      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 p-6 rounded-2xl">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <FileText className="w-5 h-5 text-slate-400" /> CS Notes
        </h3>
        
        <div className="flex flex-col sm:flex-row gap-4 mb-8 bg-slate-900/30 p-2 rounded-xl border border-slate-700/50">
          <textarea
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            placeholder="Log a call, an intervention, or anything worth remembering…"
            rows={2}
            className="flex-1 bg-transparent text-slate-200 text-sm p-3 outline-none resize-y min-h-[60px]"
          />
          <button
            onClick={handleAddNote}
            disabled={addingNote || !noteText.trim()}
            className="self-end sm:self-center mr-2 mb-2 sm:mb-0 bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            <Send className="w-4 h-4" />
            {addingNote ? "Saving…" : "Add Note"}
          </button>
        </div>

        {notes.length === 0 ? (
          <div className="text-center py-8 bg-slate-900/20 rounded-xl border border-slate-700/30 border-dashed">
            <p className="text-sm text-slate-500">No notes have been logged for this customer yet.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {notes.map((n) => (
              <div key={n.id} className="bg-slate-900/40 p-4 rounded-xl border border-slate-700/50 hover:border-slate-600 transition-colors">
                <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{n.text}</p>
                <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-700/50 text-xs text-slate-500">
                  <span className="font-medium text-slate-400">{n.author}</span>
                  <span>•</span>
                  <span>{new Date(n.created_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* History Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <HistorySection icon={LogIn} title="Recent Logins" rows={history.logins} columns={["login_timestamp", "device", "ip_country"]} />
        <HistorySection icon={MousePointer2} title="Usage Events" rows={history.usage} columns={["event_timestamp", "feature_used", "duration_secs"]} />
        <HistorySection icon={LifeBuoy} title="Support Tickets" rows={history.support} columns={["ticket_timestamp", "subject", "status"]} />
        <HistorySection icon={DollarSign} title="Payments" rows={history.payments} columns={["payment_timestamp", "amount_usd", "status"]} />
      </div>

    </div>
  );
}

function InfoTile({ icon: Icon, label, value }) {
  return (
    <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 p-5 rounded-2xl flex flex-col items-start hover:border-slate-600 transition-colors group">
      <div className="p-2 bg-slate-700/50 rounded-lg mb-3 group-hover:bg-cyan-500/10 group-hover:text-cyan-400 text-slate-400 transition-colors">
        <Icon className="w-5 h-5" />
      </div>
      <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-lg font-semibold text-white">{value}</p>
    </div>
  );
}

function HistorySection({ icon: Icon, title, rows, columns }) {
  return (
    <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl overflow-hidden flex flex-col">
      <div className="px-5 py-4 border-b border-slate-700 bg-slate-800/80 flex items-center gap-2">
        <Icon className="w-4 h-4 text-slate-400" />
        <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
      </div>
      
      {!rows || rows.length === 0 ? (
        <div className="p-8 text-center flex-1 flex flex-col items-center justify-center">
          <Calendar className="w-8 h-8 text-slate-600 mb-3" />
          <p className="text-sm text-slate-500">No records found.</p>
        </div>
      ) : (
        <div className="overflow-x-auto flex-1">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="text-xs text-slate-400 bg-slate-900/50 uppercase">
              <tr>
                {columns.map((col) => (
                  <th key={col} className="px-5 py-3 font-medium whitespace-nowrap">
                    {col.replace(/_/g, " ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50 bg-slate-800/30">
              {rows.slice(0, 5).map((row, i) => (
                <tr key={i} className="hover:bg-slate-700/30 transition-colors">
                  {columns.map((col) => {
                    // Format timestamp if it exists
                    let displayVal = row[col] ?? "";
                    if (col.includes("timestamp") && displayVal) {
                      displayVal = new Date(displayVal).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
                    }
                    return (
                      <td key={col} className="px-5 py-3">
                        {String(displayVal)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
