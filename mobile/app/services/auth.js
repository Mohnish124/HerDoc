import { Platform } from 'react-native';
import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';

import { API_BASE_URL, PIN_HASH_PEPPER, STORAGE_KEYS } from '../config';
import {
  getAuthStateByPhone,
  incrementAuthFailureState,
  lockAuthState,
  resetAuthFailureState,
  upsertAuthState,
} from '../db';

const OFFLINE_MAX_ATTEMPTS = 5;
const OFFLINE_LOCK_MINUTES = 15;

function getWebStorage() {
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    return window.localStorage;
  }
  return null;
}

async function secureSetItem(key, value) {
  if (Platform.OS === 'web') {
    const storage = getWebStorage();
    if (storage) {
      storage.setItem(key, value);
      return;
    }
  }

  await SecureStore.setItemAsync(key, value);
}

async function secureGetItem(key) {
  if (Platform.OS === 'web') {
    const storage = getWebStorage();
    if (storage) {
      return storage.getItem(key);
    }
  }

  return SecureStore.getItemAsync(key);
}

async function secureDeleteItem(key) {
  if (Platform.OS === 'web') {
    const storage = getWebStorage();
    if (storage) {
      storage.removeItem(key);
      return;
    }
  }

  await SecureStore.deleteItemAsync(key);
}

export async function hashPin(phone, pin) {
  const normalizedPhone = String(phone || '').trim();
  const normalizedPin = String(pin || '').trim();
  const input = `${PIN_HASH_PEPPER}:${normalizedPhone}:${normalizedPin}`;
  return Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, input);
}

export async function setTokens({ accessToken, refreshToken }) {
  if (accessToken) {
    await secureSetItem(STORAGE_KEYS.accessToken, accessToken);
  }
  if (refreshToken) {
    await secureSetItem(STORAGE_KEYS.refreshToken, refreshToken);
  }
}

export async function getStoredTokens() {
  const [accessToken, refreshToken] = await Promise.all([
    secureGetItem(STORAGE_KEYS.accessToken),
    secureGetItem(STORAGE_KEYS.refreshToken),
  ]);

  return { accessToken, refreshToken };
}

export async function clearTokens() {
  await Promise.all([
    secureDeleteItem(STORAGE_KEYS.accessToken),
    secureDeleteItem(STORAGE_KEYS.refreshToken),
    secureDeleteItem(STORAGE_KEYS.sessionUser),
  ]);
}

export async function refreshWorkerAccessToken() {
  const { refreshToken } = await getStoredTokens();
  if (!refreshToken) {
    throw new Error('No refresh token available');
  }

  const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload?.detail || 'Token refresh failed');
  }

  const nextAccess = payload.access_token;
  const nextRefresh = payload.refresh_token;
  await setTokens({ accessToken: nextAccess, refreshToken: nextRefresh });
  return nextAccess;
}

export async function setSessionUser(user) {
  if (!user) {
    await secureDeleteItem(STORAGE_KEYS.sessionUser);
    return;
  }
  await secureSetItem(STORAGE_KEYS.sessionUser, JSON.stringify(user));
}

export async function getSessionUser() {
  try {
    const raw = await secureGetItem(STORAGE_KEYS.sessionUser);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function getOfflineLoginStatus(phone) {
  const normalizedPhone = String(phone || '').trim();
  if (!normalizedPhone) {
    return { available: false, remainingAttempts: null, lockedUntil: null, lastLoginAt: null, name: null };
  }
  const record = getAuthStateByPhone(normalizedPhone);
  if (!record || !record.pin_hash) {
    return { available: false, remainingAttempts: null, lockedUntil: null, lastLoginAt: null, name: null };
  }

  const lockedUntil = record.locked_until ? new Date(record.locked_until).getTime() : null;
  const now = Date.now();
  if (lockedUntil && lockedUntil > now) {
    return {
      available: false,
      remainingAttempts: 0,
      lockedUntil: record.locked_until,
      lockRemainingMs: lockedUntil - now,
      lastLoginAt: record.last_login_at,
      name: record.name,
    };
  }

  const attempts = Number(record.failed_attempts || 0);
  return {
    available: true,
    remainingAttempts: Math.max(0, OFFLINE_MAX_ATTEMPTS - attempts),
    lockedUntil: null,
    lastLoginAt: record.last_login_at,
    name: record.name,
  };
}

export function isOfflineLoginAvailable(phone) {
  return getOfflineLoginStatus(phone).available;
}

export async function loginWorkerOnline(phone, pin) {
  const normalizedPhone = String(phone || '').trim();
  const normalizedPin = String(pin || '').trim();

  if (!normalizedPhone || !normalizedPin) {
    throw new Error('Phone and PIN are required.');
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/auth/login/worker`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone: normalizedPhone, pin: normalizedPin }),
    });
  } catch (networkError) {
    throw new Error('Server unreachable. Check your connection or try offline login.');
  }

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload?.detail || 'Login failed';
    throw new Error(typeof detail === 'string' ? detail : 'Login failed');
  }

  const accessToken = payload.access_token;
  const refreshToken = payload.refresh_token;
  const serverUser = payload.user || {};
  const hashedPin = await hashPin(normalizedPhone, normalizedPin);

  await setTokens({ accessToken, refreshToken });

  upsertAuthState({
    phone: normalizedPhone,
    workerId: serverUser.id,
    name: serverUser.name || 'Worker',
    pinHash: hashedPin,
    failedAttempts: 0,
    lockedUntil: null,
    lastLoginAt: new Date().toISOString(),
  });

  const user = {
    id: serverUser.id,
    name: serverUser.name || 'Worker',
    phone: normalizedPhone,
    role: serverUser.role || 'worker',
    facilityId: serverUser.facility_id || null,
  };
  await setSessionUser(user);

  return { user, accessToken, refreshToken };
}

export async function loginWorkerOffline(phone, pin) {
  const normalizedPhone = String(phone || '').trim();
  const normalizedPin = String(pin || '').trim();
  if (!normalizedPhone || !normalizedPin) {
    throw new Error('Phone and PIN are required.');
  }

  const record = getAuthStateByPhone(normalizedPhone);
  if (!record || !record.pin_hash) {
    throw new Error('No prior successful login on this device. Please sign in online first.');
  }

  const now = Date.now();
  const lockedUntil = record.locked_until ? new Date(record.locked_until).getTime() : null;
  if (lockedUntil && lockedUntil > now) {
    const remainingMinutes = Math.max(1, Math.ceil((lockedUntil - now) / 60000));
    throw new Error(`Account locked for ${remainingMinutes} minute(s).`);
  }

  const expectedHash = record.pin_hash;
  const hashedPin = await hashPin(normalizedPhone, normalizedPin);

  if (hashedPin !== expectedHash) {
    const nextAttempts = incrementAuthFailureState(normalizedPhone);
    if (nextAttempts >= OFFLINE_MAX_ATTEMPTS) {
      const lockUntil = new Date(now + OFFLINE_LOCK_MINUTES * 60 * 1000).toISOString();
      lockAuthState(normalizedPhone, lockUntil);
      throw new Error('Account locked for 15 minutes due to repeated failed PIN attempts.');
    }
    throw new Error(`Invalid PIN. ${OFFLINE_MAX_ATTEMPTS - nextAttempts} attempt(s) remaining.`);
  }

  resetAuthFailureState(normalizedPhone);
  const user = {
    id: record.worker_id,
    name: record.name || 'Worker',
    phone: record.phone,
    role: 'worker',
    facilityId: record.facility_id || null,
  };
  await setSessionUser(user);
  return { user };
}

export const OFFLINE_RATE_LIMIT = {
  MAX_ATTEMPTS: OFFLINE_MAX_ATTEMPTS,
  LOCK_MINUTES: OFFLINE_LOCK_MINUTES,
};
