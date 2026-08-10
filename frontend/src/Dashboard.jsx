import { useState } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Activity, AlertTriangle, CheckCircle, Loader2, LogOut } from 'lucide-react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';

export default function Dashboard() {
  const navigate = useNavigate();
  const token = localStorage.getItem('retainai_token');

  const [formData, setFormData] = useState({
    customer_id: 'CUST-001',
    account_age_days: 120,
    login_frequency: 0, 
    daily_usage_mins: 45.5,
    last_support_ticket: 0 
  });

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handleLogout = () => {
    localStorage.removeItem('retainai_token');
    navigate('/login');
  };

  const handleChange = (e) => {
    const { name, value, type } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'number' ? parseFloat(value) : value
    }));
  };

  const handlePredict = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      const response = await axios.post('http://127.0.0.1:8000/predict', formData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setResult(response.data);
    } catch (err) {
      if (err.response?.status === 401) handleLogout();
      setError(err.response?.data?.detail || 'Failed to connect to the prediction API.');
    } finally {
      setLoading(false);
    }
  };

  const shapData = result ? Object.entries(result.shap_explanations).map(([key, value]) => ({
    name: key.replace(/_/g, ' '),
    impact: value,
    isPositive: value > 0 
  })).sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact)) : [];

  const getRiskColorClass = (score) => {
    if (score >= 0.75) return 'risk-high';
    if (score >= 0.40) return 'risk-med';
    return 'risk-low';
  };

  return (
    <div className="dashboard-container">
      <header className="header" style={{ position: 'relative' }}>
        <button 
          onClick={handleLogout} 
          style={{ position: 'absolute', right: 0, top: 0, background: 'transparent', border: '1px solid var(--border-color)', color: 'white', padding: '8px 16px', borderRadius: 8, cursor: 'pointer', display: 'flex', alignItems: 'center' }}
        >
          <LogOut size={16} style={{ marginRight: 8 }}/> Logout
        </button>
        <motion.h1 initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
          RetainAI Dashboard
        </motion.h1>
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>
          Real-time Explainable Customer Churn Prediction
        </motion.p>
      </header>

      <div className="grid">
        <motion.div className="glass-card" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
          <h2><Activity size={20} style={{ display: 'inline', marginRight: 8 }}/> Customer Profile</h2>
          <form onSubmit={handlePredict} style={{ marginTop: 20 }}>
            <div className="form-group"><label>Customer ID</label><input type="text" name="customer_id" value={formData.customer_id} onChange={handleChange} className="form-input" /></div>
            <div className="form-group"><label>Account Age (Days)</label><input type="number" name="account_age_days" value={formData.account_age_days} onChange={handleChange} className="form-input" /></div>
            <div className="form-group"><label>Login Frequency</label>
              <select name="login_frequency" value={formData.login_frequency} onChange={handleChange} className="form-input">
                <option value={0}>Daily (0)</option><option value={1}>Weekly (1)</option><option value={2}>Monthly (2)</option>
              </select>
            </div>
            <div className="form-group"><label>Daily Usage (Mins)</label><input type="number" step="0.1" name="daily_usage_mins" value={formData.daily_usage_mins} onChange={handleChange} className="form-input" /></div>
            <div className="form-group"><label>Support Ticket Status</label>
              <select name="last_support_ticket" value={formData.last_support_ticket} onChange={handleChange} className="form-input">
                <option value={0}>Resolved (0)</option><option value={1}>Open/Escalated (1)</option><option value={2}>No Tickets (2)</option>
              </select>
            </div>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? <><Loader2 className="spinner" size={18} style={{ marginRight: 8, verticalAlign: 'middle' }}/> Analyzing...</> : 'Analyze Churn Risk'}
            </button>
          </form>
          {error && <div style={{ color: 'var(--accent-rose)', marginTop: 16, textAlign: 'center' }}>{error}</div>}
        </motion.div>

        <motion.div className="glass-card" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
          {!result && !loading && (
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
              <Activity size={48} style={{ opacity: 0.2, marginBottom: 16 }} />
              <h3>Awaiting Analysis</h3>
              <p>Run the prediction model to see results.</p>
            </div>
          )}

          {result && (
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}>
              <div className="result-box">
                <h3 style={{ color: 'var(--text-muted)', fontSize: '1rem' }}>Risk Score ({result.customer_id})</h3>
                <div className={`risk-score ${getRiskColorClass(result.churn_risk_score)}`}>
                  {(result.churn_risk_score * 100).toFixed(1)}%
                </div>
                {result.high_risk ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-rose)', fontWeight: 600 }}>
                    <AlertTriangle size={20} style={{ marginRight: 8 }}/> CRITICAL RISK DETECTED
                  </div>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-emerald)', fontWeight: 600 }}>
                    <CheckCircle size={20} style={{ marginRight: 8 }}/> HEALTHY ACCOUNT
                  </div>
                )}
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 10 }}>Analyzed by: {result.analyzed_by}</div>
              </div>

              <div style={{ marginTop: 32 }}>
                <h3 style={{ marginBottom: 8 }}>SHAP Explainability (Why?)</h3>
                <div className="shap-chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={shapData} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" horizontal={false} />
                      <XAxis type="number" stroke="var(--text-muted)" />
                      <YAxis dataKey="name" type="category" stroke="var(--text-muted)" width={120} tick={{ fontSize: 12 }} />
                      <Tooltip contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.9)', borderColor: 'var(--border-color)', borderRadius: '8px' }} formatter={(value) => [value.toFixed(4), "SHAP Impact"]} />
                      <Bar dataKey="impact" radius={[0, 4, 4, 0]}>
                        {shapData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.isPositive ? 'var(--accent-rose)' : 'var(--accent-cyan)'} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </motion.div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
