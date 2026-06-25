import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/auth/whoami/', { credentials: 'include' });
        if (res.ok) {
          const data = await res.json();
          if (data.authenticated) {
            setUser(data.user);
          }
        }
      } catch (e) {
        // ignore
      } finally {
        setChecking(false);
      }
    })();
  }, []);

  const login = useCallback((userData) => {
    setUser(userData);
  }, []);

  const logout = useCallback(async () => {
    const host = window.location.hostname;
    // 双保险：无 domain + 带 domain 各删一次
    document.cookie = 'sessionid=; Max-Age=0; path=/';
    document.cookie = `sessionid=; Max-Age=0; path=/; domain=${host}`;
    document.cookie = 'csrftoken=; Max-Age=0; path=/';
    document.cookie = `csrftoken=; Max-Age=0; path=/; domain=${host}`;
    await fetch('/api/auth/logout/', {
      method: 'POST',
      credentials: 'include',
    }).catch(() => {});
    window.location.href = '/';
  }, []);

  return (
    <AuthContext.Provider value={{ user, checking, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be inside AuthProvider');
  return ctx;
}
