import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from?.pathname || '/dashboard';

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setError('Please enter both email and password.');
      return;
    }

    setIsSubmitting(true);
    setError('');

    try {
      await login(email.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.message || 'Authentication failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickFill = (role) => {
    if (role === 'doctor') {
      setEmail('doctor@herdoc.local');
      setPassword('DoctorPass!2024');
    } else if (role === 'admin') {
      setEmail('admin@herdoc.local');
      setPassword('AdminPass!2024');
    }
    setError('');
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <div className="login-icon">🩺</div>
          <h1 className="login-title">HerDoc Portal</h1>
          <p className="login-subtitle">Primary Health Centre Clinical & Administrative Access</p>
        </div>

        {error ? (
          <div className="alert-error" role="alert">
            <span className="alert-icon">⚠️</span>
            <span>{error}</span>
          </div>
        ) : null}

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="email">Email Address</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. doctor@herdoc.local"
              required
              autoFocus
              className="form-input"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your clinical password"
              required
              className="form-input"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="btn btn-primary btn-block btn-large"
          >
            {isSubmitting ? 'Authenticating…' : 'Sign In to Portal'}
          </button>
        </form>

        <div className="demo-credentials-box">
          <p className="demo-title">Quick Demo Login:</p>
          <div className="demo-buttons">
            <button
              type="button"
              onClick={() => handleQuickFill('doctor')}
              className="btn-demo"
            >
              👩‍⚕️ Demo Doctor
            </button>
            <button
              type="button"
              onClick={() => handleQuickFill('admin')}
              className="btn-demo"
            >
              🛡️ Demo Admin
            </button>
          </div>
        </div>

        <div className="login-footer">
          <p>
            🔒 Protected by in-memory token security & <code>httpOnly</code> cookies.
          </p>
        </div>
      </div>
    </div>
  );
}
