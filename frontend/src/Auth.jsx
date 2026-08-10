import { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Lock, Mail, UserPlus, LogIn } from 'lucide-react';

export default function Auth({ isLogin }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isLogin) {
        // OAuth2 dictates form data format for token endpoint
        const formData = new URLSearchParams();
        formData.append('username', email);
        formData.append('password', password);
        
        const response = await axios.post('http://127.0.0.1:8000/login', formData, {
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
        });
        
        localStorage.setItem('retainai_token', response.data.access_token);
        navigate('/');
      } else {
        await axios.post('http://127.0.0.1:8000/signup', { email, password });
        navigate('/login');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <motion.div 
        className="glass-card" 
        style={{ width: '100%', maxWidth: 400 }}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div style={{ textAlign: 'center', marginBottom: 30 }}>
          <h2 style={{ fontSize: '2rem', marginBottom: 10, color: 'var(--accent-cyan)' }}>
            {isLogin ? 'Welcome Back' : 'Create Account'}
          </h2>
          <p style={{ color: 'var(--text-muted)' }}>
            {isLogin ? 'Sign in to access your dashboard' : 'Join RetainAI to predict churn'}
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label><Mail size={14} style={{ marginRight: 6 }}/>Email Address</label>
            <input 
              type="email" 
              className="form-input" 
              value={email} 
              onChange={(e) => setEmail(e.target.value)} 
              required 
            />
          </div>
          
          <div className="form-group">
            <label><Lock size={14} style={{ marginRight: 6 }}/>Password</label>
            <input 
              type="password" 
              className="form-input" 
              value={password} 
              onChange={(e) => setPassword(e.target.value)} 
              required 
            />
          </div>

          {error && <div style={{ color: 'var(--accent-rose)', fontSize: '0.9rem', marginBottom: 15 }}>{error}</div>}

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Processing...' : (isLogin ? <><LogIn size={18} style={{ marginRight: 8 }}/> Sign In</> : <><UserPlus size={18} style={{ marginRight: 8 }}/> Sign Up</>)}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: 20, fontSize: '0.9rem', color: 'var(--text-muted)' }}>
          {isLogin ? (
            <p>Don't have an account? <span style={{ color: 'var(--accent-cyan)', cursor: 'pointer' }} onClick={() => navigate('/signup')}>Sign up</span></p>
          ) : (
            <p>Already have an account? <span style={{ color: 'var(--accent-cyan)', cursor: 'pointer' }} onClick={() => navigate('/login')}>Sign in</span></p>
          )}
        </div>
      </motion.div>
    </div>
  );
}
