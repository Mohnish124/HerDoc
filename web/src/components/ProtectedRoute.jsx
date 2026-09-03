import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ children, requiredRole }) {
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

  if (requiredRole && user?.role !== requiredRole) {
    return (
      <div className="forbidden-card">
        <div className="forbidden-icon">🔒</div>
        <h2>Access Restricted</h2>
        <p>You do not have administrator permissions to access this management area.</p>
        <p className="user-role-notice">
          Your current role is: <strong>{user?.role?.toUpperCase()}</strong>
        </p>
        <a href="/dashboard" className="btn btn-primary">Return to Triage Dashboard</a>
      </div>
    );
  }

  return children;
}
