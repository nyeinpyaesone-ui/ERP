import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api from '../api/axios';

const AuthContext = createContext(null);

/** Restore the stored session and provide user state and authentication actions. */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    const token = localStorage.getItem('token');
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const res = await api.get('/auth/me');
      setUser(res.data);
    } catch {
      localStorage.removeItem('token');
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  /**
   * Authenticate, store the access token, update user state, and return the user.
   * A full_name property triggers registration first, followed by login using email.
   * Otherwise username takes precedence over email. Request and storage failures
   * reject the promise; a successful registration remains if login fails afterward.
   */
  const login = useCallback(async (credentials) => {
    const isRegister = 'full_name' in credentials;

    let res;
    if (isRegister) {
      // Register uses JSON
      await api.post('/auth/register', {
        email: credentials.email,
        password: credentials.password,
        full_name: credentials.full_name
      });
      // Then login with form data
      res = await api.post(
        '/auth/login',
        new URLSearchParams({
          username: credentials.email,
          password: credentials.password
        }),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
      );
    } else {
      // Login uses form data
      res = await api.post(
        '/auth/login',
        new URLSearchParams({
          username: credentials.username || credentials.email,
          password: credentials.password
        }),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
      );
    }

    const { access_token, user: userData } = res.data;
    localStorage.setItem('token', access_token);
    setUser(userData);
    return userData;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshUser: fetchUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}