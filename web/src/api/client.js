/**
 * HerDoc Web API Client
 * - Stores access token purely in memory (never localStorage / sessionStorage).
 * - Sends credentials: 'include' so httpOnly refresh cookies are automatically passed.
 * - 401 Interceptor: Catches 401 -> calls /api/auth/refresh -> retries original request once.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

let inMemoryAccessToken = null;
let isRefreshing = false;
let refreshSubscribers = [];

export function getAccessToken() {
  return inMemoryAccessToken;
}

export function setAccessToken(token) {
  inMemoryAccessToken = token || null;
}

function onRefreshed(newAccessToken) {
  refreshSubscribers.forEach((callback) => callback(newAccessToken));
  refreshSubscribers = [];
}

function addRefreshSubscriber(callback) {
  refreshSubscribers.push(callback);
}

/**
 * Silent Refresh helper calling backend /api/auth/refresh with httpOnly cookie.
 */
export async function silentRefreshToken() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({}),
    });

    if (!response.ok) {
      setAccessToken(null);
      return null;
    }

    const data = await response.json();
    const newAccessToken = data.access_token;
    setAccessToken(newAccessToken);
    return data;
  } catch (error) {
    setAccessToken(null);
    return null;
  }
}

/**
 * Unified API fetch wrapper with 401 interception & retry logic.
 */
export async function apiFetch(endpoint, options = {}) {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (inMemoryAccessToken) {
    headers['Authorization'] = `Bearer ${inMemoryAccessToken}`;
  }

  const fetchOptions = {
    ...options,
    headers,
    credentials: 'include',
  };

  let response = await fetch(url, fetchOptions);

  // 401 Interceptor: If unauthorized, attempt silent refresh once and retry
  if (response.status === 401 && !options._isRetry) {
    if (!isRefreshing) {
      isRefreshing = true;
      const refreshResult = await silentRefreshToken();
      isRefreshing = false;

      if (refreshResult?.access_token) {
        onRefreshed(refreshResult.access_token);
        // Retry original request
        return apiFetch(endpoint, {
          ...options,
          _isRetry: true,
        });
      } else {
        onRefreshed(null);
        throw new Error('Unauthorized - Session expired');
      }
    } else {
      // If already refreshing, wait for subscriber callback
      return new Promise((resolve, reject) => {
        addRefreshSubscriber((newToken) => {
          if (!newToken) {
            return reject(new Error('Unauthorized - Session expired'));
          }
          resolve(
            apiFetch(endpoint, {
              ...options,
              _isRetry: true,
            })
          );
        });
      });
    }
  }

  return response;
}
