import React, { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { canVisit, homePathForRole } from '../auth/roles';
import { useI18n } from '../i18n/I18nContext';
import { errorText } from '../i18n/errors';
import LanguageSelect from '../components/LanguageSelect';

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
  const location = useLocation();
  // `/login?as=worker` opens the health worker sign-in directly (used after a worker signs out).
  const [method, setMethod] = useState(() => (new URLSearchParams(location.search).get('as') === 'worker' ? 'worker' : 'staff'));
  const [identifier, setIdentifier] = useState('');
  const [secret, setSecret] = useState('');
  // Kept as data (not text) so a worker's message re-renders in the selected language.
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login, loginWorker, user, isAuthenticated, isLoading } = useAuth();
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const requestedPath = location.state?.from?.pathname;
  const isWorker = method === 'worker';

  if (!isLoading && isAuthenticated) {
    return <Navigate to={homePathForRole(user?.role)} replace />;
  }

  const switchMethod = (next) => {
    setMethod(next);
    setIdentifier('');
    setSecret('');
    setError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!identifier.trim() || !secret.trim()) {
      setError(isWorker ? { key: 'login.errorMissing' } : { text: 'Please enter both email and password.' });
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const serverUser = isWorker
        ? await loginWorker(identifier.trim(), secret.trim())
        : await login(identifier.trim(), secret);
      // Route by the role the server authenticated, never by the tab the user picked.
      const target = canVisit(serverUser?.role, requestedPath) ? requestedPath : homePathForRole(serverUser?.role);
      navigate(target, { replace: true });
    } catch (err) {
      setError(isWorker ? { error: err } : { text: err.message || 'Authentication failed.' });
      setSecret('');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickFill = (account) => {
    setMethod(account.method);
    setIdentifier(account.id);
    setSecret(account.secret);
    setError(null);
  };

  const errorMessage = error?.key
    ? t(error.key)
    : error?.error
      ? errorText(t, error.error, 'errors.invalidCredentials')
      : error?.text || '';

  return (
    <div className="login-page">
      <div className="login-card" lang={isWorker ? lang : 'en'}>
        <div className="login-header">
          <div className="login-icon">🩺</div>
          <h1 className="login-title">HerDoc Portal</h1>
          <p className="login-subtitle">
            {isWorker ? t('login.subtitleWorker') : 'Primary Health Centre clinical, administrative and field-worker access'}
          </p>
        </div>

        <div className="login-method-tabs" role="tablist" aria-label="Sign-in method">
          <button
            type="button"
            role="tab"
            aria-selected={!isWorker}
            className={`login-method-tab ${!isWorker ? 'login-method-tab-active' : ''}`}
            onClick={() => switchMethod('staff')}
            lang="en"
          >
            Doctor / Admin
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={isWorker}
            className={`login-method-tab ${isWorker ? 'login-method-tab-active' : ''}`}
            onClick={() => switchMethod('worker')}
            lang={lang}
          >
            {t('login.tabWorker')}
          </button>
        </div>

        {isWorker ? <LanguageSelect className="language-select-login" /> : null}

        {errorMessage ? (
          <div className="alert-error" role="alert">
            <span className="alert-icon">⚠️</span>
            <span>{errorMessage}</span>
          </div>
        ) : null}

        <form onSubmit={handleSubmit} className="login-form" autoComplete={isWorker ? 'off' : 'on'}>
          <div className="form-group">
            <label htmlFor="identifier">{isWorker ? t('login.phone') : 'Email Address'}</label>
            <input
              id="identifier"
              type={isWorker ? 'tel' : 'email'}
              inputMode={isWorker ? 'numeric' : 'email'}
              value={identifier}
              onChange={(e) => setIdentifier(isWorker ? e.target.value.replace(/[^0-9+]/g, '') : e.target.value)}
              placeholder={isWorker ? t('login.phonePlaceholder') : 'name@facility.org'}
              autoComplete={isWorker ? 'tel' : 'username'}
              required
              autoFocus
              className="form-input"
            />
          </div>

          <div className="form-group">
            <label htmlFor="secret">{isWorker ? t('login.pin') : 'Password'}</label>
            <input
              id="secret"
              type="password"
              inputMode={isWorker ? 'numeric' : undefined}
              maxLength={isWorker ? 6 : undefined}
              value={secret}
              onChange={(e) => setSecret(isWorker ? e.target.value.replace(/[^0-9]/g, '') : e.target.value)}
              placeholder={isWorker ? t('login.pinPlaceholder') : 'Enter your password'}
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
            {isSubmitting
              ? isWorker ? t('login.submitting') : 'Authenticating…'
              : isWorker ? t('login.submitWorker') : 'Sign In to Portal'}
          </button>
        </form>

        {import.meta.env.DEV && DEMO_ACCOUNTS.length > 0 ? (
          <div className="demo-credentials-box" lang="en">
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
            {isWorker ? `🔒 ${t('login.footerWorker')}` : (
              <>🔒 Protected by in-memory token security & <code>httpOnly</code> cookies.</>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
