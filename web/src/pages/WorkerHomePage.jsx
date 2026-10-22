import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import EmergencyNotice from '../components/EmergencyNotice';
import { useAuth } from '../context/AuthContext';
import { RISK_ACTIONS, fetchLatestReviews, latestRisk, listMyPatients, listVisits, registerPatient } from '../api/worker';

const EMPTY_FORM = { name: '', age: '', village: '', edd: '', phone: '' };

// Same rules as the backend PatientCreateRequest and the mobile registration form.
function validatePatient(form) {
  if (!form.name.trim()) return 'Patient name is required.';
  const age = Number(form.age);
  if (!Number.isInteger(age) || age < 1 || age > 120) return 'Age must be a whole number between 1 and 120.';
  if (!form.village.trim()) return 'Village is required.';
  if (!form.edd) return 'Expected delivery date (EDD) is required.';
  const phone = form.phone.trim();
  if (phone && (phone.length < 7 || phone.length > 32 || !/^[0-9+()\-. ]+$/.test(phone))) {
    return 'Phone number must be 7–32 digits (or leave it empty).';
  }
  return '';
}

export function RiskBadge({ level }) {
  if (!level) return <span className="risk-badge risk-badge-none">No visits yet</span>;
  return <span className={`risk-badge risk-badge-${level}`}>{level.toUpperCase()}</span>;
}

export function ReviewBadge({ review }) {
  if (!review) return <span className="review-badge review-badge-pending">Awaiting doctor review</span>;
  const status = review.status || 'pending';
  const variant = ['referred', 'reviewed'].includes(status) ? status : 'pending';
  return <span className={`review-badge review-badge-${variant}`}>Doctor: {status}</span>;
}

export default function WorkerHomePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const [patients, reviews] = await Promise.all([listMyPatients(), fetchLatestReviews()]);
      const withVisits = await Promise.all(
        patients.map(async (patient) => {
          const visits = await listVisits(patient.id);
          return { patient, latestVisit: visits[0] || null, review: reviews[patient.id] || null };
        }),
      );
      setRows(withVisits);
    } catch (err) {
      setError(err.message || 'Could not load your patients.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleRegister = async (e) => {
    e.preventDefault();
    const problem = validatePatient(form);
    if (problem) {
      setFormError(problem);
      return;
    }
    setIsSaving(true);
    setFormError('');
    try {
      const created = await registerPatient({
        name: form.name.trim(),
        age: form.age,
        village: form.village.trim(),
        edd: form.edd,
        phone: form.phone.trim(),
      });
      navigate(`/worker/patients/${created.id}`, { state: { justRegistered: true } });
    } catch (err) {
      setFormError(err.message || 'Could not register the patient.');
    } finally {
      setIsSaving(false);
    }
  };

  const update = (field) => (e) => setForm((prev) => ({ ...prev, [field]: e.target.value }));
  const redCount = rows.filter((r) => latestRisk(r.latestVisit)?.trend_adjusted_level === 'red').length;
  const yellowCount = rows.filter((r) => latestRisk(r.latestVisit)?.trend_adjusted_level === 'yellow').length;

  return (
    <div className="layout-page">
      <Navbar />
      <main className="main-content">
        <div className="page-header">
          <div>
            <h1 className="page-title">My Patients</h1>
            <p className="page-subtitle">Welcome, {user?.name}. Patients you registered, their latest risk, and doctor reviews.</p>
          </div>
          <div className="page-header-actions">
            <button onClick={load} className="btn-refresh" title="Refresh">🔄 Refresh</button>
            <button onClick={() => { setShowForm((v) => !v); setFormError(''); }} className="btn btn-primary">
              {showForm ? 'Close form' : '+ Register patient'}
            </button>
          </div>
        </div>

        <EmergencyNotice />

        {showForm ? (
          <form className="card-panel worker-form" onSubmit={handleRegister} noValidate>
            <div className="panel-header">
              <h2 className="panel-title">Register a patient</h2>
              <p className="panel-sub">The patient will be linked to your account.</p>
            </div>
            {formError ? <div className="alert-error" role="alert"><span className="alert-icon">⚠️</span><span>{formError}</span></div> : null}
            <div className="worker-form-grid">
              <div className="form-group">
                <label htmlFor="p-name">Full name</label>
                <input id="p-name" className="form-input" value={form.name} onChange={update('name')} maxLength={255} required />
              </div>
              <div className="form-group">
                <label htmlFor="p-age">Age (years)</label>
                <input id="p-age" className="form-input" type="number" inputMode="numeric" min="1" max="120" step="1" value={form.age} onChange={update('age')} required />
              </div>
              <div className="form-group">
                <label htmlFor="p-village">Village</label>
                <input id="p-village" className="form-input" value={form.village} onChange={update('village')} maxLength={255} required />
              </div>
              <div className="form-group">
                <label htmlFor="p-edd">Expected delivery date (EDD)</label>
                <input id="p-edd" className="form-input" type="date" value={form.edd} onChange={update('edd')} required />
              </div>
              <div className="form-group">
                <label htmlFor="p-phone">Phone (optional)</label>
                <input id="p-phone" className="form-input" type="tel" inputMode="tel" value={form.phone} onChange={update('phone')} maxLength={32} />
              </div>
            </div>
            <button type="submit" className="btn btn-primary" disabled={isSaving}>
              {isSaving ? 'Saving…' : 'Register patient'}
            </button>
          </form>
        ) : null}

        {!isLoading && !error && rows.length > 0 ? (
          <div className="metrics-grid">
            <div className="metric-card metric-card-total">
              <span className="metric-label">My Patients</span>
              <span className="metric-value">{rows.length}</span>
            </div>
            <div className="metric-card metric-card-red">
              <span className="metric-label">High Risk (Red)</span>
              <span className="metric-value text-red">{redCount}</span>
              <span className="metric-sub">{RISK_ACTIONS.red}</span>
            </div>
            <div className="metric-card metric-card-yellow">
              <span className="metric-label">Moderate Risk (Yellow)</span>
              <span className="metric-value text-yellow">{yellowCount}</span>
              <span className="metric-sub">{RISK_ACTIONS.yellow}</span>
            </div>
          </div>
        ) : null}

        {isLoading ? (
          <div className="state-card"><div className="spinner"></div><p>Loading your patients…</p></div>
        ) : error ? (
          <div className="state-card">
            <div className="alert-error" role="alert"><span className="alert-icon">⚠️</span><span>{error}</span></div>
            <button onClick={load} className="btn btn-secondary">Try again</button>
          </div>
        ) : rows.length === 0 ? (
          <div className="state-card">
            <p className="empty-state-notice">You have not registered any patients yet.</p>
            <button onClick={() => setShowForm(true)} className="btn btn-primary">+ Register your first patient</button>
          </div>
        ) : (
          <div className="worker-patient-list">
            {rows.map(({ patient, latestVisit, review }) => {
              const risk = latestRisk(latestVisit);
              return (
                <Link key={patient.id} to={`/worker/patients/${patient.id}`} className={`worker-patient-card worker-patient-card-${risk?.trend_adjusted_level || 'none'}`}>
                  <div className="worker-patient-main">
                    <span className="patient-name">{patient.name}</span>
                    <span className="patient-meta">{patient.age} yrs · {patient.village}{patient.edd ? ` · EDD ${patient.edd}` : ''}</span>
                    <span className="patient-meta">
                      {latestVisit ? `Last visit ${latestVisit.visit_date} · BP ${latestVisit.systolic_bp ?? '–'}/${latestVisit.diastolic_bp ?? '–'}` : 'No visits recorded'}
                    </span>
                  </div>
                  <div className="worker-patient-status">
                    <RiskBadge level={risk?.trend_adjusted_level} />
                    {risk ? <span className="metric-sub">{RISK_ACTIONS[risk.trend_adjusted_level]}</span> : null}
                    <ReviewBadge review={review} />
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
