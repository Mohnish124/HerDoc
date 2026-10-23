import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import EmergencyNotice from '../components/EmergencyNotice';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../i18n/I18nContext';
import { errorText } from '../i18n/errors';
import { fetchLatestReviews, listMyPatients, listVisits, registerPatient } from '../api/worker';
import {
  ErrorAlert,
  PatientRegistrationForm,
  WorkerMetrics,
  WorkerPatientList,
  emptyPatientForm,
  validatePatient,
} from '../components/worker/WorkerViews';

export default function WorkerHomePage() {
  const { user } = useAuth();
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyPatientForm);
  const [formError, setFormError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
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
      setError(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleRegister = async (e) => {
    e.preventDefault();
    const problemKey = validatePatient(form);
    if (problemKey) {
      setFormError({ key: problemKey });
      return;
    }
    setIsSaving(true);
    setFormError(null);
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
      setFormError({ error: err });
    } finally {
      setIsSaving(false);
    }
  };

  // Errors are kept as keys/objects and translated at render time, so switching language updates them.
  const formErrorText = formError?.key ? t(formError.key) : formError?.error ? errorText(t, formError.error, 'register.errors.failed') : '';

  return (
    <div className="layout-page" lang={lang}>
      <Navbar />
      <main className="main-content">
        <div className="page-header">
          <div>
            <h1 className="page-title">{t('home.title')}</h1>
            <p className="page-subtitle">{t('home.subtitle', { name: user?.name || '' })}</p>
          </div>
          <div className="page-header-actions">
            <button onClick={load} className="btn-refresh">{t('home.refresh')}</button>
            <button onClick={() => { setShowForm((v) => !v); setFormError(null); }} className="btn btn-primary">
              {showForm ? t('home.closeForm') : t('home.register')}
            </button>
          </div>
        </div>

        <EmergencyNotice />

        {showForm ? (
          <PatientRegistrationForm form={form} onChange={setForm} onSubmit={handleRegister} error={formErrorText} isSaving={isSaving} />
        ) : null}

        {!isLoading && !error && rows.length > 0 ? <WorkerMetrics rows={rows} /> : null}

        {isLoading ? (
          <div className="state-card"><div className="spinner"></div><p>{t('home.loading')}</p></div>
        ) : error ? (
          <div className="state-card">
            <ErrorAlert message={errorText(t, error, 'home.loadError')} />
            <button onClick={load} className="btn btn-secondary">{t('home.tryAgain')}</button>
          </div>
        ) : rows.length === 0 ? (
          <div className="state-card">
            <p className="empty-state-notice">{t('home.empty')}</p>
            <button onClick={() => setShowForm(true)} className="btn btn-primary">{t('home.registerFirst')}</button>
          </div>
        ) : (
          <WorkerPatientList rows={rows} />
        )}
      </main>
    </div>
  );
}
