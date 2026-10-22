import React from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { homePathForRole } from '../auth/roles';

export default function ProtectedRoute({ children, roles }) {
  const { user, isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="loading-screen">
        <div className="spinner"></div>
        <p>Verifying secure session…</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // UI guard only: every API call is still authorized by the backend.
  if (roles && !roles.includes(user?.role)) {
    return (
      <div className="forbidden-card">
        <div className="forbidden-icon">🔒</div>
        <h2>Access Restricted</h2>
        <p>Your account does not have permission to open this page.</p>
        <p className="user-role-notice">
          Your current role is: <strong>{user?.role?.toUpperCase()}</strong>
        </p>
        <Link to={homePathForRole(user?.role)} className="btn btn-primary">Go to my dashboard</Link>
      </div>
    );
  }

  return children;
}
