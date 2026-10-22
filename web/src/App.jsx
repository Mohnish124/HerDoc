import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import PatientDetailPage from './pages/PatientDetailPage';
import WorkersPage from './pages/WorkersPage';
import FacilityPage from './pages/FacilityPage';
import WorkerHomePage from './pages/WorkerHomePage';
import WorkerPatientPage from './pages/WorkerPatientPage';
import { STAFF_ROLES, WORKER_ROLES, homePathForRole } from './auth/roles';

function RoleHome() {
  const { user, isAuthenticated, isLoading } = useAuth();
  if (isLoading) {
    return (
      <div className="loading-screen">
        <div className="spinner"></div>
        <p>Verifying secure session…</p>
      </div>
    );
  }
  return <Navigate to={isAuthenticated ? homePathForRole(user?.role) : '/login'} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public Auth Route */}
          <Route path="/login" element={<LoginPage />} />

          {/* Protected Clinical Routes (doctor / admin) */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute roles={STAFF_ROLES}>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/patients/:id"
            element={
              <ProtectedRoute roles={STAFF_ROLES}>
                <PatientDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/facility"
            element={
              <ProtectedRoute roles={STAFF_ROLES}>
                <FacilityPage />
              </ProtectedRoute>
            }
          />

          {/* Admin-Only Management Route */}
          <Route
            path="/workers"
            element={
              <ProtectedRoute roles={['admin']}>
                <WorkersPage />
              </ProtectedRoute>
            }
          />

          {/* Health Worker Routes */}
          <Route
            path="/worker"
            element={
              <ProtectedRoute roles={WORKER_ROLES}>
                <WorkerHomePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/worker/patients/:id"
            element={
              <ProtectedRoute roles={WORKER_ROLES}>
                <WorkerPatientPage />
              </ProtectedRoute>
            }
          />

          {/* Fallback & Root Redirect: each role lands on its own dashboard */}
          <Route path="/" element={<RoleHome />} />
          <Route path="*" element={<RoleHome />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
