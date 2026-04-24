import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import api from '../api/client';
import { clearCache } from '../api/cache';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Deduplicate /auth/me requests (StrictMode + login flow can trigger multiple calls).
  const meRequestRef = useRef(null);
  const bootstrappedRef = useRef(false);

  const loadMe = useCallback(async () => {
    const token = localStorage.getItem('token');
    if (!token) {
      setUser(null);
      setLoading(false);
      return null;
    }

    if (meRequestRef.current) return meRequestRef.current;

    setLoading(true);
    meRequestRef.current = api
      .get('/auth/me')
      .then((res) => {
        setUser(res.data);
        return res.data;
      })
      .catch(() => {
        localStorage.removeItem('token');
        setUser(null);
        return null;
      })
      .finally(() => {
        meRequestRef.current = null;
        setLoading(false);
      });

    return meRequestRef.current;
  }, []);

  useEffect(() => {
    // In dev StrictMode, effects run twice; ensure we only bootstrap once.
    if (bootstrappedRef.current) return;
    bootstrappedRef.current = true;
    loadMe();
  }, [loadMe]);

  const login = async (identifier, password) => {
    const formData = new URLSearchParams();
    // Backend accepts full email OR username (email local-part).
    // OAuth2 form expects the field name to be `username`.
    formData.append('username', identifier);
    formData.append('password', password);
    
    const { data } = await api.post('/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    localStorage.setItem('token', data.access_token);

    // Single source of truth: profile fetch (deduped).
    await loadMe();
  };

  const register = async (userData) => {
    await api.post('/auth/register', userData);
    await login(userData.username || userData.email, userData.password);
  };

  const logout = () => {
    localStorage.removeItem('token');
    setUser(null);
    clearCache('get|');
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
