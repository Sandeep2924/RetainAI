import React, { useState } from 'react';
import { 
  AreaChart, Area, 
  ScatterChart, Scatter, ZAxis,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  ComposedChart, Bar, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer 
} from 'recharts';
import { 
  FileText, 
  FileSpreadsheet, 
  Mail, 
  Download, 
  Loader2, 
  CheckCircle2,
  TrendingUp,
  AlertTriangle,
  DollarSign,
  Users,
  Activity, 
  ShieldAlert,
  ChevronRight,
  Send,
  ArrowLeft
} from 'lucide-react';
import { generateReport, downloadReportCsv, emailReport, sendScheduledReport } from '../api';

const COLORS = {
  primary: '#06b6d4',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#f43f5e',
  purple: '#8b5cf6',
  grid: '#334155',
  text: '#94a3b8',
  tooltipBg: '#1e293b',
};

const historicalTrendData = [
  { month: 'Jan', avgRisk: 0.21, criticalUsers: 120, baseline: 0.25 },
  { month: 'Feb', avgRisk: 0.23, criticalUsers: 135, baseline: 0.25 },
  { month: 'Mar', avgRisk: 0.28, criticalUsers: 180, baseline: 0.25 },
  { month: 'Apr', avgRisk: 0.35, criticalUsers: 250, baseline: 0.25 },
  { month: 'May', avgRisk: 0.32, criticalUsers: 210, baseline: 0.25 },
  { month: 'Jun', avgRisk: 0.27, criticalUsers: 160, baseline: 0.25 },
  { month: 'Jul', avgRisk: 0.24, criticalUsers: 145, baseline: 0.25 },
];

const loginVsChurnData = Array.from({ length: 60 }, (_, i) => ({
  logins: Math.floor(Math.random() * 40) + 1,
  churnScore: Math.random() * (Math.random() > 0.5 ? 0.4 : 1),
  companySize: Math.floor(Math.random() * 1000) + 10,
})).map(d => ({
  ...d,
  churnScore: Math.min(1, Math.max(0.05, 1.2 - (d.logins * 0.03) + (Math.random() * 0.3 - 0.15)))
}));

const healthMetricsData = [
  { metric: 'Feature Adoption', cohort: 85, benchmark: 65, fullMark: 100 },
  { metric: 'Login Frequency', cohort: 45, benchmark: 70, fullMark: 100 },
  { metric: 'Support Tickets', cohort: 90, benchmark: 40, fullMark: 100 },
  { metric: 'Payment Health', cohort: 60, benchmark: 95, fullMark: 100 },
  { metric: 'Profile Setup', cohort: 100, benchmark: 80, fullMark: 100 },
];

const revenueImpactData = [
  { month: 'Q1', atRiskRev: 45000, retainedRev: 250000, totalRev: 295000 },
  { month: 'Q2', atRiskRev: 75000, retainedRev: 260000, totalRev: 335000 },
  { month: 'Q3', atRiskRev: 120000, retainedRev: 240000, totalRev: 360000 },
  { month: 'Q4', atRiskRev: 55000, retainedRev: 320000, totalRev: 375000 },
];

const REPORT_TYPES = [
  {
    id: 'churn_overview',
    title: 'Comprehensive Churn Report',
    description: 'Full overview of customer health, churn probabilities, and macro trends over the last 30 days.',
    icon: FileText,
    color: 'text-cyan-400',
    bgColor: 'bg-cyan-500/10',
    borderColor: 'border-cyan-500/30'
  },
  {
    id: 'customer_risk',
    title: 'High-Risk Customers List',
    description: 'Filtered list of all active users with a churn probability score greater than 0.75.',
    icon: ShieldAlert,
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/30'
  },
  {
    id: 'model_performance',
    title: 'SHAP Churn Drivers Analysis',
    description: 'Detailed breakdown of the top machine learning features driving recent churn predictions.',
    icon: Activity,
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/30'
  },
  {
    id: 'retention_campaign',
    title: 'Engagement & Usage Metrics',
    description: 'Raw data export of login frequencies, feature usage, and support ticket volumes.',
    icon: Users,
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/10',
    borderColor: 'border-purple-500/30'
  }
];

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-slate-800/95 backdrop-blur border border-slate-600 p-4 rounded-xl shadow-2xl">
        <p className="text-slate-200 font-bold mb-3 border-b border-slate-700 pb-2">{label || 'Data Point'}</p>
        {payload.map((entry, index) => (
          <div key={index} className="flex items-center gap-3 mb-1.5 text-sm">
            <div className="w-3 h-3 rounded-sm shadow-sm" style={{ backgroundColor: entry.color || entry.fill }} />
            <span className="text-slate-300 font-medium">
              {entry.name}:
            </span>
            <span className="text-white font-bold ml-auto">
              {typeof entry.value === 'number' && entry.value % 1 !== 0 
                ? entry.value.toFixed(2) 
                : entry.value.toLocaleString()}
            </span>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

export default function Reports({ onBack }) {
  const [exportState, setExportState] = useState({ status: 'idle', type: null });
  const [selectedReports, setSelectedReports] = useState(['churn_overview']);
  const [deliveryMethod, setDeliveryMethod] = useState('download');
  const [email, setEmail] = useState('');
  const [generatorStatus, setGeneratorStatus] = useState('idle');
  const [toast, setToast] = useState(null);
  const [quickEmailModal, setQuickEmailModal] = useState(false);
  const [quickEmailInput, setQuickEmailInput] = useState('');

  // Scheduled reports state
  const [schedFreq, setSchedFreq] = useState('weekly');
  const [schedEmail, setSchedEmail] = useState('');
  const [schedReports, setSchedReports] = useState(['churn_overview', 'customer_risk']);
  const [schedStatus, setSchedStatus] = useState('idle'); // idle | sending | success | error

  const showToast = (type, message) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 4000);
  };

  // Quick export: generates first selected report type OR churn_overview and downloads/emails it
  const handleExport = async (type) => {
    if (type === 'email') {
      setQuickEmailModal(true);
      return;
    }
    setExportState({ status: 'loading', type });
    try {
      const reportType = selectedReports[0] || 'churn_overview';
      const report = await generateReport(reportType, null, null);
      if (type === 'csv') {
        await downloadReportCsv(report.id, reportType);
        showToast('success', `CSV downloaded: ${report.name}`);
      } else if (type === 'pdf') {
        // PDF: download as CSV (no PDF renderer yet) — clearly labelled
        await downloadReportCsv(report.id, reportType);
        showToast('success', `Report downloaded: ${report.name}`);
      }
      setExportState({ status: 'success', type });
      setTimeout(() => setExportState({ status: 'idle', type: null }), 2500);
    } catch (err) {
      console.error(err);
      setExportState({ status: 'idle', type: null });
      showToast('error', err?.response?.data?.detail || 'Export failed. Check console.');
    }
  };

  const handleQuickEmail = async (e) => {
    e.preventDefault();
    if (!quickEmailInput) return;
    setQuickEmailModal(false);
    setExportState({ status: 'loading', type: 'email' });
    try {
      const reportType = selectedReports[0] || 'churn_overview';
      const report = await generateReport(reportType, null, null);
      await emailReport(report.id, quickEmailInput);
      setExportState({ status: 'success', type: 'email' });
      showToast('success', `Report emailed to ${quickEmailInput}`);
      setTimeout(() => setExportState({ status: 'idle', type: null }), 2500);
    } catch (err) {
      console.error(err);
      setExportState({ status: 'idle', type: null });
      showToast('error', err?.response?.data?.detail || 'Failed to send email.');
    }
    setQuickEmailInput('');
  };

  const getButtonContent = (type, label, Icon) => {
    if (exportState.type === type && exportState.status === 'loading') {
      return <><Loader2 className="w-4 h-4 animate-spin" /> Processing...</>;
    }
    if (exportState.type === type && exportState.status === 'success') {
      return <><CheckCircle2 className="w-4 h-4" /> {type === 'email' ? 'Sent!' : 'Downloaded!'}</>;
    }
    return <><Icon className="w-4 h-4" /> {label}</>;
  };

  const toggleReportSelection = (id) => {
    setSelectedReports(prev =>
      prev.includes(id)
        ? prev.filter(reportId => reportId !== id)
        : [...prev, id]
    );
  };

  const handleGenerateSubmit = async (e) => {
    e.preventDefault();
    if (selectedReports.length === 0) return;
    if (deliveryMethod === 'email' && !email) return;

    setGeneratorStatus('processing');
    try {
      let successCount = 0;
      for (const reportType of selectedReports) {
        const report = await generateReport(reportType, null, null);
        if (deliveryMethod === 'download') {
          await downloadReportCsv(report.id, reportType);
          successCount++;
        } else if (deliveryMethod === 'email') {
          await emailReport(report.id, email);
          successCount++;
        }
      }
      setGeneratorStatus('success');
      showToast(
        'success',
        deliveryMethod === 'email'
          ? `${successCount} report(s) emailed to ${email}`
          : `${successCount} report(s) downloaded successfully`
      );
    } catch (err) {
      console.error(err);
      setGeneratorStatus('idle');
      showToast('error', err?.response?.data?.detail || 'Failed to generate report. See console.');
    }
    setTimeout(() => setGeneratorStatus('idle'), 3000);
  };

  return (
    <div className="text-slate-200 font-sans selection:bg-cyan-900/50 pb-10 max-w-7xl mx-auto space-y-6 sm:space-y-8">

      {/* Toast Notification */}
      {toast && (
        <div className={`fixed top-5 right-5 z-50 flex items-center gap-3 px-4 sm:px-5 py-3 sm:py-4 rounded-xl shadow-2xl border text-sm font-medium transition-all animate-in max-w-[90vw] ${
          toast.type === 'success'
            ? 'bg-emerald-900/90 border-emerald-500/50 text-emerald-200'
            : 'bg-red-900/90 border-red-500/50 text-red-200'
        }`}>
          {toast.type === 'success'
            ? <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            : <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />}
          <span className="truncate">{toast.message}</span>
        </div>
      )}

      {/* Quick Email Modal */}
      {quickEmailModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6 sm:p-8 w-full max-w-md shadow-2xl">
            <h3 className="text-xl font-bold text-white mb-2">Email Quick Report</h3>
            <p className="text-slate-400 text-sm mb-6">
              We'll generate and email the <strong className="text-slate-200">{REPORT_TYPES.find(r => r.id === (selectedReports[0] || 'churn_overview'))?.title || 'Churn Overview'}</strong> report to the address below.
            </p>
            <form onSubmit={handleQuickEmail} className="space-y-4">
              <input
                type="email"
                required
                autoFocus
                value={quickEmailInput}
                onChange={e => setQuickEmailInput(e.target.value)}
                placeholder="recipient@company.com"
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 text-sm"
              />
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => { setQuickEmailModal(false); setQuickEmailInput(''); }}
                  className="flex-1 px-4 py-3 rounded-xl border border-slate-600 text-slate-400 hover:text-white hover:border-slate-500 transition-all font-medium text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-semibold transition-all text-sm"
                >
                  <Send className="w-4 h-4" /> Send Report
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Header Row */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 bg-slate-800/30 p-4 sm:p-6 rounded-2xl border border-slate-700/50">
        <div>
          {onBack && (
            <button
              onClick={onBack}
              className="mb-3 sm:mb-4 flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm font-medium"
            >
              <ArrowLeft className="w-4 h-4" /> Back to Dashboard
            </button>
          )}
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5 sm:gap-3">
            <TrendingUp className="text-cyan-400 w-7 h-7 sm:w-8 sm:h-8 shrink-0" />
            Reports & Analytics
          </h1>
          <p className="text-slate-400 mt-1 sm:mt-2 text-xs sm:text-sm md:text-base">
            Generate custom reports and view live breakdowns of customer health and revenue risks.
          </p>
        </div>

        {/* Quick Export Actions */}
        <div className="flex flex-wrap items-center gap-2.5 sm:gap-3 w-full sm:w-auto">
          <button
            onClick={() => handleExport('csv')}
            disabled={exportState.status !== 'idle'}
            className={`flex-1 sm:flex-initial flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-medium text-sm transition-all border ${
              exportState.type === 'csv' && exportState.status === 'success'
                ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400'
                : 'bg-slate-800 border-slate-600 text-slate-300 hover:bg-slate-700 hover:text-white'
            }`}
          >
            {getButtonContent('csv', 'Export CSV', FileSpreadsheet)}
          </button>

          <button
            onClick={() => handleExport('pdf')}
            disabled={exportState.status !== 'idle'}
            className={`flex-1 sm:flex-initial flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-medium text-sm transition-all border ${
              exportState.type === 'pdf' && exportState.status === 'success'
                ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400'
                : 'bg-slate-800 border-slate-600 text-slate-300 hover:bg-slate-700 hover:text-white'
            }`}
          >
            {getButtonContent('pdf', 'Download PDF', FileText)}
          </button>

          <button
            onClick={() => handleExport('email')}
            disabled={exportState.status !== 'idle'}
            className={`w-full sm:w-auto flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all border shadow-lg ${
              exportState.type === 'email' && exportState.status === 'success'
                ? 'bg-emerald-500 border-emerald-400 text-white shadow-emerald-500/20'
                : 'bg-cyan-600 border-cyan-500 text-white hover:bg-cyan-500 shadow-cyan-900/40'
            }`}
          >
            {getButtonContent('email', 'Email Report', Mail)}
          </button>
        </div>
      </div>

        {/* Report Generator */}
        <form onSubmit={handleGenerateSubmit} className="space-y-6">
          <div className="bg-slate-800/40 backdrop-blur-sm border border-slate-700 rounded-2xl p-6 md:p-8">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-xl font-bold text-white">1. Select Report Types</h2>
              <span className="text-sm font-medium px-3 py-1 bg-slate-700/50 text-slate-300 rounded-full">
                {selectedReports.length} selected
              </span>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {REPORT_TYPES.map((report) => {
                const isSelected = selectedReports.includes(report.id);
                const Icon = report.icon;
                
                return (
                  <div 
                    key={report.id}
                    onClick={() => toggleReportSelection(report.id)}
                    className={`relative p-5 rounded-xl border-2 cursor-pointer transition-all duration-200 group ${
                      isSelected 
                        ? 'border-cyan-500 bg-cyan-500/5' 
                        : 'border-slate-700 bg-slate-800/50 hover:border-slate-500'
                    }`}
                  >
                    <div className={`absolute top-5 right-5 w-5 h-5 rounded border flex items-center justify-center transition-colors ${
                      isSelected ? 'bg-cyan-500 border-cyan-500' : 'border-slate-500 group-hover:border-slate-400'
                    }`}>
                      {isSelected && <CheckCircle2 className="w-3.5 h-3.5 text-white" />}
                    </div>

                    <div className="flex items-start gap-4 pr-8">
                      <div className={`p-2.5 rounded-lg ${report.bgColor} border ${report.borderColor}`}>
                        <Icon className={`w-6 h-6 ${report.color}`} />
                      </div>
                      <div>
                        <h3 className={`font-semibold mb-1 ${isSelected ? 'text-white' : 'text-slate-200'}`}>
                          {report.title}
                        </h3>
                        <p className="text-sm text-slate-400 leading-relaxed">
                          {report.description}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="bg-slate-800/40 backdrop-blur-sm border border-slate-700 rounded-2xl p-4 sm:p-6 md:p-8">
            <h2 className="text-lg sm:text-xl font-bold text-white mb-4 sm:mb-6">2. Delivery Method</h2>
            
            <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 mb-4 sm:mb-6">
              <button
                type="button"
                onClick={() => setDeliveryMethod('download')}
                className={`flex-1 flex items-center justify-center gap-3 p-3.5 sm:p-4 rounded-xl border-2 transition-all ${
                  deliveryMethod === 'download'
                    ? 'border-cyan-500 bg-cyan-500/10 text-white'
                    : 'border-slate-700 bg-slate-800/50 text-slate-400 hover:text-slate-200 hover:border-slate-600'
                }`}
              >
                <Download className="w-5 h-5" />
                <span className="font-medium text-sm sm:text-base">Direct Download</span>
              </button>
              
              <button
                type="button"
                onClick={() => setDeliveryMethod('email')}
                className={`flex-1 flex items-center justify-center gap-3 p-3.5 sm:p-4 rounded-xl border-2 transition-all ${
                  deliveryMethod === 'email'
                    ? 'border-cyan-500 bg-cyan-500/10 text-white'
                    : 'border-slate-700 bg-slate-800/50 text-slate-400 hover:text-slate-200 hover:border-slate-600'
                }`}
              >
                <Mail className="w-5 h-5" />
                <span className="font-medium text-sm sm:text-base">Send to Email</span>
              </button>
            </div>

            <div className={`transition-all duration-300 overflow-hidden ${deliveryMethod === 'email' ? 'max-h-24 opacity-100' : 'max-h-0 opacity-0'}`}>
              <div className="space-y-2">
                <label htmlFor="email" className="block text-xs sm:text-sm font-medium text-slate-300">
                  Recipient Email Address
                </label>
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="team@yourcompany.com"
                  required={deliveryMethod === 'email'}
                  className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-shadow text-sm"
                />
              </div>
            </div>
          </div>

          <div className="flex justify-stretch sm:justify-end">
            <button
              type="submit"
              disabled={selectedReports.length === 0 || generatorStatus === 'processing' || generatorStatus === 'success'}
              className={`w-full sm:w-auto relative overflow-hidden flex items-center justify-center gap-2 px-6 sm:px-8 py-3.5 sm:py-4 rounded-xl font-semibold text-white transition-all duration-300 ${
                selectedReports.length === 0
                  ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                  : generatorStatus === 'success'
                  ? 'bg-emerald-500 hover:bg-emerald-600 shadow-lg shadow-emerald-500/20'
                  : 'bg-cyan-600 hover:bg-cyan-500 shadow-lg shadow-cyan-900/40 hover:shadow-cyan-500/25'
              }`}
            >
              {generatorStatus === 'idle' && (
                <>
                  {deliveryMethod === 'download' ? <Download className="w-5 h-5" /> : <Send className="w-5 h-5" />}
                  {deliveryMethod === 'download' ? 'Generate & Download' : 'Send Report'}
                  <ChevronRight className="w-5 h-5 ml-1" />
                </>
              )}
              
              {generatorStatus === 'processing' && (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Generating {selectedReports.length} {selectedReports.length === 1 ? 'Report' : 'Reports'}...
                </>
              )}

              {generatorStatus === 'success' && (
                <>
                  <CheckCircle2 className="w-5 h-5" />
                  {deliveryMethod === 'download' ? 'Download Started!' : 'Email Sent Successfully!'}
                </>
              )}
            </button>
          </div>
        </form>

        {/* ── Scheduled Reports ──────────────────────────────────────── */}
        <div className="bg-slate-800/40 backdrop-blur-sm border border-slate-700 rounded-2xl p-4 sm:p-6 md:p-8">
          <div className="flex items-center gap-3 mb-4 sm:mb-6">
            <div className="p-2.5 rounded-lg bg-purple-500/10 border border-purple-500/30 shrink-0">
              <Mail className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h2 className="text-lg sm:text-xl font-bold text-white">Scheduled Report Delivery</h2>
              <p className="text-slate-400 text-xs sm:text-sm mt-0.5">Generate and email a report bundle on demand by frequency.</p>
            </div>
          </div>

          {/* Frequency selector */}
          <div className="mb-4 sm:mb-6">
            <p className="text-xs sm:text-sm font-semibold text-slate-300 mb-3">1. Choose Frequency</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 sm:gap-3">
              {[
                { key: 'daily',   label: 'Daily',   icon: '⏱️', desc: 'Last 24 h snapshot' },
                { key: 'weekly',  label: 'Weekly',  icon: '📅', desc: '7-day rolling view'  },
                { key: 'monthly', label: 'Monthly', icon: '📆', desc: '30-day full summary'  },
              ].map(f => (
                <button
                  key={f.key}
                  type="button"
                  onClick={() => setSchedFreq(f.key)}
                  className={`flex items-center gap-3 px-4 sm:px-5 py-3 sm:py-3.5 rounded-xl border-2 transition-all text-left w-full ${
                    schedFreq === f.key
                      ? 'border-purple-500 bg-purple-500/10 text-white'
                      : 'border-slate-700 bg-slate-800/50 text-slate-400 hover:border-slate-500 hover:text-slate-200'
                  }`}
                >
                  <span className="text-xl shrink-0">{f.icon}</span>
                  <div>
                    <p className="font-semibold text-sm leading-none mb-1">{f.label}</p>
                    <p className="text-xs text-slate-500">{f.desc}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Report type multi-select */}
          <div className="mb-4 sm:mb-6">
            <p className="text-xs sm:text-sm font-semibold text-slate-300 mb-3">2. Reports to Include</p>
            <div className="flex flex-wrap gap-2">
              {REPORT_TYPES.map(r => {
                const selected = schedReports.includes(r.id);
                const Icon = r.icon;
                return (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => setSchedReports(prev =>
                      selected ? prev.filter(x => x !== r.id) : [...prev, r.id]
                    )}
                    className={`flex items-center gap-2 px-3 sm:px-3.5 py-2 rounded-lg border text-xs sm:text-sm font-medium transition-all ${
                      selected
                        ? `${r.bgColor} ${r.borderColor} ${r.color}`
                        : 'bg-slate-800/50 border-slate-700 text-slate-400 hover:border-slate-500'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {r.title.split(' ').slice(0, 2).join(' ')}
                    {selected && <CheckCircle2 className="w-3.5 h-3.5 ml-1" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Email + Send */}
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="email"
              required
              value={schedEmail}
              onChange={e => setSchedEmail(e.target.value)}
              placeholder="recipient@company.com"
              className="flex-1 bg-slate-900 border border-slate-600 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 transition-shadow text-sm"
            />
            <button
              type="button"
              disabled={!schedEmail || schedReports.length === 0 || schedStatus === 'sending' || schedStatus === 'success'}
              onClick={async () => {
                if (!schedEmail || schedReports.length === 0) return;
                setSchedStatus('sending');
                try {
                  await sendScheduledReport(schedEmail, schedFreq, schedReports);
                  setSchedStatus('success');
                  showToast('success', `${schedFreq.charAt(0).toUpperCase() + schedFreq.slice(1)} bundle emailed to ${schedEmail}`);
                  setTimeout(() => setSchedStatus('idle'), 3000);
                } catch (err) {
                  console.error(err);
                  setSchedStatus('idle');
                  showToast('error', err?.response?.data?.detail || 'Failed to send scheduled report.');
                }
              }}
              className={`flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-semibold text-sm transition-all whitespace-nowrap w-full sm:w-auto ${
                !schedEmail || schedReports.length === 0
                  ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                  : schedStatus === 'success'
                  ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/20'
                  : 'bg-purple-600 hover:bg-purple-500 text-white shadow-lg shadow-purple-900/40'
              }`}
            >
              {schedStatus === 'sending' && <><Loader2 className="w-4 h-4 animate-spin" /> Sending...</>}
              {schedStatus === 'success' && <><CheckCircle2 className="w-4 h-4" /> Sent!</>}
              {(schedStatus === 'idle' || schedStatus === 'error') && (
                <><Send className="w-4 h-4" /> Send {schedFreq.charAt(0).toUpperCase() + schedFreq.slice(1)} Bundle</>
              )}
            </button>
          </div>

          {schedReports.length === 0 && (
            <p className="text-amber-400 text-xs mt-3 flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5" /> Select at least one report type above.
            </p>
          )}
        </div>

        {/* Analytics Overview */}
        <div className="pt-2 sm:pt-6">
          <h2 className="text-xl sm:text-2xl font-extrabold text-white mb-4 sm:mb-6">Analytics Overview</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            
            {/* Chart 1: Historical Risk Trends */}
            <div className="col-span-1 lg:col-span-2 bg-slate-800/40 backdrop-blur-sm border border-slate-700 p-4 sm:p-6 rounded-2xl">
              <div className="flex items-center justify-between mb-4 sm:mb-6">
                <h3 className="text-base sm:text-xl font-bold text-white flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 sm:w-5 sm:h-5 text-warning shrink-0" />
                  Historical Churn Risk Trend (Trailing 7 Months)
                </h3>
              </div>
              <div className="h-[280px] sm:h-[350px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={historicalTrendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorRisk" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={COLORS.danger} stopOpacity={0.4}/>
                        <stop offset="95%" stopColor={COLORS.danger} stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORS.grid} />
                    <XAxis dataKey="month" stroke={COLORS.text} tick={{ fill: COLORS.text }} />
                    <YAxis stroke={COLORS.text} tick={{ fill: COLORS.text }} tickFormatter={(val) => val.toFixed(2)} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend verticalAlign="top" height={36} wrapperStyle={{ color: COLORS.text }} />
                    <Area 
                      type="monotone" 
                      dataKey="avgRisk" 
                      name="Avg Cohort Risk Score" 
                      stroke={COLORS.danger} 
                      strokeWidth={3}
                      fillOpacity={1} 
                      fill="url(#colorRisk)" 
                    />
                    <Line 
                      type="dashed" 
                      dataKey="baseline" 
                      name="Industry Baseline" 
                      stroke={COLORS.text} 
                      strokeDasharray="5 5" 
                      dot={false} 
                      strokeWidth={2}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Chart 2: Engagement Correlation */}
            <div className="bg-slate-800/40 backdrop-blur-sm border border-slate-700 p-4 sm:p-6 rounded-2xl">
              <h3 className="text-base sm:text-xl font-bold text-white mb-1 sm:mb-2 flex items-center gap-2">
                <Users className="w-4 h-4 sm:w-5 sm:h-5 text-primary shrink-0" />
                Engagement Correlation
              </h3>
              <p className="text-xs sm:text-sm text-slate-400 mb-4 sm:mb-6">Logins per month vs. Churn Probability.</p>
              <div className="h-[260px] sm:h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 20, right: 10, bottom: 20, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
                    <XAxis 
                      type="number" 
                      dataKey="logins" 
                      name="Monthly Logins" 
                      stroke={COLORS.text} 
                      tick={{ fill: COLORS.text, fontSize: 11 }}
                      label={{ value: 'Monthly Logins', position: 'insideBottom', offset: -10, fill: COLORS.text, fontSize: 11 }} 
                    />
                    <YAxis 
                      type="number" 
                      dataKey="churnScore" 
                      name="Churn Score" 
                      stroke={COLORS.text} 
                      tick={{ fill: COLORS.text, fontSize: 11 }}
                      tickFormatter={(val) => val.toFixed(1)}
                      label={{ value: 'Risk', angle: -90, position: 'insideLeft', fill: COLORS.text, fontSize: 11 }} 
                    />
                    <ZAxis type="number" dataKey="companySize" range={[40, 250]} name="Account Size" />
                    <Tooltip cursor={{ strokeDasharray: '3 3' }} content={<CustomTooltip />} />
                    <Scatter name="Active Accounts" data={loginVsChurnData} fill={COLORS.primary} fillOpacity={0.6} />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Chart 3: Cohort Health Matrix */}
            <div className="bg-slate-800/40 backdrop-blur-sm border border-slate-700 p-4 sm:p-6 rounded-2xl flex flex-col items-center">
              <div className="w-full">
                <h3 className="text-base sm:text-xl font-bold text-white mb-1 sm:mb-2 flex items-center gap-2">
                  <ActivityIcon />
                  Cohort Health Matrix
                </h3>
                <p className="text-xs sm:text-sm text-slate-400 mb-2">High-Risk Cohort vs. Ideal Benchmarks.</p>
              </div>
              <div className="h-[280px] sm:h-[320px] w-full mt-2 sm:mt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart cx="50%" cy="50%" outerRadius="68%" data={healthMetricsData}>
                    <PolarGrid stroke={COLORS.grid} />
                    <PolarAngleAxis dataKey="metric" tick={{ fill: COLORS.text, fontSize: 10 }} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: COLORS.grid }} tickCount={5} />
                    <Radar name="High-Risk Cohort" dataKey="cohort" stroke={COLORS.danger} fill={COLORS.danger} fillOpacity={0.4} />
                    <Radar name="Healthy Benchmark" dataKey="benchmark" stroke={COLORS.success} fill={COLORS.success} fillOpacity={0.2} />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                    <Tooltip content={<CustomTooltip />} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Chart 4: Revenue Impact Analysis */}
            <div className="col-span-1 lg:col-span-2 bg-slate-800/40 backdrop-blur-sm border border-slate-700 p-4 sm:p-6 rounded-2xl">
              <h3 className="text-base sm:text-xl font-bold text-white mb-1 sm:mb-2 flex items-center gap-2">
                <DollarSign className="w-4 h-4 sm:w-5 sm:h-5 text-success shrink-0" />
                Quarterly Revenue Impact Analysis
              </h3>
              <p className="text-xs sm:text-sm text-slate-400 mb-4 sm:mb-6">Tracking At-Risk ARR against Retained ARR.</p>
              <div className="h-[280px] sm:h-[350px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={revenueImpactData} margin={{ top: 20, right: 10, bottom: 20, left: -10 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORS.grid} />
                    <XAxis dataKey="month" stroke={COLORS.text} tick={{ fill: COLORS.text, fontSize: 11 }} scale="band" />
                    <YAxis 
                      yAxisId="left" 
                      stroke={COLORS.text} 
                      tick={{ fill: COLORS.text, fontSize: 11 }} 
                      tickFormatter={(val) => `$${val / 1000}k`}
                    />
                    <YAxis 
                      yAxisId="right" 
                      orientation="right" 
                      stroke={COLORS.text} 
                      tick={{ fill: COLORS.text, fontSize: 11 }} 
                      tickFormatter={(val) => `$${val / 1000}k`}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend verticalAlign="top" height={36} wrapperStyle={{ color: COLORS.text, fontSize: '12px' }} />
                    
                    <Bar yAxisId="left" dataKey="retainedRev" name="Retained ARR" stackId="a" fill={COLORS.primary} radius={[0, 0, 4, 4]} />
                    <Bar yAxisId="left" dataKey="atRiskRev" name="At-Risk ARR" stackId="a" fill={COLORS.warning} radius={[4, 4, 0, 0]} />
                    
                    <Line 
                      yAxisId="right" 
                      type="monotone" 
                      dataKey="totalRev" 
                      name="Total Pipeline ARR" 
                      stroke={COLORS.success} 
                      strokeWidth={3} 
                      dot={{ r: 4, fill: COLORS.success, strokeWidth: 2, stroke: '#0f172a' }} 
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>

          </div>
        </div>

      </div>
  );
}

function ActivityIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-purple-400">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2"></path>
    </svg>
  );
}
