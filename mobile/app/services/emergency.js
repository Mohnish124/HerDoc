import * as Location from 'expo-location';

import { API_BASE_URL } from '../config';
import { getStoredTokens, refreshWorkerAccessToken } from './auth';

const LOCATION_TIMEOUT_MS = 8000;
// Upper bound on waiting for the server so the worker is told to call directly instead of
// watching a spinner (e.g. while a sleeping free-tier server starts up).
const SOS_REQUEST_TIMEOUT_MS = 30000;
const SOS_UNCONFIRMED_MESSAGE =
  'The server did not confirm the alert, so it may not have been delivered. Please call emergency services directly.';

function withTimeout(promise, ms) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('timeout')), ms);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}

// Returns { latitude, longitude } or null when permission is denied / unavailable.
export async function getCurrentCoordinatesIfAvailable() {
  try {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== 'granted') {
      return null;
    }
    const position = await withTimeout(
      Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }),
      LOCATION_TIMEOUT_MS,
    );
    const { latitude, longitude } = position?.coords || {};
    if (typeof latitude !== 'number' || typeof longitude !== 'number') {
      return null;
    }
    return { latitude, longitude };
  } catch {
    try {
      const last = await Location.getLastKnownPositionAsync();
      if (last?.coords) {
        return { latitude: last.coords.latitude, longitude: last.coords.longitude };
      }
    } catch {
      // ignore
    }
    return null;
  }
}

async function postEmergency(accessToken, body) {
  return fetch(`${API_BASE_URL}/api/emergency`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(body),
  });
}

// Sends the SOS to the HerDoc backend (which relays it to Telegram).
// Throws Error with a user-facing message on failure.
export async function sendEmergencySOS({ coordinates } = {}) {
  const body = coordinates
    ? { latitude: coordinates.latitude, longitude: coordinates.longitude }
    : {};

  let { accessToken } = await getStoredTokens();
  if (!accessToken) {
    accessToken = await refreshWorkerAccessToken();
  }

  let response;
  try {
    response = await withTimeout(postEmergency(accessToken, body), SOS_REQUEST_TIMEOUT_MS);
    if (response.status === 401) {
      accessToken = await refreshWorkerAccessToken();
      response = await withTimeout(postEmergency(accessToken, body), SOS_REQUEST_TIMEOUT_MS);
    }
  } catch (error) {
    if (error?.message === 'timeout') {
      throw new Error(SOS_UNCONFIRMED_MESSAGE);
    }
    throw new Error('No connection to the server. Please call emergency services directly.');
  }

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload?.detail;
    throw new Error(
      typeof detail === 'string' ? detail : 'Emergency alert failed. Please call emergency services directly.',
    );
  }
  // Only report success when the backend confirms Telegram accepted the alert.
  if (payload?.status !== 'sent') {
    throw new Error(SOS_UNCONFIRMED_MESSAGE);
  }
  return payload;
}
