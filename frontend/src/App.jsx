import { useState } from 'react';
import axios from 'axios';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell 
} from 'recharts';
import { Activity, AlertTriangle, CheckCircle, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';

function App() {
  const [formData, setFormData] = useState({
    customer_id: 'CUST-001',
    account_age_days: 120,
    login_frequency: 0, // 0: Daily, 1: Weekly, 2: Monthly
    daily_usage_mins: 45.5,
    last_support_ticket: 0 // 0: Resolved, 1: Open, 2: None
  });

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

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
      // Connect to FastAPI backend
      const response = await axios.post('http://127.0.0.1:8000/predict', formData);
      setResult(response.data);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to connect to the prediction API.');
    } finally {
      setLoading(false);
    }
  };

  // Format SHAP data for Recharts
  const shapData = result ? Object.entries(result.shap_explanations).map(([key, value]) => ({
    name: key.replace(/_/g, ' '),
    impact: value,
    isPositive: value > 0 // Positive impact means higher churn risk
  })).sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact)) : [];

  const getRiskColorClass = (score) => {
    if (score >= 0.75) return 'risk-high';
    if (score >= 0.40) return 'risk-med';
    return 'risk-low';
  };

  return (
    <div className="dashboard-container">
      <header className="header">
        <motion.h1 initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
          RetainAI Dashboard
        </motion.h1>
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>
          Real-time Explainable Customer Churn Prediction
        </motion.p>
      </header>

      <div className="grid">
        {/* Left Column: Form */}
        <motion.div 
          className="glass-card"
          initial={{ opacity: 0, x: -20 }} 
          animate={{ opacity: 1, x: 0 }} 
          transition={{ delay: 0.2 }}
        >
          <h2><Activity size={20} style={{ display: 'inline', marginRight: 8 }}/> Customer Profile</h2>
          <p style={{ color: 'var(--text-muted)', marginBottom: 20, fontSize: '0.9rem' }}>
            Adjust metrics to simulate real-time risk evaluation.
          </p>

          <form onSubmit={handlePredict}>
            <div className="form-group">
              <label>Customer ID</label>
              <input type="text" name="customer_id" value={formData.customer_id} onChange={handleChange} className="form-input" />
            </div>

            <div className="form-group">
              <label>Account Age (Days)</label>
              <input type="number" name="account_age_days" value={formData.account_age_days} onChange={handleChange} className="form-input" />
            </div>

            <div className="form-group">
              <label>Login Frequency</label>
              <select name="login_frequency" value={formData.login_frequency} onChange={handleChange} className="form-input">
                <option value={0}>Daily (0)</option>
                <option value={1}>Weekly (1)</option>
                <option value={2}>Monthly (2)</option>
              </select>
            </div>

            <div className="form-group">
              <label>Daily Usage (Mins)</label>
              <input type="number" step="0.1" name="daily_usage_mins" value={formData.daily_usage_mins} onChange={handleChange} className="form-input" />
            </div>

            <div className="form-group">
              <label>Support Ticket Status</label>
              <select name="last_support_ticket" value={formData.last_support_ticket} onChange={handleChange} className="form-input">
                <option value={0}>Resolved (0)</option>
                <option value={1}>Open/Escalated (1)</option>
                <option value={2}>No Tickets (2)</option>
              </select>
            </div>

            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? <><Loader2 className="spinner" size={18} style={{ marginRight: 8, verticalAlign: 'middle' }}/> Analyzing...</> : 'Analyze Churn Risk'}
            </button>
          </form>
          
          {error && <div style={{ color: 'var(--accent-rose)', marginTop: 16, textAlign: 'center' }}>{error}</div>}
        </motion.div>

        {/* Right Column: Results & Explainability */}
        <motion.div 
          className="glass-card"
          initial={{ opacity: 0, x: 20 }} 
          animate={{ opacity: 1, x: 0 }} 
          transition={{ delay: 0.3 }}
        >
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
                <h3 style={{ color: 'var(--text-muted)', fontSize: '1rem', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  Risk Score ({result.customer_id})
                </h3>
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
              </div>

              <div style={{ marginTop: 32 }}>
                <h3 style={{ marginBottom: 8 }}>SHAP Explainability (Why?)</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: 16 }}>
                  How each feature contributed to this specific customer's churn risk score. Red increases risk, blue decreases risk.
                </p>
                
                <div className="shap-chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={shapData} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" horizontal={false} />
                      <XAxis type="number" stroke="var(--text-muted)" />
                      <YAxis dataKey="name" type="category" stroke="var(--text-muted)" width={120} tick={{ fontSize: 12 }} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.9)', borderColor: 'var(--border-color)', borderRadius: '8px' }}
                        formatter={(value) => [value.toFixed(4), "SHAP Impact"]}
                      />
                      <Bar dataKey="impact" radius={[0, 4, 4, 0]}>
                        {shapData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.isPositive ? 'var(--accent-rose)' : 'var(--accent-cyan)'} />
                        ))}
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

export default App;
