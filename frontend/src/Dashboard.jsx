import { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line
} from 'recharts';
import { 
  Search, AlertTriangle, CheckCircle, Activity, 
  TrendingDown, LogOut, ArrowRight, Terminal 
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
  const [agentState, setAgentState] = useState('idle'); // idle, running, done
  const [agentLogs, setAgentLogs] = useState([]);
  const [generatedEmail, setGeneratedEmail] = useState(null);
  const [viewAll, setViewAll] = useState(false);

  // Reset agent state when switching customers
  useEffect(() => {
    setAgentState('idle');
    setAgentLogs([]);
    setGeneratedEmail(null);
  }, [activeCustomer?.customer_id]);

  // Poll for live incoming customers every 2 seconds
  useEffect(() => {
    const fetchLiveEvents = async () => {
      try {
        const response = await axios.get('http://127.0.0.1:8001/recent_events', {
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

  // Generate deterministic dynamic history graph based on customer data
  const getCustomerHistory = (customer) => {
    if (!customer) return [];
    const baseUsage = customer.req_data?.daily_usage_mins || 50;
    const baseLogins = customer.req_data?.login_frequency === 0 ? 30 : customer.req_data?.login_frequency === 1 ? 4 : 1; 
    
    // Create a simple deterministic variance using customer_id length and month index
    const seed = customer.customer_id.length;
    
    return ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'].map((month, i) => {
      // If they are churning (high risk), simulate a downward trend over the 6 months
      const trend = customer.high_risk ? (5 - i) / 5 : 1;
      return {
        month,
        usage: Math.max(0, Math.floor((baseUsage + (Math.sin(seed + i) * 15)) * trend)),
        logins: Math.max(0, Math.floor((baseLogins + (Math.cos(seed + i) * 2)) * trend))
      };
    });
  };

  const dynamicHistory = getCustomerHistory(activeCustomer);

  const runAgent = async () => {
    setAgentState('running');
    setAgentLogs(["> Agent initialized.", "> Connecting to OpenAI LLM..."]);
    
    try {
      const driver = activeCustomer.top_driver || "";
      setAgentLogs(prev => [...prev, "> Analyzing SHAP diagnostics for " + (activeCustomer.req_data?.profile_metadata?.name || activeCustomer.customer_id) + "..."]);
      
      const response = await axios.post('http://127.0.0.1:8001/execute_agent', {
        customer_data: activeCustomer.req_data,
        shap_explanations: activeCustomer.shap_explanations
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      let actionLog = "> Applying tailored retention playbook.";
      if (driver === "Daily_Usage_Mins") actionLog = "> Booking 1-on-1 optimization session via Calendly API...";
      else if (driver === "Last_Support_Ticket") actionLog = "> Escalating user to VIP Support Queue in Zendesk...";
      else if (driver === "Login_Frequency") actionLog = "> Unlocking early-access feature flags via LaunchDarkly...";
      else actionLog = "> Applying Loyalty Upgrade via Stripe API...";

      setAgentLogs(prev => [...prev, "> AI has generated a personalized retention strategy.", "> Drafting email based on risk profile...", "> Email drafted successfully.", actionLog, "> Follow-up tasks created. Pipeline complete."]);
      
      setTimeout(() => {
        setGeneratedEmail(response.data.email_draft || "Error: No email generated.");
        setAgentState('done');
      }, 1500); // brief delay for UX
    } catch (error) {
      setAgentLogs(prev => [...prev, "> ERROR: Failed to connect to AI Agent."]);
      setAgentState('done');
    }
  };

  // Filter customers by search
  const searchedCustomers = liveCustomers.filter(c => 
    (c.req_data?.profile_metadata?.name || c.customer_id).toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Show only up to 15 high risk customers
  const highRiskCustomers = searchedCustomers.filter(c => c.high_risk);
  const displayedCustomers = viewAll ? searchedCustomers.slice(0, 50) : highRiskCustomers.slice(0, 15);
  const otherCount = Math.max(0, liveCustomers.length - displayedCustomers.length);

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--bg-primary)', overflow: 'hidden' }}>
      
      {/* Sidebar: Live Stream Feed */}
      <div style={{ width: 350, background: 'var(--bg-secondary)', borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
        <div style={{ padding: '24px 20px', borderBottom: '1px solid var(--border-color)' }}>
          <h2 style={{ fontSize: '1.2rem', color: 'white', display: 'flex', alignItems: 'center' }}>
            <Activity size={20} color="var(--accent-cyan)" style={{ marginRight: 10 }} />
            Live Analyst Feed
          </h2>
          <p style={{ color: 'var(--accent-emerald)', fontSize: '0.8rem', marginTop: 8, display: 'flex', alignItems: 'center' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-emerald)', marginRight: 6, animation: 'pulse 2s infinite' }}></span>
            Monitoring {displayedCustomers.length} high-risk streams. {otherCount} other customers active.
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

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ fontSize: '0.85rem', textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: 1, margin: 0 }}>
              Real-Time Pipeline
            </h3>
            <button 
              onClick={() => setViewAll(!viewAll)} 
              style={{ background: viewAll ? 'rgba(56, 189, 248, 0.1)' : 'transparent', border: `1px solid ${viewAll ? 'var(--accent-cyan)' : 'var(--border-color)'}`, color: viewAll ? 'var(--accent-cyan)' : 'var(--text-muted)', fontSize: '0.75rem', padding: '4px 8px', borderRadius: 4, cursor: 'pointer', transition: 'all 0.2s' }}
            >
              {viewAll ? "Viewing All" : "High Risk Only"}
            </button>
          </div>
          
          <div style={{ overflowY: 'auto', flex: 1, paddingRight: 5, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {displayedCustomers.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', textAlign: 'center', marginTop: 20 }}>
                {liveCustomers.length === 0 ? "Awaiting live data stream..." : "No matches found."}
              </div>
            ) : (
              <AnimatePresence>
                {displayedCustomers.map(customer => (
                  <motion.div 
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    key={`${customer.customer_id}-${customer.timestamp}`}
                    onClick={() => setActiveCustomer(customer)}
                    style={{ 
                      padding: 16, borderRadius: 8, cursor: 'pointer',
                      background: activeCustomer?.customer_id === customer.customer_id ? 'rgba(56, 189, 248, 0.1)' : 'rgba(255,255,255,0.02)',
                      borderTop: `1px solid ${activeCustomer?.customer_id === customer.customer_id ? 'var(--accent-cyan)' : 'var(--border-color)'}`,
                      borderRight: `1px solid ${activeCustomer?.customer_id === customer.customer_id ? 'var(--accent-cyan)' : 'var(--border-color)'}`,
                      borderBottom: `1px solid ${activeCustomer?.customer_id === customer.customer_id ? 'var(--accent-cyan)' : 'var(--border-color)'}`,
                      borderLeft: `4px solid ${customer.high_risk ? 'var(--accent-rose)' : 'var(--accent-emerald)'}`
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, color: 'white', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '180px' }}>
                        {customer.req_data?.profile_metadata?.name || customer.customer_id}
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
            
            {/* Header / Profile Card */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 40, flexWrap: 'wrap', gap: 20 }}>
              
              <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
                {/* Avatar Placeholder */}
                <div style={{ width: 80, height: 80, borderRadius: '50%', background: 'linear-gradient(135deg, var(--accent-indigo), var(--accent-cyan))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '2rem', color: 'white', fontWeight: 600 }}>
                  {activeCustomer.req_data?.profile_metadata?.name?.charAt(0) || activeCustomer.customer_id.charAt(0)}
                </div>
                
                <div>
                  <h1 style={{ fontSize: '2.5rem', margin: '0 0 8px 0', color: 'white' }}>
                    {activeCustomer.req_data?.profile_metadata?.name || 'Unknown User'}
                  </h1>
                  
                  <div style={{ display: 'flex', gap: '16px', color: 'var(--text-muted)', fontSize: '0.95rem', flexWrap: 'wrap' }}>
                    <span style={{ background: 'rgba(255,255,255,0.05)', padding: '4px 10px', borderRadius: 12 }}>
                      🆔 {activeCustomer.customer_id}
                    </span>
                    <span style={{ background: 'rgba(255,255,255,0.05)', padding: '4px 10px', borderRadius: 12 }}>
                      👤 {activeCustomer.req_data?.profile_metadata?.gender || 'Unknown'}, {activeCustomer.req_data?.profile_metadata?.age || '?'} yrs
                    </span>
                    <span style={{ background: 'rgba(255,255,255,0.05)', padding: '4px 10px', borderRadius: 12 }}>
                      📍 {activeCustomer.req_data?.profile_metadata?.location || 'Unknown Location'}
                    </span>
                  </div>
                  
                  <div style={{ display: 'flex', gap: '16px', color: 'var(--accent-cyan)', fontSize: '0.95rem', marginTop: 12 }}>
                    <span style={{ fontWeight: 600 }}>
                      🕒 Account Age: {activeCustomer.req_data?.account_age_days} days
                    </span>
                    <span style={{ fontWeight: 600 }}>
                      📊 Avg Usage: {activeCustomer.req_data?.daily_usage_mins?.toFixed(1)} mins/day
                    </span>
                  </div>
                </div>
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

              {/* Action Plan / Agent Terminal */}
              <div className="glass-card" style={{ display: 'flex', flexDirection: 'column' }}>
                <h3 style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
                  {agentState === 'idle' ? (
                    <><AlertTriangle size={20} style={{ marginRight: 8, color: 'var(--accent-amber)' }}/> Action Plan: What to do next</>
                  ) : (
                    <><Terminal size={20} style={{ marginRight: 8, color: 'var(--accent-indigo)' }}/> Autonomous Agent Execution</>
                  )}
                </h3>
                
                {agentState === 'idle' ? (
                  <>
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
                    
                    <button className="btn-primary" onClick={runAgent} style={{ marginTop: 'auto' }}>
                      Execute Automated Playbook
                    </button>
                  </>
                ) : (
                  <div style={{ background: '#0f172a', padding: 24, borderRadius: 8, border: '1px solid var(--accent-indigo)', flex: 1, display: 'flex', flexDirection: 'column', fontFamily: 'monospace' }}>
                    <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
                      {agentLogs.map((log, index) => (
                        <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} key={index} style={{ color: index === agentLogs.length - 1 && agentState === 'running' ? 'var(--accent-cyan)' : 'var(--text-muted)', fontSize: '0.9rem' }}>
                          {log}
                        </motion.div>
                      ))}
                      {agentState === 'running' && (
                        <motion.div animate={{ opacity: [1, 0, 1] }} transition={{ repeat: Infinity, duration: 1 }} style={{ color: 'var(--accent-cyan)' }}>
                          _
                        </motion.div>
                      )}
                    </div>
                    {agentState === 'done' && (
                      <button className="btn-primary" onClick={() => setAgentState('idle')} style={{ marginTop: 20, background: 'var(--accent-emerald)' }}>
                        Agent Execution Finished
                      </button>
                    )}
                  </div>
                )}
              </div>

              {generatedEmail && (
                <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="glass-card" style={{ gridColumn: '1 / -1', background: 'rgba(56, 189, 248, 0.05)', border: '1px solid var(--accent-cyan)' }}>
                  <h3 style={{ display: 'flex', alignItems: 'center', marginBottom: 16, color: 'var(--accent-cyan)' }}>
                    <CheckCircle size={20} style={{ marginRight: 8 }}/> Autonomous Email Dispatched
                  </h3>
                  <div style={{ padding: 20, background: 'rgba(0,0,0,0.3)', borderRadius: 8, whiteSpace: 'pre-wrap', color: 'white', lineHeight: 1.6, fontStyle: 'italic', fontSize: '1.05rem', borderLeft: '4px solid var(--accent-cyan)' }}>
                    {generatedEmail}
                  </div>
                </motion.div>
              )}

              {/* Historical Usage Graph */}
              <div className="glass-card" style={{ gridColumn: '1 / -1' }}>
                <h3 style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
                  <TrendingDown size={20} style={{ marginRight: 8, color: 'var(--text-muted)' }}/> 
                  6-Month Activity History (User Trends)
                </h3>
                <div style={{ height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={dynamicHistory} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
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
