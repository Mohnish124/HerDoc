import React, { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { canVisit, homePathForRole } from '../auth/roles';

// Local development only: production builds replace import.meta.env.DEV with false, so these
// seeded demo identities are dropped from the bundle (the production API also rejects them).
const DEMO_ACCOUNTS = import.meta.env.DEV
  ? [
      { label: '👩‍⚕️ Demo Doctor', method: 'staff', id: 'doctor@herdoc.local', secret: 'DoctorPass!2024' },
      { label: '🛡️ Demo Admin', method: 'staff', id: 'admin@herdoc.local', secret: 'AdminPass!2024' },
      { label: '🧑‍🌾 Demo Worker', method: 'worker', id: '9000000003', secret: '2468' },
    ]
  : [];

export default function LoginPage() {
  const [method, setMethod] = useState('staff');
  const [identifier, setIdentifier] = useState('');
  const [secret, setSecret] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login, loginWorker, user, isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const requestedPath = location.state?.from?.pathname;
  const isWorker = method === 'worker';

  if (!isLoading && isAuthenticated) {
    return <Navigate to={homePathForRole(user?.role)} replace />;
  }

  const switchMethod = (next) => {
    setMethod(next);
    setIdentifier('');
    setSecret('');
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!identifier.trim() || !secret.trim()) {
      setError(isWorker ? 'Please enter your phone number and PIN.' : 'Please enter both email and password.');
      return;
    }

    setIsSubmitting(true);
    setError('');

    try {
      const serverUser = isWorker
        ? await loginWorker(identifier.trim(), secret.trim())
        : await login(identifier.trim(), secret);
      // Route by the role the server authenticated, never by the tab the user picked.
      const target = canVisit(serverUser?.role, requestedPath) ? requestedPath : homePathForRole(serverUser?.role);
      navigate(target, { replace: true });
    } catch (err) {
      setError(err.message || 'Authentication failed.');
      setSecret('');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickFill = (account) => {
    setMethod(account.method);
    setIdentifier(account.id);
    setSecret(account.secret);
    setError('');
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <div className="login-icon">🩺</div>
          <h1 className="login-title">HerDoc Portal</h1>
          <p className="login-subtitle">Primary Health Centre clinical, administrative and field-worker access</p>
        </div>

        <div className="login-method-tabs" role="tablist" aria-label="Sign-in method">
          <button
            type="button"
            role="tab"
            aria-selected={!isWorker}
            className={`login-method-tab ${!isWorker ? 'login-method-tab-active' : ''}`}
            onClick={() => switchMethod('staff')}
          >
            Doctor / Admin
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={isWorker}
            className={`login-method-tab ${isWorker ? 'login-method-tab-active' : ''}`}
            onClick={() => switchMethod('worker')}
          >
            Health Worker
          </button>
        </div>

        {error ? (
          <div className="alert-error" role="alert">
            <span className="alert-icon">⚠️</span>
            <span>{error}</span>
          </div>
        ) : null}

        <form onSubmit={handleSubmit} className="login-form" autoComplete={isWorker ? 'off' : 'on'}>
          <div className="form-group">
            <label htmlFor="identifier">{isWorker ? 'Phone Number' : 'Email Address'}</label>
            <input
              id="identifier"
              type={isWorker ? 'tel' : 'email'}
              inputMode={isWorker ? 'numeric' : 'email'}
              value={identifier}
              onChange={(e) => setIdentifier(isWorker ? e.target.value.replace(/[^0-9+]/g, '') : e.target.value)}
              placeholder={isWorker ? 'Registered mobile number' : 'name@facility.org'}
              autoComplete={isWorker ? 'tel' : 'username'}
              required
              autoFocus
              className="form-input"
            />
          </div>

          <div className="form-group">
            <label htmlFor="secret">{isWorker ? 'PIN' : 'Password'}</label>
            <input
              id="secret"
              type="password"
              inputMode={isWorker ? 'numeric' : undefined}
              maxLength={isWorker ? 6 : undefined}
              value={secret}
              onChange={(e) => setSecret(isWorker ? e.target.value.replace(/[^0-9]/g, '') : e.target.value)}
              placeholder={isWorker ? '4–6 digit PIN' : 'Enter your password'}
              autoComplete={isWorker ? 'off' : 'current-password'}
              required
              className="form-input"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="btn btn-primary btn-block btn-large"
          >
            {isSubmitting ? 'Authenticating…' : isWorker ? 'Sign In as Health Worker' : 'Sign In to Portal'}
          </button>
        </form>

        {import.meta.env.DEV && DEMO_ACCOUNTS.length > 0 ? (
          <div className="demo-credentials-box">
            <p className="demo-title">Quick Demo Login (local development only):</p>
            <div className="demo-buttons">
              {DEMO_ACCOUNTS.map((account) => (
                <button key={account.label} type="button" onClick={() => handleQuickFill(account)} className="btn-demo">
                  {account.label}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        <div className="login-footer">
          <p>
            🔒 Protected by in-memory token security & <code>httpOnly</code> cookies.
          </p>
        </div>
      </div>
    </div>
  );
}
