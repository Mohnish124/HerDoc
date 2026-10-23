import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import EmergencyNotice from '../components/EmergencyNotice';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../i18n/I18nContext';
import { errorText } from '../i18n/errors';
import { fetchLatestReviews, getPatient, latestRisk, listVisits, newId, recordVisit } from '../api/worker';
import { ErrorAlert, PatientHeader, ReviewPanel, VisitForm, VisitHistory } from '../components/worker/WorkerViews';

const EMPTY_VITALS = { systolic_bp: '', diastolic_bp: '', blood_sugar: '', body_temp_c: '', heart_rate: '' };
const INTEGER_FIELDS = ['systolic_bp', 'diastolic_bp', 'blood_sugar', 'heart_rate'];

export default function WorkerPatientPage() {
  const { id } = useParams();
  const location = useLocation();
  const { user } = useAuth();
  const { t, lang } = useI18n();
  const [patient, setPatient] = useState(null);
  const [visits, setVisits] = useState([]);
  const [review, setReview] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [vitals, setVitals] = useState(EMPTY_VITALS);
  const [formError, setFormError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [result, setResult] = useState(null);
  // One pending submission (ids + classification) is reused on retry so a dropped response cannot duplicate the visit.
  const pendingRef = useRef(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const [p, v, reviews] = await Promise.all([getPatient(id), listVisits(id), fetchLatestReviews()]);
      setPatient(p);
      setVisits(v);
      setReview(reviews[id] || null);
    } catch (err) {
      setLoadError(err);
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const updateVital = (field, value) => {
    pendingRef.current = null; // edited values => a new submission
    setResult(null);
    setVitals((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isSaving) return;
    setFormError(null);
    setResult(null);

    try {
      // Loaded on demand: the shared mobile model bundle is large.
      const { classifyVisit, validateVitals } = await import('../risk/classifyVisit');
      const problemKey =
        validateVitals(vitals) ||
        (INTEGER_FIELDS.some((f) => !Number.isInteger(Number(vitals[f]))) ? 'vitals.errors.wholeNumbers' : '');
      if (problemKey) {
        setFormError({ key: problemKey });
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
      setFormError({ error: err });
    } finally {
      setIsSaving(false);
    }
  };

  const formErrorText = formError?.key
    ? t(formError.key)
    : formError?.error
      ? `${errorText(t, formError.error, 'visitForm.saveFailed')} ${t('visitForm.retryHint')}`
      : '';

  if (isLoading || loadError) {
    return (
      <div className="layout-page" lang={lang}>
        <Navbar />
        <main className="main-content">
          {isLoading ? (
            <div className="state-card"><div className="spinner"></div><p>{t('patient.loading')}</p></div>
          ) : (
            <div className="state-card">
              <ErrorAlert message={errorText(t, loadError, 'patient.loadError')} />
              <Link to="/worker" className="btn btn-secondary">{t('patient.back')}</Link>
            </div>
          )}
        </main>
      </div>
    );
  }

  return (
    <div className="layout-page" lang={lang}>
      <Navbar />
      <main className="main-content">
        <div className="detail-top-nav">
          <Link to="/worker" className="btn btn-secondary">{t('patient.back')}</Link>
        </div>

        {location.state?.justRegistered ? (
          <div className="alert-success" role="status">{t('patient.registered')}</div>
        ) : null}

        <PatientHeader patient={patient} currentLevel={latestRisk(visits[0])?.trend_adjusted_level} review={review} />

        <EmergencyNotice />

        <div className="detail-grid">
          <div className="detail-left-col">
            <ReviewPanel review={review} />
            <VisitHistory visits={visits} />
          </div>

          <VisitForm vitals={vitals} onChange={updateVital} onSubmit={handleSubmit} error={formErrorText} isSaving={isSaving} result={result} />
        </div>
      </main>
    </div>
  );
}
