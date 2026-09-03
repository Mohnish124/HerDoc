/**
 * HerDoc Offline Synchronization Engine
 * Connects local SQLite sync_queue with backend POST /api/sync.
 * Idempotent, batch-oriented, safe retry on network drops, with silent token refresh.
 */

import { API_BASE_URL } from '../config';
import {
  applyServerPatientReview,
  getLastSyncedAt,
  getPendingSyncItemsCount,
  getPendingSyncQueueEntries,
  markSyncQueueItemFailed,
  markSyncQueueItemsCompleted,
  setLastSyncedAt,
} from '../db';
import { getStoredTokens, refreshWorkerAccessToken } from './auth';
import { getIsConnected } from './connectivity';

let isSyncInProgress = false;
const syncListeners = new Set();

export function subscribeToSyncState(listener) {
  syncListeners.add(listener);
  return () => syncListeners.delete(listener);
}

function notifySyncListeners(state) {
  for (const listener of syncListeners) {
    try {
      listener(state);
    } catch {
      // Ignore listener errors
    }
  }
}

/**
 * Executes a full synchronization round with the backend.
 *
 * @param {Object} options
 * @param {boolean} options.force - Force sync even if no pending queue items exist (to pull reviews).
 * @returns {Promise<Object>}
 */
export async function synchronizeOfflineData({ force = false } = {}) {
  if (isSyncInProgress) {
    return { status: 'already_syncing' };
  }

  const isConnected = getIsConnected();
  if (!isConnected) {
    return { status: 'offline', pendingCount: getPendingSyncItemsCount() };
  }

  isSyncInProgress = true;
  notifySyncListeners({ isSyncing: true, pendingCount: getPendingSyncItemsCount() });

  try {
    const pendingEntries = getPendingSyncQueueEntries() || [];
    if (!pendingEntries.length && !force) {
      isSyncInProgress = false;
      notifySyncListeners({ isSyncing: false, pendingCount: 0 });
      return { status: 'up_to_date', syncedCount: 0 };
    }

    // Group pending items by entity type
    const patients = [];
    const visits = [];
    const riskFlags = [];
    const queueIdsToSync = [];

    for (const entry of pendingEntries) {
      try {
        const payload = typeof entry.payload === 'string' ? JSON.parse(entry.payload) : entry.payload;
        if (!payload) continue;

        if (entry.entity_type === 'patient') {
          patients.push(payload);
          queueIdsToSync.push(entry.id);
        } else if (entry.entity_type === 'visit') {
          visits.push(payload);
          queueIdsToSync.push(entry.id);
        } else if (entry.entity_type === 'risk_flag') {
          riskFlags.push(payload);
          queueIdsToSync.push(entry.id);
        }
      } catch (parseErr) {
        markSyncQueueItemFailed(entry.id, `JSON parse error: ${parseErr.message}`);
      }
    }

    const lastSyncedAt = getLastSyncedAt();
    const requestBody = {
      patients,
      visits,
      risk_flags: riskFlags,
      last_synced_at: lastSyncedAt,
    };

    let { accessToken } = await getStoredTokens();
    if (!accessToken) {
      accessToken = await refreshWorkerAccessToken();
    }

    let response = await fetch(`${API_BASE_URL}/api/sync`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(requestBody),
    });

    // Handle expired token with silent refresh & single retry
    if (response.status === 401) {
      try {
        accessToken = await refreshWorkerAccessToken();
        response = await fetch(`${API_BASE_URL}/api/sync`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify(requestBody),
        });
      } catch (refreshErr) {
        throw new Error('Authentication expired. Please log in again.');
      }
    }

    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = result?.detail || 'Sync request failed';
      throw new Error(typeof detail === 'string' ? detail : 'Sync failed');
    }

    // Mark successful items in queue as synced
    markSyncQueueItemsCompleted(queueIdsToSync);

    // Apply any server-side reviews received for this worker's patients
    const serverReviews = result?.server_updates?.reviews || result?.reviews || [];
    for (const review of serverReviews) {
      applyServerPatientReview({
        patientId: review.patient_id,
        status: review.status,
        notes: review.notes,
        reviewedAt: review.reviewed_at,
      });
    }

    if (result.sync_timestamp) {
      setLastSyncedAt(result.sync_timestamp);
    }

    const remainingPending = getPendingSyncItemsCount();
    notifySyncListeners({ isSyncing: false, pendingCount: remainingPending, lastSynced: result.sync_timestamp });

    return {
      status: 'success',
      syncedCount: queueIdsToSync.length,
      serverUpdatesCount: serverReviews.length,
      remainingPending,
      syncTimestamp: result.sync_timestamp,
    };
  } catch (error) {
    const pendingEntries = getPendingSyncQueueEntries() || [];
    for (const entry of pendingEntries) {
      markSyncQueueItemFailed(entry.id, error.message || 'Sync error');
    }

    const currentPending = getPendingSyncItemsCount();
    notifySyncListeners({ isSyncing: false, pendingCount: currentPending, error: error.message });

    return {
      status: 'error',
      error: error.message || 'Unknown synchronization error',
      pendingCount: currentPending,
    };
  } finally {
    isSyncInProgress = false;
  }
}
