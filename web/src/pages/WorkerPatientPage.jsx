import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import EmergencyNotice from '../components/EmergencyNotice';
import { useAuth } from '../context/AuthContext';
import { RISK_ACTIONS, fetchLatestReviews, getPatient, latestRisk, listVisits, newId, recordVisit } from '../api/worker';
import { RiskBadge, ReviewBadge } from './WorkerHomePage';

const EMPTY_VITALS = { systolic_bp: '', diastolic_bp: '', blood_sugar: '', body_temp_c: '', heart_rate: '' };
const INTEGER_FIELDS = ['systolic_bp', 'diastolic_bp', 'blood_sugar', 'heart_rate'];

export default function WorkerPatientPage() {
  const { id } = useParams();
  const location = useLocation();
  const { user } = useAuth();
  const [patient, setPatient] = useState(null);
  const [visits, setVisits] = useState([]);
  const [review, setReview] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [vitals, setVitals] = useState(EMPTY_VITALS);
  const [formError, setFormError] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [result, setResult] = useState(null);
  // One pending submission (ids + classification) is reused on retry so a dropped response cannot duplicate the visit.
  const pendingRef = useRef(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setLoadError('');
    try {
      const [p, v, reviews] = await Promise.all([getPatient(id), listVisits(id), fetchLatestReviews()]);
      setPatient(p);
      setVisits(v);
      setReview(reviews[id] || null);
    } catch (err) {
      setLoadError(err.message || 'Could not load this patient.');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const update = (field) => (e) => {
    pendingRef.current = null; // edited values => a new submission
    setResult(null);
    setVitals((prev) => ({ ...prev, [field]: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isSaving) return;
    setFormError('');
    setResult(null);

    try {
      // Loaded on demand: the shared mobile model bundle is large.
      const { classifyVisit, validateVitals } = await import('../risk/classifyVisit');
      const problem =
        validateVitals(vitals) ||
        (INTEGER_FIELDS.some((f) => !Number.isInteger(Number(vitals[f]))) ? 'BP, blood sugar and heart rate must be whole numbers.' : '');
      if (problem) {
        setFormError(problem);
        return;
      }

      setIsSaving(true);
      if (!pendingRef.current) {
        const now = new Date();
        pendingRef.current = {
          now,
          ids: { visitId: newId(), flagId: newId() },
          classification: classifyVisit({ patientAge: patient?.age, vitals, priorVisits: visits, now }),
        };
      }
      const { now, ids, classification } = pendingRef.current;
      await recordVisit({ patientId: id, workerId: user.id, vitals, classification, ids, now });
      pendingRef.current = null;
      setResult(classification);
      setVitals(EMPTY_VITALS);
      setVisits(await listVisits(id));
    } catch (err) {
      setFormError(`${err.message || 'Could not save the visit.'} Your entries are kept; you can try again.`);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="layout-page"><Navbar /><main className="main-content">
        <div className="state-card"><div className="spinner"></div><p>Loading patient…</p></div>
      </main></div>
    );
  }

  if (loadError) {
    return (
      <div className="layout-page"><Navbar /><main className="main-content">
        <div className="state-card">
          <div className="alert-error" role="alert"><span className="alert-icon">⚠️</span><span>{loadError}</span></div>
          <Link to="/worker" className="btn btn-secondary">Back to my patients</Link>
        </div>
      </main></div>
    );
  }

  const currentRisk = latestRisk(visits[0]);

  return (
    <div className="layout-page">
      <Navbar />
      <main className="main-content">
        <div className="detail-top-nav">
          <Link to="/worker" className="btn btn-secondary">← My patients</Link>
        </div>

        {location.state?.justRegistered ? (
          <div className="alert-success" role="status">Patient registered. Record the first visit below.</div>
        ) : null}

        <div className="card-panel worker-patient-header">
          <div>
            <h1 className="page-title">{patient.name}</h1>
            <p className="page-subtitle">
              {patient.age} yrs · {patient.village}{patient.edd ? ` · EDD ${patient.edd}` : ''}{patient.phone ? ` · ${patient.phone}` : ''}
            </p>
          </div>
          <div className="worker-patient-status">
            <RiskBadge level={currentRisk?.trend_adjusted_level} />
            {currentRisk ? <span className="metric-sub">{RISK_ACTIONS[currentRisk.trend_adjusted_level]}</span> : null}
            <ReviewBadge review={review} />
          </div>
        </div>

        <EmergencyNotice />

        <div className="detail-grid">
          <div className="detail-left-col">
            <div className="card-panel">
              <div className="panel-header">
                <h2 className="panel-title">Doctor review</h2>
              </div>
              {review ? (
                <div>
                  <ReviewBadge review={review} />
                  {review.reviewed_at ? <p className="metric-sub">Reviewed {String(review.reviewed_at).slice(0, 10)}</p> : null}
                  {review.notes ? <p className="review-notes-full">{review.notes}</p> : <p className="metric-sub">No notes.</p>}
                </div>
              ) : (
                <p className="empty-state-notice">No doctor review yet.</p>
              )}
            </div>

            <div className="card-panel">
              <div className="panel-header">
                <h2 className="panel-title">Visit history</h2>
                <p className="panel-sub">{visits.length} visit{visits.length === 1 ? '' : 's'} recorded</p>
              </div>
              {visits.length === 0 ? (
                <p className="empty-state-notice">No visits yet. Record the first visit with the form.</p>
              ) : (
                <div className="visit-history-list">
                  {visits.map((visit) => {
                    const risk = latestRisk(visit);
                    return (
                      <div key={visit.id} className="visit-item-card">
                        <div className="visit-header-row">
                          <span className="visit-date-badge">{visit.visit_date}</span>
                          <RiskBadge level={risk?.trend_adjusted_level} />
                        </div>
                        <p className="metric-sub">
                          BP {visit.systolic_bp ?? '–'}/{visit.diastolic_bp ?? '–'} mmHg · Sugar {visit.blood_sugar ?? '–'} mg/dL ·
                          Temp {visit.body_temp_c ?? '–'} °C · HR {visit.heart_rate ?? '–'} bpm
                        </p>
                        {risk ? <p className="metric-sub">Action: {RISK_ACTIONS[risk.trend_adjusted_level]}</p> : null}
                        {risk?.trend_reason ? <p className="trend-reason-hint">Trend: {risk.trend_reason}</p> : null}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          <form className="card-panel worker-form" onSubmit={handleSubmit} noValidate>
            <div className="panel-header">
              <h2 className="panel-title">Record a visit</h2>
              <p className="panel-sub">Risk is classified with the same model and trend rules as the HerDoc mobile app.</p>
            </div>
            {formError ? <div className="alert-error" role="alert"><span className="alert-icon">⚠️</span><span>{formError}</span></div> : null}
            {result ? (
              <div className={`worker-risk-result worker-risk-result-${result.trend_adjusted_level}`} role="status">
                <RiskBadge level={result.trend_adjusted_level} />
                <strong>{result.action}</strong>
                {result.trend_reason ? <span>Trend: {result.trend_reason}</span> : null}
                <span className="metric-sub">Visit saved.</span>
              </div>
            ) : null}
            {[
              ['systolic_bp', 'Systolic BP (mmHg)', '1'],
              ['diastolic_bp', 'Diastolic BP (mmHg)', '1'],
              ['blood_sugar', 'Blood sugar (mg/dL)', '1'],
              ['body_temp_c', 'Body temperature (°C)', '0.1'],
              ['heart_rate', 'Heart rate (bpm)', '1'],
            ].map(([field, label, step]) => (
              <div className="form-group" key={field}>
                <label htmlFor={`v-${field}`}>{label}</label>
                <input
                  id={`v-${field}`}
                  className="form-input"
                  type="number"
                  inputMode="decimal"
                  step={step}
                  value={vitals[field]}
                  onChange={update(field)}
                  required
                />
              </div>
            ))}
            <button type="submit" className="btn btn-primary btn-block" disabled={isSaving}>
              {isSaving ? 'Classifying and saving…' : 'Classify risk and save visit'}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
