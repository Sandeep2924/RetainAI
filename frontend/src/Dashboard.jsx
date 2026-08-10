import { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line
} from 'recharts';
import { 
  Search, AlertTriangle, CheckCircle, Activity, Users, 
  TrendingDown, TrendingUp, LogOut, FileText, ArrowRight 
} from 'lucide-react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';

const MOCK_CUSTOMERS = [
  { id: 'CUST-8832', name: 'Acme Corp', age: 45, login: 2, usage: 12.5, ticket: 1 },
  { id: 'CUST-1049', name: 'Globex Inc', age: 120, login: 2, usage: 5.0, ticket: 1 },
  { id: 'CUST-2911', name: 'Soylent Ltd', age: 300, login: 0, usage: 145.2, ticket: 0 },
  { id: 'CUST-5590', name: 'Initech', age: 14, login: 1, usage: 22.0, ticket: 1 },
];

const MOCK_HISTORY = [
  { month: 'Jan', usage: 120, logins: 20 },
  { month: 'Feb', usage: 110, logins: 18 },
  { month: 'Mar', usage: 80, logins: 12 },
  { month: 'Apr', usage: 45, logins: 5 },
  { month: 'May', usage: 30, logins: 2 },
  { month: 'Jun', usage: 15, logins: 1 },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const token = localStorage.getItem('retainai_token');
  
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCustomer, setActiveCustomer] = useState(MOCK_CUSTOMERS[0]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    // Auto-analyze selected customer
    analyzeCustomer(activeCustomer);
  }, [activeCustomer]);

  const handleLogout = () => {
    localStorage.removeItem('retainai_token');
    navigate('/login');
  };

  const analyzeCustomer = async (customer) => {
    setLoading(true);
    try {
      const payload = {
        customer_id: customer.id,
        account_age_days: customer.age,
        login_frequency: customer.login,
        daily_usage_mins: customer.usage,
        last_support_ticket: customer.ticket
      };
      const response = await axios.post('http://127.0.0.1:8000/predict', payload, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setResult(response.data);
    } catch (err) {
      if (err.response?.status === 401) handleLogout();
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const shapData = result ? Object.entries(result.shap_explanations).map(([key, value]) => ({
    name: key.replace(/_/g, ' '),
    impact: value,
    isPositive: value > 0 
  })).sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact)) : [];

  const getActionRecommendation = (topDriver) => {
    if (!topDriver) return "Review account history for anomalies.";
    if (topDriver === 'Login_Frequency') return "Trigger automated re-engagement email sequence offering a free 1-on-1 strategy session.";
    if (topDriver === 'Daily_Usage_Mins') return "Send feature discovery campaign to highlight unused tools and value-adds.";
    if (topDriver === 'Last_Support_Ticket') return "Escalate open tickets immediately to Level 2 Support for white-glove resolution.";
    if (topDriver === 'Account_Age_Days') return "Offer a long-term loyalty discount or upgrade their plan for free for 3 months.";
    return "Schedule a Customer Success check-in call.";
  };

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--bg-primary)', overflow: 'hidden' }}>
      
      {/* Sidebar: Auto-detected At-Risk Customers */}
      <div style={{ width: 320, background: 'var(--bg-secondary)', borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '24px 20px', borderBottom: '1px solid var(--border-color)' }}>
          <h2 style={{ fontSize: '1.2rem', color: 'white', display: 'flex', alignItems: 'center' }}>
            <Activity size={20} color="var(--accent-cyan)" style={{ marginRight: 10 }} />
            RetainAI Analyst
          </h2>
        </div>
        
        <div style={{ padding: 20 }}>
          <div style={{ position: 'relative', marginBottom: 24 }}>
            <Search size={16} style={{ position: 'absolute', top: 12, left: 12, color: 'var(--text-muted)' }} />
            <input 
              type="text" 
              placeholder="Search customers..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ width: '100%', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-color)', borderRadius: 8, padding: '10px 10px 10px 36px', color: 'white', outline: 'none' }}
            />
          </div>

          <h3 style={{ fontSize: '0.85rem', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 12, letterSpacing: 1 }}>
            ⚠️ Auto-Detected Risk Queue
          </h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {MOCK_CUSTOMERS.filter(c => c.name.toLowerCase().includes(searchQuery.toLowerCase()) || c.id.includes(searchQuery)).map(customer => (
              <div 
                key={customer.id}
                onClick={() => setActiveCustomer(customer)}
                style={{ 
                  padding: 16, borderRadius: 8, cursor: 'pointer',
                  background: activeCustomer.id === customer.id ? 'rgba(56, 189, 248, 0.1)' : 'rgba(255,255,255,0.02)',
                  border: `1px solid ${activeCustomer.id === customer.id ? 'var(--accent-cyan)' : 'var(--border-color)'}`
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, color: 'white' }}>{customer.name}</span>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{customer.id}</span>
                </div>
                <div style={{ fontSize: '0.85rem', color: customer.login > 0 ? 'var(--accent-rose)' : 'var(--text-muted)' }}>
                  {customer.login === 2 ? 'Monthly Active (Low)' : customer.login === 1 ? 'Weekly Active' : 'Daily Active'}
                </div>
              </div>
            ))}
          </div>
        </div>
        
        <div style={{ marginTop: 'auto', padding: 20, borderTop: '1px solid var(--border-color)' }}>
          <button onClick={handleLogout} style={{ width: '100%', background: 'transparent', border: 'none', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
            <LogOut size={16} style={{ marginRight: 8 }} /> Sign Out
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '40px 60px' }}>
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} key={activeCustomer.id}>
          
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 40 }}>
            <div>
              <h1 style={{ fontSize: '2.5rem', margin: 0, color: 'white' }}>{activeCustomer.name}</h1>
              <p style={{ color: 'var(--text-muted)', fontSize: '1.1rem' }}>{activeCustomer.id} • Customer for {activeCustomer.age} days</p>
            </div>
            
            {result && (
              <div style={{ textAlign: 'right', background: 'var(--bg-glass)', padding: '16px 24px', borderRadius: 12, border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Current Churn Risk</div>
                <div style={{ fontSize: '2.5rem', fontWeight: 800, color: result.high_risk ? 'var(--accent-rose)' : 'var(--accent-emerald)' }}>
                  {(result.churn_risk_score * 100).toFixed(1)}%
                </div>
              </div>
            )}
          </div>

          {loading ? (
            <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-muted)' }}>Analyzing live data...</div>
          ) : result ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
              
              {/* SHAP Explanation */}
              <div className="glass-card">
                <h3 style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
                  <Activity size={20} style={{ marginRight: 8, color: 'var(--accent-cyan)' }}/> 
                  Why is this happening? (AI Diagnostics)
                </h3>
                <div style={{ height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={shapData} layout="vertical" margin={{ top: 0, right: 0, left: 30, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={false} />
                      <XAxis type="number" stroke="var(--text-muted)" />
                      <YAxis dataKey="name" type="category" stroke="var(--text-muted)" width={120} tick={{ fontSize: 12 }} />
                      <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid var(--border-color)' }} />
                      <Bar dataKey="impact" radius={[0, 4, 4, 0]}>
                        {shapData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.isPositive ? 'var(--accent-rose)' : 'var(--accent-cyan)'} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Action Plan */}
              <div className="glass-card" style={{ display: 'flex', flexDirection: 'column' }}>
                <h3 style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
                  <AlertTriangle size={20} style={{ marginRight: 8, color: 'var(--accent-amber)' }}/> 
                  Action Plan: What to do next
                </h3>
                
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: 24, borderRadius: 8, border: '1px solid rgba(255,255,255,0.05)', marginBottom: 20 }}>
                  <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: 8 }}>Primary Risk Driver Detected:</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 600, color: 'white', marginBottom: 16 }}>{result.top_driver.replace(/_/g, ' ')}</div>
                  
                  <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: 8 }}>Recommended Action:</div>
                  <div style={{ display: 'flex', alignItems: 'flex-start' }}>
                    <ArrowRight size={18} color="var(--accent-emerald)" style={{ marginRight: 10, marginTop: 2 }} />
                    <span style={{ fontSize: '1.1rem', color: 'var(--text-main)', lineHeight: 1.5 }}>
                      {getActionRecommendation(result.top_driver)}
                    </span>
                  </div>
                </div>
                
                <button className="btn-primary" style={{ marginTop: 'auto' }}>
                  Execute Automated Playbook
                </button>
              </div>

              {/* Historical Usage Graph */}
              <div className="glass-card" style={{ gridColumn: '1 / -1' }}>
                <h3 style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
                  <TrendingDown size={20} style={{ marginRight: 8, color: 'var(--text-muted)' }}/> 
                  6-Month Activity History (Simulated)
                </h3>
                <div style={{ height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={MOCK_HISTORY} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                      <XAxis dataKey="month" stroke="var(--text-muted)" />
                      <YAxis stroke="var(--text-muted)" />
                      <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid var(--border-color)' }} />
                      <Line type="monotone" dataKey="usage" name="Usage Mins" stroke="var(--accent-cyan)" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                      <Line type="monotone" dataKey="logins" name="Total Logins" stroke="var(--accent-indigo)" strokeWidth={3} dot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

            </div>
          ) : null}
        </motion.div>
      </div>
    </div>
  );
}
