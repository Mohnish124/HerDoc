import React, { createContext, useContext, useEffect, useState } from 'react';
import { API_BASE_URL, apiFetch, setAccessToken, silentRefreshToken } from '../api/client';

// Exported for rendering checks (scripts/check-i18n.mjs); app code uses AuthProvider/useAuth.
export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Silent session restore on app mount
  useEffect(() => {
    let mounted = true;

    async function initSession() {
      try {
        const result = await silentRefreshToken();
        if (result?.user && mounted) {
          setUser(result.user);
        }
      } catch (err) {
        // No active session
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    }

    initSession();

    return () => {
      mounted = false;
    };
  }, []);

  /**
   * Shared browser login: the access token is kept only in memory (setAccessToken) and the
   * refresh token only in the httpOnly cookie set by the backend. The returned user (and its
   * role) comes from the server, never from what the browser chose.
   */
  const signIn = async (path, body, fallbackMessage) => {
    let response;
    try {
      response = await fetch(`${API_BASE_URL}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body),
      });
    } catch (netErr) {
      throw new Error('Backend server is unreachable. Check your network or API connection.');
    }

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data?.detail || fallbackMessage;
      throw new Error(typeof detail === 'string' ? detail : 'Login failed.');
    }

    const { access_token, user: serverUser } = data;
    setAccessToken(access_token);
    setUser(serverUser);
    return serverUser;
  };

  /** Staff (admin / doctor): email + password. */
  const login = async (email, password) => {
    const normalizedEmail = String(email || '').trim();
    const normalizedPassword = String(password || '').trim();

    if (!normalizedEmail || !normalizedPassword) {
      throw new Error('Email and password are required.');
    }
    return signIn('/api/auth/login/web', { email: normalizedEmail, password: normalizedPassword }, 'Invalid email or password.');
  };

  /** Health worker: phone + PIN, through the browser-specific cookie login. */
  const loginWorker = async (phone, pin) => {
    const normalizedPhone = String(phone || '').trim();
    const normalizedPin = String(pin || '').trim();

    if (!normalizedPhone || !normalizedPin) {
      throw new Error('Phone number and PIN are required.');
    }
    return signIn('/api/auth/login/worker/web', { phone: normalizedPhone, pin: normalizedPin }, 'Invalid phone number or PIN.');
  };

  /**
   * Logout: Clears in-memory token, calls backend logout to revoke token and clear cookie.
   */
  const logout = async () => {
    try {
      await fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({}),
      });
    } catch {
      // Ignore network errors during logout
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  };

  const value = {
    user,
    isAuthenticated: Boolean(user),
    isLoading,
    login,
    loginWorker,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
