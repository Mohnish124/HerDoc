import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { apiFetch } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [patients, setPatients] = useState([]);
  const [filters, setFilters] = useState({ facilities: [], workers: [] });
  const [selectedFacility, setSelectedFacility] = useState('');
  const [selectedWorker, setSelectedWorker] = useState('');
  const [selectedRisk, setSelectedRisk] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchFilters = useCallback(async () => {
    try {
      const res = await apiFetch('/api/dashboard/filters');
      if (res.ok) {
        const data = await res.json();
        setFilters(data);
      }
    } catch {
      // Ignore filter load errors
    }
  }, []);

  const fetchFlaggedPatients = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (selectedFacility) params.append('facility_id', selectedFacility);
      if (selectedWorker) params.append('worker_id', selectedWorker);
      if (selectedRisk) params.append('risk_level', selectedRisk);

      const endpoint = `/api/dashboard/flagged${params.toString() ? `?${params.toString()}` : ''}`;
      const res = await apiFetch(endpoint);

      if (!res.ok) {
        throw new Error('Failed to load flagged patients');
      }

      const data = await res.json();
      setPatients(data || []);
    } catch (err) {
      setError(err.message || 'Unable to retrieve triage data.');
    } finally {
      setLoading(false);
    }
  }, [selectedFacility, selectedWorker, selectedRisk]);

  useEffect(() => {
    fetchFilters();
  }, [fetchFilters]);

  useEffect(() => {
    fetchFlaggedPatients();
  }, [fetchFlaggedPatients]);

  const filteredList = patients.filter((p) => {
    if (!search.trim()) return true;
    const term = search.toLowerCase();
    return (
      p.name.toLowerCase().includes(term) ||
      (p.village && p.village.toLowerCase().includes(term)) ||
      (p.worker?.name && p.worker.name.toLowerCase().includes(term))
    );
  });

  const redCount = patients.filter((p) => p.latest_risk?.trend_adjusted_level === 'red').length;
  const yellowCount = patients.filter((p) => p.latest_risk?.trend_adjusted_level === 'yellow').length;
  const pendingReviewCount = patients.filter((p) => !p.review?.status || p.review?.status === 'pending').length;

  return (
    <div className="layout-page">
      <Navbar />
      <main className="main-content">
        {/* Page Top Header */}
        <div className="page-header">
          <div>
            <h1 className="page-title">Maternal Risk Triage Dashboard</h1>
            <p className="page-subtitle">
              Real-time flagged patients prioritized by on-device ML inference and physiological trend escalation.
            </p>
          </div>
          <button onClick={fetchFlaggedPatients} className="btn-refresh" title="Refresh records">
            🔄 Refresh
          </button>
        </div>

        {/* Metric Summary Cards */}
        <div className="metrics-grid">
          <div className="metric-card metric-card-total">
            <span className="metric-label">Total Flagged Cases</span>
            <span className="metric-value">{patients.length}</span>
            <span className="metric-sub">Active pregnancies monitored</span>
          </div>

          <div className="metric-card metric-card-red">
            <span className="metric-label">High Risk (Red)</span>
            <span className="metric-value text-red">{redCount}</span>
            <span className="metric-sub">Immediate 24h PHC referral</span>
          </div>

          <div className="metric-card metric-card-yellow">
            <span className="metric-label">Moderate Risk (Yellow)</span>
            <span className="metric-value text-yellow">{yellowCount}</span>
            <span className="metric-sub">1-Week follow-up recheck</span>
          </div>

          <div className="metric-card metric-card-pending">
            <span className="metric-label">Pending Doctor Action</span>
            <span className="metric-value text-blue">{pendingReviewCount}</span>
            <span className="metric-sub">Awaiting clinical review</span>
          </div>
        </div>

        {/* Filter Controls Bar */}
        <div className="filter-bar">
          <div className="filter-group">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by patient, village, or worker…"
              className="search-input-field"
            />
          </div>

          {user?.role === 'admin' && (
            <div className="filter-group">
              <select
                value={selectedFacility}
                onChange={(e) => setSelectedFacility(e.target.value)}
                className="select-field"
              >
                <option value="">All Facilities</option>
                {filters.facilities.map((f) => (
                  <option key={f.id} value={f.id}>{f.name}</option>
                ))}
              </select>
            </div>
          )}

          <div className="filter-group">
            <select
              value={selectedWorker}
              onChange={(e) => setSelectedWorker(e.target.value)}
              className="select-field"
            >
              <option value="">All Field Workers</option>
              {filters.workers.map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <select
              value={selectedRisk}
              onChange={(e) => setSelectedRisk(e.target.value)}
              className="select-field"
            >
              <option value="">All Risk Levels</option>
              <option value="red">High Risk (Red)</option>
              <option value="yellow">Moderate Risk (Yellow)</option>
              <option value="green">Low Risk (Green)</option>
            </select>
          </div>
        </div>

        {/* Triage Table / State Handlers */}
        {loading ? (
          <div className="state-card">
            <div className="spinner"></div>
            <p>Loading flagged triage patients…</p>
          </div>
        ) : null}

        {!loading && error ? (
          <div className="alert-error">
            <span>⚠️ {error}</span>
          </div>
        ) : null}

        {!loading && !error && filteredList.length === 0 ? (
          <div className="all-clear-card">
            <div className="all-clear-icon">🎉</div>
            <h2>All Clear — No Flagged Patients</h2>
            <p>
              {search || selectedFacility || selectedWorker || selectedRisk
                ? 'No flagged patient records matched your active filter criteria.'
                : 'There are currently no high-risk or moderate-risk maternal cases requiring doctor triage in this facility.'}
            </p>
          </div>
        ) : null}

        {!loading && !error && filteredList.length > 0 ? (
          <div className="table-responsive">
            <table className="triage-table">
              <thead>
                <tr>
                  <th>Triage Priority & Risk</th>
                  <th>Patient Info</th>
                  <th>Assigned Field Worker</th>
                  <th>Latest Vitals Recorded</th>
                  <th>Doctor Review Status</th>
                  <th className="text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredList.map((item) => {
                  const risk = item.latest_risk?.trend_adjusted_level || 'green';
                  const isEscalated = Boolean(item.latest_risk?.trend_reason);
                  const reviewStatus = item.review?.status || 'pending';

                  return (
                    <tr key={item.id} className={`triage-row triage-row-${risk}`}>
                      <td>
                        <div className="risk-cell">
                          <span className={`risk-badge risk-badge-${risk}`}>
                            {risk.toUpperCase()}
                          </span>
                          {isEscalated ? (
                            <span className="trend-escalated-pill" title={item.latest_risk.trend_reason}>
                              ↗ Trend Escalated
                            </span>
                          ) : null}
                          {item.latest_risk?.trend_reason ? (
                            <span className="trend-reason-hint">{item.latest_risk.trend_reason}</span>
                          ) : null}
                        </div>
                      </td>

                      <td>
                        <div className="patient-cell">
                          <span className="patient-name">{item.name}</span>
                          <span className="patient-meta">
                            {item.age} yrs • {item.village || 'Village unknown'}
                          </span>
                          {item.edd ? <span className="patient-edd">EDD: {item.edd}</span> : null}
                        </div>
                      </td>

                      <td>
                        <div className="worker-cell">
                          <span className="worker-name">{item.worker?.name || 'Unassigned'}</span>
                          <span className="worker-phone">{item.worker?.phone || 'No phone'}</span>
                          <span className="facility-name">{item.facility?.name}</span>
                        </div>
                      </td>

                      <td>
                        <div className="vitals-cell">
                          <span className="vitals-date">
                            {item.last_visit?.visit_date || 'Unknown date'}
                          </span>
                          <span className="vitals-bp">
                            BP: <strong>{item.last_visit?.systolic_bp}/{item.last_visit?.diastolic_bp}</strong> mmHg
                          </span>
                          <span className="vitals-sub">
                            BS: {item.last_visit?.blood_sugar} mg/dL • Temp: {item.last_visit?.body_temp_c}°C
                          </span>
                        </div>
                      </td>

                      <td>
                        <div className="review-cell">
                          <span className={`review-badge review-badge-${reviewStatus}`}>
                            {reviewStatus.toUpperCase()}
                          </span>
                          {item.review?.notes ? (
                            <span className="review-notes-preview">"{item.review.notes}"</span>
                          ) : null}
                        </div>
                      </td>

                      <td className="text-right">
                        <button
                          onClick={() => navigate(`/patients/${item.id}`)}
                          className="btn btn-action"
                        >
                          Review & Detail →
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </main>
    </div>
  );
}
