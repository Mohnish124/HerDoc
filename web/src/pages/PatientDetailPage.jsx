import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import Navbar from '../components/Navbar';
import { apiFetch } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function PatientDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();

  const [patient, setPatient] = useState(null);
  const [visits, setVisits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Review Form State
  const [reviewStatus, setReviewStatus] = useState('reviewed'); // 'reviewed' | 'referred'
  const [reviewNotes, setReviewNotes] = useState('');
  const [submittingReview, setSubmittingReview] = useState(false);
  const [reviewSuccessMsg, setReviewSuccessMsg] = useState('');
  const [reviewError, setReviewError] = useState('');

  const loadData = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError('');
    try {
      const [patientRes, visitsRes] = await Promise.all([
        apiFetch(`/api/patients/${id}`),
        apiFetch(`/api/patients/${id}/visits`),
      ]);

      if (!patientRes.ok) {
        throw new Error('Failed to load patient profile');
      }
      if (!visitsRes.ok) {
        throw new Error('Failed to load patient visits');
      }

      const patientData = await patientRes.json();
      const visitsData = await visitsRes.json();

      setPatient(patientData);
      setVisits(visitsData || []);
    } catch (err) {
      setError(err.message || 'Unable to retrieve patient information.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSubmitReview = async (e) => {
    e.preventDefault();
    setSubmittingReview(true);
    setReviewSuccessMsg('');
    setReviewError('');

    try {
      const res = await apiFetch('/api/reviews', {
        method: 'POST',
        body: JSON.stringify({
          patient_id: id,
          status: reviewStatus,
          notes: reviewNotes.trim() || null,
        }),
      });

      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload?.detail || 'Failed to submit clinical review');
      }

      setReviewSuccessMsg(
        reviewStatus === 'referred'
          ? '✓ Patient successfully marked as REFERRED. Referral recorded in audit log.'
          : '✓ Patient successfully marked as REVIEWED. Care plan recorded in audit log.'
      );
      await loadData();
    } catch (err) {
      setReviewError(err.message || 'Unable to submit clinical review.');
    } finally {
      setSubmittingReview(false);
    }
  };

  // Prepare chart data (chronological oldest -> newest)
  const chartData = [...visits]
    .sort((a, b) => {
      const tA = new Date(a.visit_date || a.created_locally_at || 0).getTime();
      const tB = new Date(b.visit_date || b.created_locally_at || 0).getTime();
      return tA - tB;
    })
    .map((v, idx) => ({
      visitLabel: `V${idx + 1} (${v.visit_date})`,
      systolic: Number(v.systolic_bp) || null,
      diastolic: Number(v.diastolic_bp) || null,
      bloodSugar: Number(v.blood_sugar) || null,
      heartRate: Number(v.heart_rate) || null,
    }));

  return (
    <div className="layout-page">
      <Navbar />
      <main className="main-content">
        <div className="detail-top-nav">
          <Link to="/dashboard" className="back-link">
            ← Back to Triage Dashboard
          </Link>
        </div>

        {loading ? (
          <div className="state-card">
            <div className="spinner"></div>
            <p>Loading patient clinical records…</p>
          </div>
        ) : null}

        {!loading && error ? (
          <div className="alert-error">
            <span>⚠️ {error}</span>
          </div>
        ) : null}

        {!loading && patient ? (
          <>
            {/* Patient Demographic Summary Card */}
            <div className="patient-profile-header">
              <div className="profile-main">
                <div className="profile-avatar">
                  <span>{patient.name[0].toUpperCase()}</span>
                </div>
                <div>
                  <h1 className="profile-name">{patient.name}</h1>
                  <p className="profile-meta">
                    {patient.age} years old • Village: <strong>{patient.village || 'Not specified'}</strong> • Phone: {patient.phone || '—'}
                  </p>
                </div>
              </div>

              <div className="profile-badges">
                <div className="info-pill">
                  <span className="info-pill-label">Estimated Due Date</span>
                  <span className="info-pill-value">{patient.edd || 'Not recorded'}</span>
                </div>
                <div className="info-pill">
                  <span className="info-pill-label">Assigned ASHA Worker</span>
                  <span className="info-pill-value">{patient.worker?.name || 'Unassigned'}</span>
                </div>
              </div>
            </div>

            <div className="detail-grid">
              {/* Left Column: Trend Chart & Visit History */}
              <div className="detail-left-col">
                {/* Physiological Trend Chart */}
                <div className="card-panel">
                  <div className="panel-header">
                    <h2 className="panel-title">Physiological Vitals Trajectory</h2>
                    <span className="panel-sub">
                      Tracking systolic/diastolic BP (mmHg) and blood sugar (mg/dL) across consecutive visits.
                    </span>
                  </div>

                  {visits.length < 2 ? (
                    <div className="empty-chart-notice">
                      <p>At least 2 visits are required to generate trajectory graphs.</p>
                      <p className="sub">Currently {visits.length} visit recorded.</p>
                    </div>
                  ) : (
                    <div className="chart-container" style={{ width: '100%', height: 320 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 20 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                          <XAxis dataKey="visitLabel" stroke="#64748b" fontSize={12} />
                          <YAxis stroke="#64748b" fontSize={12} domain={['auto', 'auto']} />
                          <Tooltip
                            contentStyle={{
                              backgroundColor: '#ffffff',
                              borderRadius: '8px',
                              border: '1px solid #cbd5e1',
                              boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
                            }}
                          />
                          <Legend wrapperStyle={{ paddingTop: 10 }} />
                          <Line
                            type="monotone"
                            dataKey="systolic"
                            name="Systolic BP (mmHg)"
                            stroke="#2563eb"
                            strokeWidth={3}
                            dot={{ r: 5 }}
                            activeDot={{ r: 7 }}
                          />
                          <Line
                            type="monotone"
                            dataKey="diastolic"
                            name="Diastolic BP (mmHg)"
                            stroke="#0284c7"
                            strokeWidth={2.5}
                            dot={{ r: 4 }}
                          />
                          <Line
                            type="monotone"
                            dataKey="bloodSugar"
                            name="Blood Sugar (mg/dL)"
                            stroke="#ea580c"
                            strokeWidth={2.5}
                            dot={{ r: 4 }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>

                {/* Visit History Log */}
                <div className="card-panel">
                  <div className="panel-header">
                    <h2 className="panel-title">Visit History Log ({visits.length})</h2>
                  </div>

                  {visits.length === 0 ? (
                    <div className="empty-state-notice">
                      <p>No offline visits recorded for this patient yet.</p>
                    </div>
                  ) : (
                    <div className="visit-history-list">
                      {visits.map((visit, index) => {
                        const flag = visit.risk_flags?.[0] || null;
                        const risk = flag?.trend_adjusted_level || flag?.model_risk_level || 'green';
                        const isEscalated = Boolean(flag?.trend_reason);

                        return (
                          <div key={visit.id || index} className="visit-item-card">
                            <div className="visit-header-row">
                              <div>
                                <span className="visit-number">Visit #{visits.length - index}</span>
                                <span className="visit-date-badge">{visit.visit_date}</span>
                              </div>
                              <div className="risk-tag-group">
                                <span className={`risk-badge risk-badge-${risk}`}>
                                  {risk.toUpperCase()} RISK
                                </span>
                                {isEscalated ? (
                                  <span className="trend-escalated-pill">
                                    ↗ Escalated
                                  </span>
                                ) : null}
                              </div>
                            </div>

                            {flag?.trend_reason ? (
                              <div className="trend-alert-snippet">
                                <span>↗ {flag.trend_reason}</span>
                              </div>
                            ) : null}

                            <div className="vitals-matrix">
                              <div className="matrix-box">
                                <span className="m-label">Blood Pressure</span>
                                <span className="m-val">
                                  {visit.systolic_bp != null && visit.diastolic_bp != null
                                    ? `${visit.systolic_bp}/${visit.diastolic_bp} mmHg`
                                    : '—'}
                                </span>
                              </div>
                              <div className="matrix-box">
                                <span className="m-label">Blood Sugar</span>
                                <span className="m-val">
                                  {visit.blood_sugar != null ? `${visit.blood_sugar} mg/dL` : '—'}
                                </span>
                              </div>
                              <div className="matrix-box">
                                <span className="m-label">Temperature</span>
                                <span className="m-val">
                                  {visit.body_temp_c != null ? `${visit.body_temp_c} °C` : '—'}
                                </span>
                              </div>
                              <div className="matrix-box">
                                <span className="m-label">Heart Rate</span>
                                <span className="m-val">
                                  {visit.heart_rate != null ? `${visit.heart_rate} bpm` : '—'}
                                </span>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              {/* Right Column: Doctor Clinical Review Panel */}
              <div className="detail-right-col">
                <div className="card-panel review-sticky-panel">
                  <div className="panel-header">
                    <h2 className="panel-title">Doctor Clinical Review</h2>
                    <span className="panel-sub">
                      Evaluate maternal risk, update care protocol, or order emergency facility referral.
                    </span>
                  </div>

                  {reviewSuccessMsg ? (
                    <div className="alert-success">
                      <span>{reviewSuccessMsg}</span>
                    </div>
                  ) : null}

                  {reviewError ? (
                    <div className="alert-error">
                      <span>⚠️ {reviewError}</span>
                    </div>
                  ) : null}

                  <form onSubmit={handleSubmitReview} className="review-action-form">
                    <div className="form-group">
                      <label className="form-label">Clinical Action Determination</label>
                      <div className="review-radio-group">
                        <label
                          className={`radio-card ${
                            reviewStatus === 'reviewed' ? 'radio-card-active radio-card-reviewed' : ''
                          }`}
                        >
                          <input
                            type="radio"
                            name="reviewStatus"
                            value="reviewed"
                            checked={reviewStatus === 'reviewed'}
                            onChange={(e) => setReviewStatus(e.target.value)}
                          />
                          <div>
                            <span className="radio-title">Mark as Reviewed</span>
                            <span className="radio-desc">Routine follow-up / advised standard antenatal care.</span>
                          </div>
                        </label>

                        <label
                          className={`radio-card ${
                            reviewStatus === 'referred' ? 'radio-card-active radio-card-referred' : ''
                          }`}
                        >
                          <input
                            type="radio"
                            name="reviewStatus"
                            value="referred"
                            checked={reviewStatus === 'referred'}
                            onChange={(e) => setReviewStatus(e.target.value)}
                          />
                          <div>
                            <span className="radio-title">Refer to PHC / Hospital</span>
                            <span className="radio-desc">High risk or sustained worsening requires immediate transport.</span>
                          </div>
                        </label>
                      </div>
                    </div>

                    <div className="form-group">
                      <label htmlFor="reviewNotes" className="form-label">
                        Clinical Instructions & Notes for Field Worker
                      </label>
                      <textarea
                        id="reviewNotes"
                        rows={4}
                        value={reviewNotes}
                        onChange={(e) => setReviewNotes(e.target.value)}
                        placeholder="e.g., Blood pressure elevated across 3 visits. Refer to District Hospital for preeclampsia workup and lab tests immediately."
                        className="form-textarea"
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={submittingReview}
                      className={`btn btn-block btn-large ${
                        reviewStatus === 'referred' ? 'btn-danger-action' : 'btn-primary'
                      }`}
                    >
                      {submittingReview ? 'Recording Review…' : 'Submit Clinical Decision'}
                    </button>
                  </form>
                </div>
              </div>
            </div>
          </>
        ) : null}
      </main>
    </div>
  );
}
