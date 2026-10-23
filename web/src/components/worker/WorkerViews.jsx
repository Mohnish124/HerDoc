/**
 * Presentational building blocks for the health worker screens. They render data passed in as
 * props (no fetching), so each screen can be checked in every language (scripts/check-i18n.mjs).
 * Risk codes and review statuses arrive as backend codes and are only translated for display.
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { REVIEW_STATUSES, RISK_LEVELS } from '../../i18n';
import { useI18n } from '../../i18n/I18nContext';
import { latestRisk } from '../../api/worker';

export function RiskBadge({ level }) {
  const { t } = useI18n();
  if (!RISK_LEVELS.includes(level)) return <span className="risk-badge risk-badge-none">{t('risk.none')}</span>;
  return <span className={`risk-badge risk-badge-${level}`}>{t(`risk.level.${level}`)}</span>;
}

export function RiskAction({ level, as: Tag = 'span', withLabel = false }) {
  const { t } = useI18n();
  if (!RISK_LEVELS.includes(level)) return null;
  const action = t(`risk.action.${level}`);
  return <Tag className="metric-sub">{withLabel ? t('risk.actionLabel', { action }) : action}</Tag>;
}

export function ReviewBadge({ review }) {
  const { t } = useI18n();
  if (!review) return <span className="review-badge review-badge-pending">{t('review.awaiting')}</span>;
  const code = review.status || 'pending';
  const variant = ['referred', 'reviewed'].includes(code) ? code : 'pending';
  const label = REVIEW_STATUSES.includes(code) ? t(`review.statusValue.${code}`) : code;
  return <span className={`review-badge review-badge-${variant}`}>{t('review.status', { status: label })}</span>;
}

export function emptyPatientForm() {
  return { name: '', age: '', village: '', edd: '', phone: '' };
}

// Same rules as the backend PatientCreateRequest. Returns a translation key or ''.
export function validatePatient(form) {
  if (!form.name.trim()) return 'register.errors.name';
  const age = Number(form.age);
  if (!Number.isInteger(age) || age < 1 || age > 120) return 'register.errors.age';
  if (!form.village.trim()) return 'register.errors.village';
  if (!form.edd) return 'register.errors.edd';
  const phone = form.phone.trim();
  if (phone && (phone.length < 7 || phone.length > 32 || !/^[0-9+()\-. ]+$/.test(phone))) return 'register.errors.phone';
  return '';
}

export function ErrorAlert({ message }) {
  if (!message) return null;
  return (
    <div className="alert-error" role="alert">
      <span className="alert-icon">⚠️</span>
      <span>{message}</span>
    </div>
  );
}

export function PatientRegistrationForm({ form, onChange, onSubmit, error, isSaving }) {
  const { t } = useI18n();
  const update = (field) => (e) => onChange({ ...form, [field]: e.target.value });
  return (
    <form className="card-panel worker-form" onSubmit={onSubmit} noValidate>
      <div className="panel-header">
        <h2 className="panel-title">{t('register.title')}</h2>
        <p className="panel-sub">{t('register.subtitle')}</p>
      </div>
      <ErrorAlert message={error} />
      <div className="worker-form-grid">
        <div className="form-group">
          <label htmlFor="p-name">{t('register.name')}</label>
          <input id="p-name" className="form-input" value={form.name} onChange={update('name')} maxLength={255} required />
        </div>
        <div className="form-group">
          <label htmlFor="p-age">{t('register.age')}</label>
          <input id="p-age" className="form-input" type="number" inputMode="numeric" min="1" max="120" step="1" value={form.age} onChange={update('age')} required />
        </div>
        <div className="form-group">
          <label htmlFor="p-village">{t('register.village')}</label>
          <input id="p-village" className="form-input" value={form.village} onChange={update('village')} maxLength={255} required />
        </div>
        <div className="form-group">
          <label htmlFor="p-edd">{t('register.edd')}</label>
          <input id="p-edd" className="form-input" type="date" value={form.edd} onChange={update('edd')} required />
        </div>
        <div className="form-group">
          <label htmlFor="p-phone">{t('register.phone')}</label>
          <input id="p-phone" className="form-input" type="tel" inputMode="tel" value={form.phone} onChange={update('phone')} maxLength={32} />
        </div>
      </div>
      <button type="submit" className="btn btn-primary" disabled={isSaving}>
        {isSaving ? t('register.saving') : t('register.submit')}
      </button>
    </form>
  );
}

export function WorkerMetrics({ rows }) {
  const { t } = useI18n();
  const count = (level) => rows.filter((r) => latestRisk(r.latestVisit)?.trend_adjusted_level === level).length;
  return (
    <div className="metrics-grid">
      <div className="metric-card metric-card-total">
        <span className="metric-label">{t('home.metricPatients')}</span>
        <span className="metric-value">{rows.length}</span>
      </div>
      <div className="metric-card metric-card-red">
        <span className="metric-label">{t('home.metricRed')}</span>
        <span className="metric-value text-red">{count('red')}</span>
        <RiskAction level="red" />
      </div>
      <div className="metric-card metric-card-yellow">
        <span className="metric-label">{t('home.metricYellow')}</span>
        <span className="metric-value text-yellow">{count('yellow')}</span>
        <RiskAction level="yellow" />
      </div>
    </div>
  );
}

function PatientMeta({ patient }) {
  const { t } = useI18n();
  return (
    <>
      {t('home.years', { age: patient.age })} · {patient.village}
      {patient.edd ? ` · ${t('home.edd', { date: patient.edd })}` : ''}
    </>
  );
}

export function WorkerPatientList({ rows }) {
  const { t } = useI18n();
  return (
    <div className="worker-patient-list">
      {rows.map(({ patient, latestVisit, review }) => {
        const level = latestRisk(latestVisit)?.trend_adjusted_level;
        return (
          <Link key={patient.id} to={`/worker/patients/${patient.id}`} className={`worker-patient-card worker-patient-card-${level || 'none'}`}>
            <div className="worker-patient-main">
              <span className="patient-name">{patient.name}</span>
              <span className="patient-meta"><PatientMeta patient={patient} /></span>
              <span className="patient-meta">
                {latestVisit
                  ? t('home.lastVisit', { date: latestVisit.visit_date, sys: latestVisit.systolic_bp ?? '–', dia: latestVisit.diastolic_bp ?? '–' })
                  : t('home.noVisits')}
              </span>
            </div>
            <div className="worker-patient-status">
              <RiskBadge level={level} />
              <RiskAction level={level} />
              <ReviewBadge review={review} />
            </div>
          </Link>
        );
      })}
    </div>
  );
}

export function PatientHeader({ patient, currentLevel, review }) {
  return (
    <div className="card-panel worker-patient-header">
      <div>
        <h1 className="page-title">{patient.name}</h1>
        <p className="page-subtitle">
          <PatientMeta patient={patient} />
          {patient.phone ? ` · ${patient.phone}` : ''}
        </p>
      </div>
      <div className="worker-patient-status">
        <RiskBadge level={currentLevel} />
        <RiskAction level={currentLevel} />
        <ReviewBadge review={review} />
      </div>
    </div>
  );
}

export function ReviewPanel({ review }) {
  const { t } = useI18n();
  return (
    <div className="card-panel">
      <div className="panel-header">
        <h2 className="panel-title">{t('review.title')}</h2>
      </div>
      {review ? (
        <div>
          <ReviewBadge review={review} />
          {review.reviewed_at ? <p className="metric-sub">{t('review.reviewedOn', { date: String(review.reviewed_at).slice(0, 10) })}</p> : null}
          {review.notes ? (
            <>
              <p className="metric-sub">{t('review.notesLabel')}</p>
              {/* Doctor's free-text notes are clinical records: shown exactly as written, never machine-translated. */}
              <p className="review-notes-full" lang="und">{review.notes}</p>
            </>
          ) : (
            <p className="metric-sub">{t('review.noNotes')}</p>
          )}
        </div>
      ) : (
        <p className="empty-state-notice">{t('review.none')}</p>
      )}
    </div>
  );
}

export function VisitHistory({ visits }) {
  const { t, trendReason } = useI18n();
  return (
    <div className="card-panel">
      <div className="panel-header">
        <h2 className="panel-title">{t('visits.title')}</h2>
        <p className="panel-sub">{t(visits.length === 1 ? 'visits.count_one' : 'visits.count_other', { count: visits.length })}</p>
      </div>
      {visits.length === 0 ? (
        <p className="empty-state-notice">{t('visits.empty')}</p>
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
                  {t('visits.vitalsLine', {
                    sys: visit.systolic_bp ?? '–',
                    dia: visit.diastolic_bp ?? '–',
                    sugar: visit.blood_sugar ?? '–',
                    temp: visit.body_temp_c ?? '–',
                    hr: visit.heart_rate ?? '–',
                  })}
                </p>
                <RiskAction level={risk?.trend_adjusted_level} as="p" withLabel />
                {risk?.trend_reason ? <p className="trend-reason-hint">{t('risk.trendLabel', { reason: trendReason(risk.trend_reason) })}</p> : null}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

const VITAL_FIELDS = [
  ['systolic_bp', 'vitals.systolic', '1'],
  ['diastolic_bp', 'vitals.diastolic', '1'],
  ['blood_sugar', 'vitals.sugar', '1'],
  ['body_temp_c', 'vitals.temp', '0.1'],
  ['heart_rate', 'vitals.heartRate', '1'],
];

export function RiskResult({ result }) {
  const { t, trendReason } = useI18n();
  if (!result) return null;
  return (
    <div className={`worker-risk-result worker-risk-result-${result.trend_adjusted_level}`} role="status">
      <RiskBadge level={result.trend_adjusted_level} />
      <RiskAction level={result.trend_adjusted_level} as="strong" />
      {result.trend_reason ? <span>{t('risk.trendLabel', { reason: trendReason(result.trend_reason) })}</span> : null}
      <span className="metric-sub">{t('visitForm.saved')}</span>
    </div>
  );
}

export function VisitForm({ vitals, onChange, onSubmit, error, isSaving, result }) {
  const { t } = useI18n();
  return (
    <form className="card-panel worker-form" onSubmit={onSubmit} noValidate>
      <div className="panel-header">
        <h2 className="panel-title">{t('visitForm.title')}</h2>
        <p className="panel-sub">{t('visitForm.subtitle')}</p>
      </div>
      <ErrorAlert message={error} />
      <RiskResult result={result} />
      {VITAL_FIELDS.map(([field, labelKey, step]) => (
        <div className="form-group" key={field}>
          <label htmlFor={`v-${field}`}>{t(labelKey)}</label>
          <input
            id={`v-${field}`}
            className="form-input"
            type="number"
            inputMode="decimal"
            step={step}
            value={vitals[field]}
            onChange={(e) => onChange(field, e.target.value)}
            required
          />
        </div>
      ))}
      <button type="submit" className="btn btn-primary btn-block" disabled={isSaving}>
        {isSaving ? t('visitForm.saving') : t('visitForm.submit')}
      </button>
    </form>
  );
}
