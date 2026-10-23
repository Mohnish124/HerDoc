import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { homePathForRole } from '../auth/roles';
import { useI18n } from '../i18n/I18nContext';
import LanguageSelect from './LanguageSelect';

export default function Navbar() {
  const { user, logout } = useAuth();
  const { t } = useI18n();
  const location = useLocation();
  const navigate = useNavigate();
  const isWorker = user?.role === 'worker';

  const handleLogout = async () => {
    await logout();
    // Workers return to the phone + PIN sign-in, in the language they chose.
    navigate(isWorker ? '/login?as=worker' : '/login');
  };

  const isActive = (path) => location.pathname === path;

  // Only the worker view is translated; the doctor/admin portal stays in English.
  return (
    <header className={`navbar-container ${isWorker ? 'navbar-worker' : ''}`}>
      <div className="navbar-content">
        <div className="navbar-left">
          <Link to={homePathForRole(user?.role)} className="brand-logo">
            <span className="brand-icon">🩺</span>
            <div className="brand-titles">
              <span className="brand-name">HerDoc</span>
              <span className="brand-subtitle">{isWorker ? t('nav.subtitle') : 'PHC Clinical Portal'}</span>
            </div>
          </Link>

          <nav className="navbar-nav" aria-label={isWorker ? t('nav.mainLabel') : 'Main navigation'}>
            {isWorker ? (
              <Link
                to="/worker"
                className={`nav-link ${isActive('/worker') ? 'nav-link-active' : ''}`}
                aria-current={isActive('/worker') ? 'page' : undefined}
              >
                {t('nav.myPatients')}
              </Link>
            ) : (
              <>
                <Link
                  to="/dashboard"
                  className={`nav-link ${isActive('/dashboard') ? 'nav-link-active' : ''}`}
                aria-current={isActive('/dashboard') ? 'page' : undefined}
                >
                  Triage Dashboard
                </Link>
                <Link
                  to="/facility"
                  className={`nav-link ${isActive('/facility') ? 'nav-link-active' : ''}`}
                aria-current={isActive('/facility') ? 'page' : undefined}
                >
                  Facility Overview
                </Link>
              </>
            )}
            {user?.role === 'admin' && (
              <Link
                to="/workers"
                className={`nav-link ${isActive('/workers') ? 'nav-link-active' : ''}`}
                aria-current={isActive('/workers') ? 'page' : undefined}
              >
                Worker Management
              </Link>
            )}
          </nav>
        </div>

        <div className="navbar-right">
          {isWorker ? <LanguageSelect className="language-select-compact" /> : null}
          <div className="user-profile-badge">
            <span className="user-avatar-circle">
              {user?.name ? user.name[0].toUpperCase() : 'U'}
            </span>
            <div className="user-meta">
              <span className="user-name">{user?.name || 'User'}</span>
              <span className={`role-tag role-tag-${user?.role || 'doctor'}`}>
                {isWorker ? t('nav.role') : (user?.role || 'doctor').toUpperCase()}
              </span>
            </div>
          </div>

          <button onClick={handleLogout} className="btn-logout" title={isWorker ? t('nav.signOut') : 'Sign out'}>
            {isWorker ? t('nav.signOut') : 'Sign out'}
          </button>
        </div>
      </div>
    </header>
  );
}
