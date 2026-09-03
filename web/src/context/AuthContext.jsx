import React, { createContext, useContext, useEffect, useState } from 'react';
import { apiFetch, setAccessToken, silentRefreshToken } from '../api/client';

const AuthContext = createContext(null);

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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
   * Log in via email + password.
   * Access token is stored only in memory via setAccessToken.
   * Refresh token is stored in httpOnly cookie set by backend.
   */
  const login = async (email, password) => {
    const normalizedEmail = String(email || '').trim();
    const normalizedPassword = String(password || '').trim();

    if (!normalizedEmail || !normalizedPassword) {
      throw new Error('Email and password are required.');
    }

    let response;
    try {
      response = await fetch(`${API_BASE_URL}/api/auth/login/web`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email: normalizedEmail, password: normalizedPassword }),
      });
    } catch (netErr) {
      throw new Error('Backend server is unreachable. Check your network or API connection.');
    }

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data?.detail || 'Invalid email or password.';
      throw new Error(typeof detail === 'string' ? detail : 'Login failed.');
    }

    const { access_token, user: serverUser } = data;
    setAccessToken(access_token);
    setUser(serverUser);
    return serverUser;
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
