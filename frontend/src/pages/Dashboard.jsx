import { useEffect, useState } from "react";
import { fetchSummary, fetchCustomers, runHighRiskAlert } from "../api";
import CustomerTable from "../components/CustomerTable";
import { formatPercent, driverLabel } from "../risk";
import {
  PieChart, Pie, Cell,
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  BarChart
} from 'recharts';
import { Users, AlertTriangle, Activity, TrendingDown, ShieldAlert, Cpu, Download, ChevronDown, FileText, FileSpreadsheet, Loader2, CheckCircle2 } from 'lucide-react';

// Theme Colors
const COLORS = {
  highRisk: '#ef4444',   // Red
  mediumRisk: '#f59e0b', // Orange
  lowRisk: '#10b981',    // Green
  shapDriver: '#06b6d4', // Cyan
  chartGrid: '#334155',  // Slate-700
  chartText: '#94a3b8',  // Slate-400
  tooltipBg: '#1e293b',  // Slate-800
};

// Mock data for the activity chart (backend doesn't provide this yet)
const activityVsChurnData = [
  { segment: '0-2 Wks', avgLogins: 45, churnProb: 0.12 },
  { segment: '2-4 Wks', avgLogins: 38, churnProb: 0.18 },
  { segment: '1-2 Mos', avgLogins: 25, churnProb: 0.35 },
  { segment: '2-3 Mos', avgLogins: 15, churnProb: 0.55 },
  { segment: '3-6 Mos', avgLogins: 8, churnProb: 0.78 },
  { segment: '6+ Mos', avgLogins: 4, churnProb: 0.88 },
];

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-slate-800 border border-slate-700 p-3 rounded-lg shadow-xl text-sm">
        <p className="text-slate-200 font-semibold mb-2">{label}</p>
        {payload.map((entry, index) => (
          <div key={index} className="flex items-center gap-2 mb-1">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: entry.color || entry.fill }} />
            <span className="text-slate-300">
              {entry.name}: <span className="font-medium text-white">{entry.value}</span>
            </span>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

export default function Dashboard({ onSelectCustomer, onViewAll, isAdmin }) {
  const [summary, setSummary] = useState(null);
  const [highRisk, setHighRisk] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [alertStatus, setAlertStatus] = useState(null);
  const [alertBusy, setAlertBusy] = useState(false);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [downloadState, setDownloadState] = useState({ status: 'idle', format: null });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [summaryData, customers] = await Promise.all([
          fetchSummary(),
          fetchCustomers(true),
        ]);
        if (!cancelled) {
          setSummary(summaryData);
          setHighRisk(customers.slice(0, 8));
        }
      } catch (err) {
        if (!cancelled) setError("Couldn't load dashboard data. Is the backend running?");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const handleDownload = (format) => {
    setIsDropdownOpen(false);
    setDownloadState({ status: 'loading', format });
    setTimeout(() => {
      setDownloadState({ status: 'success', format });
      setTimeout(() => setDownloadState({ status: 'idle', format: null }), 2500);
    }, 1500);
  };

  async function handleSendAlert() {
    setAlertBusy(true);
    setAlertStatus(null);
    try {
      const result = await runHighRiskAlert(0.75);
      setAlertStatus(result);
    } catch {
      setAlertStatus({ error: true });
    } finally {
      setAlertBusy(false);
    }
  }

  if (loading) {
    return <p className="text-slate-400">Loading dashboard…</p>;
  }

  if (error) {
    return <p className="text-red-500">{error}</p>;
  }

  // Transform backend data for charts
  const riskDistributionData = summary ? [
    { name: 'Low Risk', value: Object.values(summary.risk_distribution)[0] || 0, color: COLORS.lowRisk },
    { name: 'Medium Risk', value: Object.values(summary.risk_distribution)[1] || 0, color: COLORS.mediumRisk },
    { name: 'High Risk', value: Object.values(summary.risk_distribution)[2] || 0, color: COLORS.highRisk },
  ].filter(d => d.value > 0) : [];

  const shapDriversData = summary ? Object.entries(summary.top_driver_breakdown || {})
    .map(([feature, count]) => ({ feature: driverLabel(feature), impact: count }))
    .sort((a, b) => b.impact - a.impact) : [];

  // If there are no shap drivers or all impacts are 0, ensure it renders properly
  const hasShapData = shapDriversData.some(d => d.impact > 0);

  return (
    <div className="text-slate-200 font-sans selection:bg-cyan-900 pb-10">
      
      {/* Header */}
      <header className="flex flex-col md:flex-row items-start md:items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <div className="bg-cyan-500/10 p-2 rounded-lg border border-cyan-500/20">
            <Cpu className="w-8 h-8 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight">RetainAI Dashboard</h1>
            <p className="text-slate-400 text-sm mt-1">Live Customer Risk Assessment & Predictive Modeling</p>
          </div>
        </div>
        
        <div className="mt-4 md:mt-0 flex items-center gap-4 z-50">
          {/* Status Badge */}
          <div className="hidden sm:flex items-center gap-2 bg-slate-800/50 px-4 py-2 rounded-full border border-slate-700">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
            <span className="text-sm font-medium text-slate-300">Live Pipeline</span>
          </div>

          {/* Download Dropdown UI */}
          <div className="relative">
            {downloadState.status === 'loading' ? (
              <button disabled className="flex items-center gap-2 bg-slate-800 border border-slate-700 px-4 py-2 rounded-lg text-sm font-medium text-slate-300 cursor-not-allowed">
                <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
                Generating {downloadState.format}...
              </button>
            ) : downloadState.status === 'success' ? (
              <button disabled className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/30 px-4 py-2 rounded-lg text-sm font-medium text-emerald-400 cursor-default transition-colors">
                <CheckCircle2 className="w-4 h-4" />
                Downloaded {downloadState.format}
              </button>
            ) : (
              <button 
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                className="flex items-center gap-2 bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors border border-cyan-500 hover:border-cyan-400 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 shadow-lg shadow-cyan-900/20"
              >
                <Download className="w-4 h-4" />
                Download Report
                <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${isDropdownOpen ? 'rotate-180' : ''}`} />
              </button>
            )}

            {isDropdownOpen && downloadState.status === 'idle' && (
              <div className="absolute right-0 mt-2 w-48 bg-slate-800 border border-slate-700 rounded-lg shadow-xl overflow-hidden origin-top-right z-50">
                <div className="p-1">
                  <button 
                    onClick={() => handleDownload('PDF')}
                    className="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-slate-300 hover:text-white hover:bg-slate-700/50 rounded-md transition-colors"
                  >
                    <FileText className="w-4 h-4 text-rose-400" />
                    Export as PDF
                  </button>
                  <button 
                    onClick={() => handleDownload('CSV')}
                    className="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-slate-300 hover:text-white hover:bg-slate-700/50 rounded-md transition-colors"
                  >
                    <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
                    Export as CSV
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* KPI Cards section */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 p-6 rounded-2xl relative overflow-hidden group hover:border-slate-600 transition-colors">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <Users className="w-16 h-16 text-emerald-500" />
          </div>
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-emerald-500/10 rounded-lg">
              <Users className="w-5 h-5 text-emerald-400" />
            </div>
            <h3 className="text-slate-400 font-medium">Active Customers</h3>
          </div>
          <div className="flex items-baseline gap-2">
            <p className="text-4xl font-bold text-emerald-400">{summary.total_customers.toLocaleString()}</p>
          </div>
        </div>

        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 p-6 rounded-2xl relative overflow-hidden group hover:border-slate-600 transition-colors">
           <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <ShieldAlert className="w-16 h-16 text-red-500" />
          </div>
          <div className="flex items-center gap-3 mb-2">
             <div className="p-2 bg-red-500/10 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-red-400" />
            </div>
            <h3 className="text-slate-400 font-medium">High-Risk Segment</h3>
          </div>
          <div className="flex items-baseline gap-2">
            <p className="text-4xl font-bold text-red-500">{summary.high_risk_count.toLocaleString()}</p>
            <div className="flex items-center text-red-400 text-sm font-medium bg-red-500/10 px-2 py-1 rounded-full">
              <TrendingDown className="w-4 h-4 mr-1" />
              Critical
            </div>
          </div>
        </div>

        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 p-6 rounded-2xl relative overflow-hidden group hover:border-slate-600 transition-colors">
           <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <Activity className="w-16 h-16 text-cyan-500" />
          </div>
          <div className="flex items-center gap-3 mb-2">
             <div className="p-2 bg-cyan-500/10 rounded-lg">
              <Activity className="w-5 h-5 text-cyan-400" />
            </div>
            <h3 className="text-slate-400 font-medium">Avg Churn Score</h3>
          </div>
          <div className="flex items-baseline gap-2">
            <p className="text-4xl font-bold text-white">{summary.avg_risk_score.toFixed(2)}</p>
            <span className="text-slate-500 text-sm">/ 1.0</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Chart 1: Donut Chart - Risk Distribution */}
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 p-6 rounded-2xl flex flex-col">
          <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
            Customer Risk Distribution
          </h3>
          <div className="flex-1 min-h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={riskDistributionData}
                  cx="50%"
                  cy="50%"
                  innerRadius={80}
                  outerRadius={120}
                  paddingAngle={5}
                  dataKey="value"
                  stroke="none"
                >
                  {riskDistributionData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
                <Legend 
                  verticalAlign="bottom" 
                  height={36}
                  wrapperStyle={{ color: COLORS.chartText }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Horizontal Bar - SHAP Drivers */}
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 p-6 rounded-2xl flex flex-col">
          <h3 className="text-lg font-semibold text-white mb-6">Churn Drivers (SHAP)</h3>
          <div className="flex-1 min-h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                layout="vertical"
                data={shapDriversData}
                margin={{ top: 5, right: 30, left: 40, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke={COLORS.chartGrid} />
                <XAxis 
                  type="number" 
                  stroke={COLORS.chartText}
                  tick={{ fill: COLORS.chartText, fontSize: 12 }}
                  domain={[0, 'dataMax']}
                />
                <YAxis 
                  dataKey="feature" 
                  type="category" 
                  stroke={COLORS.chartText}
                  tick={{ fill: COLORS.chartText, fontSize: 12 }}
                  width={140}
                />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: '#334155', opacity: 0.4 }} />
                <Bar dataKey="impact" name="Customers Affected" fill={COLORS.shapDriver} radius={[0, 4, 4, 0]}>
                  {
                    shapDriversData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS.shapDriver} fillOpacity={1 - (index * 0.1)} />
                    ))
                  }
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 p-6 rounded-2xl mb-6">
        <h3 className="text-lg font-semibold text-white mb-6">Activity Metrics vs. Churn Risk</h3>
        <div className="h-[350px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={activityVsChurnData}
              margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORS.chartGrid} />
              
              <XAxis 
                dataKey="segment" 
                stroke={COLORS.chartText} 
                tick={{ fill: COLORS.chartText }}
                dy={10}
              />
              
              <YAxis 
                yAxisId="left" 
                stroke={COLORS.chartText}
                tick={{ fill: COLORS.chartText }}
                label={{ value: 'Avg Logins / Month', angle: -90, position: 'insideLeft', fill: COLORS.chartText, dy: 50, dx: -10 }}
              />
              
              <YAxis 
                yAxisId="right" 
                orientation="right" 
                stroke={COLORS.chartText}
                tick={{ fill: COLORS.chartText }}
                tickFormatter={(val) => `${(val * 100).toFixed(0)}%`}
                label={{ value: 'Churn Probability', angle: 90, position: 'insideRight', fill: COLORS.chartText, dy: -50, dx: 10 }}
              />
              
              <Tooltip content={<CustomTooltip />} cursor={{ fill: '#334155', opacity: 0.4 }} />
              <Legend wrapperStyle={{ paddingTop: '20px', color: COLORS.chartText }} />
              
              <Bar 
                yAxisId="left" 
                dataKey="avgLogins" 
                name="Avg Logins" 
                fill="#3b82f6" 
                radius={[4, 4, 0, 0]} 
                barSize={40}
              />
              
              <Line 
                yAxisId="right" 
                type="monotone" 
                dataKey="churnProb" 
                name="Churn Prob." 
                stroke={COLORS.mediumRisk} 
                strokeWidth={3} 
                dot={{ r: 6, fill: '#0f172a', stroke: COLORS.mediumRisk, strokeWidth: 2 }}
                activeDot={{ r: 8 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 p-6 rounded-2xl">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-lg font-semibold text-white">
            High-risk customers
          </h3>
          <div className="flex gap-4 items-center">
            {isAdmin && (
              <div className="flex flex-col items-end">
                <button
                  onClick={handleSendAlert}
                  disabled={alertBusy}
                  className="bg-rose-600 hover:bg-rose-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {alertBusy ? "Sending…" : "Send high-risk alert"}
                </button>
                {alertStatus && (
                  <p className="text-xs text-slate-400 mt-1">
                    {alertStatus.error
                      ? "Couldn't send the alert."
                      : `${alertStatus.count} flagged · Slack: ${alertStatus.slack} · Email: ${alertStatus.email}`}
                  </p>
                )}
              </div>
            )}
            <button
              onClick={onViewAll}
              className="border border-slate-600 hover:bg-slate-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              View all customers
            </button>
          </div>
        </div>
        
        {/* We keep the existing CustomerTable here */}
        <div className="rounded-xl overflow-hidden border border-slate-700">
          <CustomerTable
            customers={highRisk}
            onSelect={onSelectCustomer}
            emptyLabel="No high-risk customers right now."
          />
        </div>
      </div>
    </div>
  );
}
