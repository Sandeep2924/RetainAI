import { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line
} from 'recharts';
import { 
  Search, AlertTriangle, CheckCircle, Activity, 
  TrendingDown, LogOut, ArrowRight 
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';

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
  const [liveCustomers, setLiveCustomers] = useState([]);
  const [activeCustomer, setActiveCustomer] = useState(null);

  // Poll for live incoming customers every 2 seconds
  useEffect(() => {
    const fetchLiveEvents = async () => {
      try {
        const response = await axios.get('http://127.0.0.1:8000/recent_events', {
          headers: { Authorization: `Bearer ${token}` }
        });
        
        const events = response.data.events;
        setLiveCustomers(events);
        
        // Auto-select the first customer if none is selected
        if (!activeCustomer && events.length > 0) {
          setActiveCustomer(events[0]);
        }
      } catch (err) {
        if (err.response?.status === 401) handleLogout();
        console.error(err);
      }
    };

    fetchLiveEvents(); // initial fetch
    const interval = setInterval(fetchLiveEvents, 2000);
    return () => clearInterval(interval);
  }, [token, activeCustomer]);

  const handleLogout = () => {
    localStorage.removeItem('retainai_token');
    navigate('/login');
  };

  const getActionRecommendation = (topDriver) => {
    if (!topDriver) return "Review account history for anomalies.";
    if (topDriver === 'Login_Frequency') return "Trigger automated re-engagement email sequence offering a free 1-on-1 strategy session.";
    if (topDriver === 'Daily_Usage_Mins') return "Send feature discovery campaign to highlight unused tools and value-adds.";
    if (topDriver === 'Last_Support_Ticket') return "Escalate open tickets immediately to Level 2 Support for white-glove resolution.";
    if (topDriver === 'Account_Age_Days') return "Offer a long-term loyalty discount or upgrade their plan for free for 3 months.";
    return "Schedule a Customer Success check-in call.";
  };

  // Filter customers by search
  const filteredCustomers = liveCustomers.filter(c => 
    c.customer_id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--bg-primary)', overflow: 'hidden' }}>
      
      {/* Sidebar: Live Stream Feed */}
      <div style={{ width: 350, background: 'var(--bg-secondary)', borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '24px 20px', borderBottom: '1px solid var(--border-color)' }}>
          <h2 style={{ fontSize: '1.2rem', color: 'white', display: 'flex', alignItems: 'center' }}>
            <Activity size={20} color="var(--accent-cyan)" style={{ marginRight: 10 }} />
            Live Analyst Feed
          </h2>
          <p style={{ color: 'var(--accent-emerald)', fontSize: '0.8rem', marginTop: 8, display: 'flex', alignItems: 'center' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-emerald)', marginRight: 6, animation: 'pulse 2s infinite' }}></span>
            Monitoring {liveCustomers.length}/100 streams...
          </p>
        </div>
        
        <div style={{ padding: 20, flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ position: 'relative', marginBottom: 24 }}>
            <Search size={16} style={{ position: 'absolute', top: 12, left: 12, color: 'var(--text-muted)' }} />
            <input 
              type="text" 
              placeholder="Search by Customer ID..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ width: '100%', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-color)', borderRadius: 8, padding: '10px 10px 10px 36px', color: 'white', outline: 'none' }}
            />
          </div>

          <h3 style={{ fontSize: '0.85rem', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 12, letterSpacing: 1 }}>
            Real-Time Pipeline
          </h3>
          
          <div style={{ overflowY: 'auto', flex: 1, paddingRight: 5, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {filteredCustomers.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', textAlign: 'center', marginTop: 20 }}>
                {liveCustomers.length === 0 ? "Awaiting live data stream..." : "No matches found."}
              </div>
            ) : (
              <AnimatePresence>
                {filteredCustomers.map(customer => (
                  <motion.div 
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    key={`${customer.customer_id}-${customer.timestamp}`}
                    onClick={() => setActiveCustomer(customer)}
                    style={{ 
                      padding: 16, borderRadius: 8, cursor: 'pointer',
                      background: activeCustomer?.customer_id === customer.customer_id ? 'rgba(56, 189, 248, 0.1)' : 'rgba(255,255,255,0.02)',
                      border: `1px solid ${activeCustomer?.customer_id === customer.customer_id ? 'var(--accent-cyan)' : 'var(--border-color)'}`,
                      borderLeft: `4px solid ${customer.high_risk ? 'var(--accent-rose)' : 'var(--accent-emerald)'}`
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, color: 'white', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '180px' }}>
                        {customer.customer_id}
                      </span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{customer.timestamp}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.85rem', color: customer.high_risk ? 'var(--accent-rose)' : 'var(--accent-emerald)', fontWeight: 600 }}>
                        {(customer.churn_risk_score * 100).toFixed(1)}% Risk
                      </span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        {customer.top_driver ? customer.top_driver.replace(/_/g, ' ') : 'N/A'}
                      </span>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            )}
          </div>
        </div>
        
        <div style={{ padding: 20, borderTop: '1px solid var(--border-color)' }}>
          <button onClick={handleLogout} style={{ width: '100%', background: 'transparent', border: 'none', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
            <LogOut size={16} style={{ marginRight: 8 }} /> Sign Out
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '40px 60px' }}>
        {activeCustomer ? (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} key={activeCustomer.customer_id}>
            
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 40 }}>
              <div>
                <h1 style={{ fontSize: '2.5rem', margin: 0, color: 'white' }}>{activeCustomer.customer_id}</h1>
                <p style={{ color: 'var(--text-muted)', fontSize: '1.1rem', marginTop: 8 }}>
                  Account Age: {activeCustomer.req_data?.account_age_days} days | 
                  Usage: {activeCustomer.req_data?.daily_usage_mins} mins/day
                </p>
              </div>
              
              <div style={{ textAlign: 'right', background: 'var(--bg-glass)', padding: '16px 24px', borderRadius: 12, border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Calculated Churn Risk</div>
                <div style={{ fontSize: '2.5rem', fontWeight: 800, color: activeCustomer.high_risk ? 'var(--accent-rose)' : 'var(--accent-emerald)' }}>
                  {(activeCustomer.churn_risk_score * 100).toFixed(1)}%
                </div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
              
              {/* SHAP Explanation */}
              <div className="glass-card">
                <h3 style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
                  <Activity size={20} style={{ marginRight: 8, color: 'var(--accent-cyan)' }}/> 
                  Why is this happening? (AI Diagnostics)
                </h3>
                <div style={{ height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart 
                      data={Object.entries(activeCustomer.shap_explanations || {}).map(([k, v]) => ({ name: k.replace(/_/g, ' '), impact: v, isPositive: v > 0 })).sort((a,b) => Math.abs(b.impact) - Math.abs(a.impact))} 
                      layout="vertical" 
                      margin={{ top: 0, right: 0, left: 30, bottom: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={false} />
                      <XAxis type="number" stroke="var(--text-muted)" />
                      <YAxis dataKey="name" type="category" stroke="var(--text-muted)" width={120} tick={{ fontSize: 12 }} />
                      <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid var(--border-color)' }} />
                      <Bar dataKey="impact" radius={[0, 4, 4, 0]}>
                        {Object.entries(activeCustomer.shap_explanations || {}).map((_, i) => (
                          <Cell key={i} fill={Object.values(activeCustomer.shap_explanations)[i] > 0 ? 'var(--accent-rose)' : 'var(--accent-cyan)'} />
                        ))}
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
                
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: 24, borderRadius: 8, border: '1px solid rgba(255,255,255,0.05)', flex: 1, marginBottom: 20 }}>
                  <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: 8 }}>Primary Risk Driver Detected:</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 600, color: 'white', marginBottom: 16 }}>
                    {activeCustomer.top_driver ? activeCustomer.top_driver.replace(/_/g, ' ') : 'N/A'}
                  </div>
                  
                  <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: 8 }}>Recommended Action:</div>
                  <div style={{ display: 'flex', alignItems: 'flex-start' }}>
                    <ArrowRight size={18} color="var(--accent-emerald)" style={{ marginRight: 10, marginTop: 2 }} />
                    <span style={{ fontSize: '1.1rem', color: 'var(--text-main)', lineHeight: 1.5 }}>
                      {getActionRecommendation(activeCustomer.top_driver)}
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
                  6-Month Activity History (User Trends)
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
          </motion.div>
        ) : (
          <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
            <Activity size={64} style={{ opacity: 0.1, marginBottom: 20 }} />
            <h2>Waiting for live stream data...</h2>
            <p>Ensure your Python stream simulator is running.</p>
          </div>
        )}
      </div>
      
      {/* Global CSS for pulse animation */}
      <style>{`
        @keyframes pulse {
          0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
          70% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
          100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }
      `}</style>
    </div>
  );
}
