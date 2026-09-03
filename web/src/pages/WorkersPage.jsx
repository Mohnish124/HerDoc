import React, { useCallback, useEffect, useState } from 'react';
import Navbar from '../components/Navbar';
import { apiFetch } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function WorkersPage() {
  const { user } = useAuth();

  const [workers, setWorkers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');

  // Add Worker Modal State
  const [showAddModal, setShowAddModal] = useState(false);
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [temporaryPin, setTemporaryPin] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [createdWorkerSuccess, setCreatedWorkerSuccess] = useState(null); // { name, phone, temporaryPin }

  // Status update loading state
  const [updatingWorkerId, setUpdatingWorkerId] = useState(null);

  const fetchWorkers = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await apiFetch('/api/workers');
      if (!res.ok) {
        throw new Error('Failed to load field worker directory.');
      }
      const data = await res.json();
      setWorkers(data || []);
    } catch (err) {
      setError(err.message || 'Unable to load worker records.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWorkers();
  }, [fetchWorkers]);

  const handleAddWorker = async (e) => {
    e.preventDefault();
    if (!name.trim() || !phone.trim() || !temporaryPin.trim()) {
      setFormError('All fields are required.');
      return;
    }

    if (temporaryPin.length < 4 || temporaryPin.length > 6) {
      setFormError('Temporary PIN must be 4 to 6 digits.');
      return;
    }

    setIsSubmitting(true);
    setFormError('');

    try {
      const res = await apiFetch('/api/auth/register/worker', {
        method: 'POST',
        body: JSON.stringify({
          name: name.trim(),
          phone: phone.trim(),
          temporary_pin: temporaryPin.trim(),
        }),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.detail || 'Failed to register field worker.');
      }

      setCreatedWorkerSuccess({
        name: name.trim(),
        phone: phone.trim(),
        temporaryPin: temporaryPin.trim(),
      });

      // Clear input fields
      setName('');
      setPhone('');
      setTemporaryPin('');
      await fetchWorkers();
    } catch (err) {
      setFormError(err.message || 'Unable to register worker.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleStatus = async (worker) => {
    const nextStatus = !worker.is_active;
    const confirmMsg = nextStatus
      ? `Reactivate account for ${worker.name}?`
      : `Deactivate account for ${worker.name}? This will revoke their mobile login sessions immediately.`;

    if (!window.confirm(confirmMsg)) return;

    setUpdatingWorkerId(worker.id);
    try {
      const res = await apiFetch(`/api/workers/${worker.id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: nextStatus }),
      });

      if (!res.ok) {
        throw new Error('Failed to update worker status.');
      }

      await fetchWorkers();
    } catch (err) {
      alert(err.message || 'Unable to update worker status.');
    } finally {
      setUpdatingWorkerId(null);
    }
  };

  const filteredWorkers = workers.filter((w) => {
    if (!search.trim()) return true;
    const term = search.toLowerCase();
    return (
      w.name.toLowerCase().includes(term) ||
      (w.phone && w.phone.includes(term)) ||
      (w.facility_name && w.facility_name.toLowerCase().includes(term))
    );
  });

  const activeCount = workers.filter((w) => w.is_active).length;
  const inactiveCount = workers.filter((w) => !w.is_active).length;

  return (
    <div className="layout-page">
      <Navbar />
      <main className="main-content">
        {/* Header */}
        <div className="page-header">
          <div>
            <h1 className="page-title">Field Worker Directory & Onboarding</h1>
            <p className="page-subtitle">
              Manage ASHA / ANM field worker credentials, provision temporary PINs, and control mobile sync access.
            </p>
          </div>
          <div className="header-actions">
            <button
              onClick={() => {
                setCreatedWorkerSuccess(null);
                setFormError('');
                setShowAddModal(true);
              }}
              className="btn btn-primary"
            >
              + Add Field Worker
            </button>
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="metrics-grid">
          <div className="metric-card metric-card-total">
            <span className="metric-label">Total Registered Workers</span>
            <span className="metric-value">{workers.length}</span>
            <span className="metric-sub">Field health agents</span>
          </div>

          <div className="metric-card metric-card-total">
            <span className="metric-label">Active Sync Accounts</span>
            <span className="metric-value text-green">{activeCount}</span>
            <span className="metric-sub">Authorized for offline sync</span>
          </div>

          <div className="metric-card metric-card-yellow">
            <span className="metric-label">Deactivated Accounts</span>
            <span className="metric-value text-yellow">{inactiveCount}</span>
            <span className="metric-sub">Access blocked / revoked</span>
          </div>
        </div>

        {/* Search Bar */}
        <div className="filter-bar">
          <div className="filter-group">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search worker by name, phone number, or facility…"
              className="search-input-field"
            />
          </div>
        </div>

        {/* Table & State Handling */}
        {loading ? (
          <div className="state-card">
            <div className="spinner"></div>
            <p>Loading field worker directory…</p>
          </div>
        ) : null}

        {!loading && error ? (
          <div className="alert-error">
            <span>⚠️ {error}</span>
          </div>
        ) : null}

        {!loading && !error && filteredWorkers.length === 0 ? (
          <div className="placeholder-card">
            <div className="placeholder-icon">👩‍⚕️</div>
            <h2>No Field Workers Found</h2>
            <p>
              {search
                ? 'No workers matched your search criteria.'
                : 'No field workers have been registered in this facility yet. Click "Add Field Worker" to onboard your first ASHA/ANM worker.'}
            </p>
          </div>
        ) : null}

        {!loading && !error && filteredWorkers.length > 0 ? (
          <div className="table-responsive">
            <table className="triage-table">
              <thead>
                <tr>
                  <th>Field Worker</th>
                  <th>Contact Phone</th>
                  <th>Facility</th>
                  <th>Assigned Patients</th>
                  <th>Last Sync Timestamp</th>
                  <th>Account Status</th>
                  <th className="text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredWorkers.map((w) => (
                  <tr key={w.id} className="triage-row">
                    <td>
                      <div className="patient-cell">
                        <span className="patient-name">{w.name}</span>
                        <span className="patient-meta">ID: {w.id.slice(0, 8)}…</span>
                      </div>
                    </td>
                    <td>
                      <span className="worker-phone">{w.phone || '—'}</span>
                    </td>
                    <td>
                      <span className="facility-name">{w.facility_name}</span>
                    </td>
                    <td>
                      <strong>{w.patients_count}</strong> patients
                    </td>
                    <td>
                      <span className="vitals-date">
                        {w.last_sync ? new Date(w.last_sync).toLocaleString() : 'Never synced'}
                      </span>
                    </td>
                    <td>
                      <span
                        className={`status-pill ${
                          w.is_active ? 'status-pill-active' : 'status-pill-inactive'
                        }`}
                      >
                        {w.is_active ? 'Active' : 'Deactivated'}
                      </span>
                    </td>
                    <td className="text-right">
                      <button
                        onClick={() => handleToggleStatus(w)}
                        disabled={updatingWorkerId === w.id}
                        className={`btn ${
                          w.is_active ? 'btn-deactivate' : 'btn-reactivate'
                        }`}
                      >
                        {updatingWorkerId === w.id
                          ? 'Updating…'
                          : w.is_active
                          ? 'Deactivate'
                          : 'Reactivate'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {/* Add Worker Modal */}
        {showAddModal ? (
          <div className="modal-backdrop">
            <div className="modal-card">
              <div className="modal-header">
                <h2>Onboard Field Worker</h2>
                <button
                  onClick={() => setShowAddModal(false)}
                  className="modal-close-btn"
                >
                  ✕
                </button>
              </div>

              {createdWorkerSuccess ? (
                <div className="modal-success-body">
                  <div className="success-pin-box">
                    <span className="success-pin-label">Temporary PIN Created</span>
                    <span className="success-pin-code">{createdWorkerSuccess.temporaryPin}</span>
                    <p className="success-pin-instruction">
                      ⚠️ <strong>Crucial:</strong> Share this temporary PIN with{' '}
                      <strong>{createdWorkerSuccess.name}</strong> (Phone: {createdWorkerSuccess.phone}) now.
                      For security, this PIN is hashed and will <strong>never be shown again</strong>.
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setCreatedWorkerSuccess(null);
                      setShowAddModal(false);
                    }}
                    className="btn btn-primary btn-block"
                  >
                    Done & Close
                  </button>
                </div>
              ) : (
                <form onSubmit={handleAddWorker} className="modal-form">
                  {formError ? (
                    <div className="alert-error">
                      <span>⚠️ {formError}</span>
                    </div>
                  ) : null}

                  <div className="form-group">
                    <label htmlFor="workerName">Full Name</label>
                    <input
                      id="workerName"
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="e.g. Sunita Devi (ASHA)"
                      required
                      className="form-input"
                      autoFocus
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="workerPhone">Mobile Phone Number</label>
                    <input
                      id="workerPhone"
                      type="tel"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="e.g. 9876543210"
                      required
                      className="form-input"
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="workerPin">Temporary PIN (4-6 digits)</label>
                    <input
                      id="workerPin"
                      type="password"
                      maxLength={6}
                      value={temporaryPin}
                      onChange={(e) => setTemporaryPin(e.target.value.replace(/\D/g, ''))}
                      placeholder="e.g. 2468"
                      required
                      className="form-input"
                    />
                    <small className="form-hint">
                      Worker will enter this PIN on mobile to initialize their offline profile.
                    </small>
                  </div>

                  <div className="modal-actions">
                    <button
                      type="button"
                      onClick={() => setShowAddModal(false)}
                      className="btn btn-secondary"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="btn btn-primary"
                    >
                      {isSubmitting ? 'Registering…' : 'Create Worker Account'}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        ) : null}
      </main>
    </div>
  );
}
