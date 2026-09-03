import React, { useCallback, useEffect, useState } from 'react';
import Navbar from '../components/Navbar';
import { apiFetch } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function FacilityPage() {
  const { user } = useAuth();
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchOverview = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await apiFetch('/api/dashboard/facility-overview');
      if (!res.ok) {
        throw new Error('Failed to load facility overview data.');
      }
      const data = await res.json();
      setOverview(data);
    } catch (err) {
      setError(err.message || 'Unable to retrieve facility operational metrics.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  const totalPatients = overview?.total_patients || 0;
  const redFlags = overview?.active_flags?.red || 0;
  const yellowFlags = overview?.active_flags?.yellow || 0;
  const greenFlags = overview?.active_flags?.green || 0;
  const activeWorkers = overview?.active_workers_last_7_days || 0;

  const redPct = totalPatients > 0 ? Math.round((redFlags / totalPatients) * 100) : 0;
  const yellowPct = totalPatients > 0 ? Math.round((yellowFlags / totalPatients) * 100) : 0;
  const greenPct = totalPatients > 0 ? Math.round((greenFlags / totalPatients) * 100) : 0;

  return (
    <div className="layout-page">
      <Navbar />
      <main className="main-content">
        <div className="page-header">
          <div>
            <h1 className="page-title">Facility Operational Overview</h1>
            <p className="page-subtitle">
              {overview?.facility_name || 'Primary Health Centre'} • Maternal risk distribution and field worker sync activity.
            </p>
          </div>
          <button onClick={fetchOverview} className="btn-refresh">
            🔄 Refresh Metrics
          </button>
        </div>

        {loading ? (
          <div className="state-card">
            <div className="spinner"></div>
            <p>Aggregating facility health indicators…</p>
          </div>
        ) : null}

        {!loading && error ? (
          <div className="alert-error">
            <span>⚠️ {error}</span>
          </div>
        ) : null}

        {!loading && overview ? (
          <>
            {/* Top Indicator Cards */}
            <div className="metrics-grid">
              <div className="metric-card metric-card-total">
                <span className="metric-label">Total Pregnancies Registered</span>
                <span className="metric-value">{totalPatients}</span>
                <span className="metric-sub">Active cohort across all villages</span>
              </div>

              <div className="metric-card metric-card-red">
                <span className="metric-label">High-Risk (Red Flags)</span>
                <span className="metric-value text-red">{redFlags}</span>
                <span className="metric-sub">
                  {redPct}% of patient population
                </span>
              </div>

              <div className="metric-card metric-card-yellow">
                <span className="metric-label">Moderate-Risk (Yellow Flags)</span>
                <span className="metric-value text-yellow">{yellowFlags}</span>
                <span className="metric-sub">
                  {yellowPct}% of patient population
                </span>
              </div>

              <div className="metric-card metric-card-total">
                <span className="metric-label">Active Workers (Last 7 Days)</span>
                <span className="metric-value text-blue">{activeWorkers}</span>
                <span className="metric-sub">Field health workers syncing visits</span>
              </div>
            </div>

            {/* Risk Distribution Breakdown Panel */}
            <div className="card-panel">
              <div className="panel-header">
                <h2 className="panel-title">Maternal Risk Level Distribution</h2>
                <span className="panel-sub">
                  Categorization based on on-device ensemble inference and consecutive-visit trend adjustments.
                </span>
              </div>

              <div className="distribution-progress-bar">
                <div
                  className="bar-segment bar-red"
                  style={{ width: `${redPct}%` }}
                  title={`High Risk (Red): ${redFlags} (${redPct}%)`}
                ></div>
                <div
                  className="bar-segment bar-yellow"
                  style={{ width: `${yellowPct}%` }}
                  title={`Moderate Risk (Yellow): ${yellowFlags} (${yellowPct}%)`}
                ></div>
                <div
                  className="bar-segment bar-green"
                  style={{ width: `${greenPct}%` }}
                  title={`Routine Care (Green): ${greenFlags} (${greenPct}%)`}
                ></div>
              </div>

              <div className="distribution-legend">
                <div className="legend-item">
                  <span className="legend-dot dot-red"></span>
                  <span className="legend-text">High Risk (Red): <strong>{redFlags}</strong> ({redPct}%)</span>
                </div>
                <div className="legend-item">
                  <span className="legend-dot dot-yellow"></span>
                  <span className="legend-text">Moderate Risk (Yellow): <strong>{yellowFlags}</strong> ({yellowPct}%)</span>
                </div>
                <div className="legend-item">
                  <span className="legend-dot dot-green"></span>
                  <span className="legend-text">Low Risk (Green): <strong>{greenFlags}</strong> ({greenPct}%)</span>
                </div>
              </div>
            </div>
          </>
        ) : null}
      </main>
    </div>
  );
}
