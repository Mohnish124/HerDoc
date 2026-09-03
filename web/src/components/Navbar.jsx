import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Navbar() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const isActive = (path) => location.pathname === path;

  return (
    <header className="navbar-container">
      <div className="navbar-content">
        <div className="navbar-left">
          <Link to="/dashboard" className="brand-logo">
            <span className="brand-icon">🩺</span>
            <div className="brand-titles">
              <span className="brand-name">HerDoc</span>
              <span className="brand-subtitle">PHC Clinical Portal</span>
            </div>
          </Link>

          <nav className="navbar-nav">
            <Link
              to="/dashboard"
              className={`nav-link ${isActive('/dashboard') ? 'nav-link-active' : ''}`}
            >
              Triage Dashboard
            </Link>
            <Link
              to="/facility"
              className={`nav-link ${isActive('/facility') ? 'nav-link-active' : ''}`}
            >
              Facility Overview
            </Link>
            {user?.role === 'admin' && (
              <Link
                to="/workers"
                className={`nav-link ${isActive('/workers') ? 'nav-link-active' : ''}`}
              >
                Worker Management
              </Link>
            )}
          </nav>
        </div>

        <div className="navbar-right">
          <div className="user-profile-badge">
            <span className="user-avatar-circle">
              {user?.name ? user.name[0].toUpperCase() : 'U'}
            </span>
            <div className="user-meta">
              <span className="user-name">{user?.name || 'User'}</span>
              <span className={`role-tag role-tag-${user?.role || 'doctor'}`}>
                {(user?.role || 'doctor').toUpperCase()}
              </span>
            </div>
          </div>

          <button onClick={handleLogout} className="btn-logout" title="Sign out">
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}
