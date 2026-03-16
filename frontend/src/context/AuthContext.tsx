import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import type { ReactNode } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5001';

interface User {
  email: string;
  name: string;
  picture: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  login: () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const popupRef = useRef<Window | null>(null);

  const fetchUser = useCallback(() => {
    return fetch(`${API_BASE}/api/auth/me`, { credentials: 'include' })
      .then(res => (res.ok ? res.json() : null))
      .then(data => setUser(data ?? null))
      .catch(() => setUser(null));
  }, []);

  useEffect(() => {
    fetchUser().finally(() => setLoading(false));
  }, [fetchUser]);

  // Listen for popup completion
  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.data === 'auth_complete') {
        fetchUser();
        popupRef.current = null;
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [fetchUser]);

  const login = useCallback(() => {
    const isMobile = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
    const returnTo = window.location.pathname + window.location.search;

    if (isMobile) {
      // Mobile: full redirect (popups don't work reliably)
      window.location.href = `${API_BASE}/api/auth/google?returnTo=${encodeURIComponent(returnTo)}`;
      return;
    }

    // Desktop: popup flow to preserve page state
    const w = 500;
    const h = 600;
    const left = window.screenX + (window.outerWidth - w) / 2;
    const top = window.screenY + (window.outerHeight - h) / 2;

    const popup = window.open(
      `${API_BASE}/api/auth/google?popup=1`,
      'signin',
      `width=${w},height=${h},left=${left},top=${top},popup=1`,
    );

    if (popup) {
      popupRef.current = popup;
      // Fallback: poll in case postMessage fails (popup blockers, etc.)
      const interval = setInterval(() => {
        if (popup.closed) {
          clearInterval(interval);
          fetchUser();
          popupRef.current = null;
        }
      }, 500);
    } else {
      // Popup blocked — fall back to redirect
      window.location.href = `${API_BASE}/api/auth/google?returnTo=${encodeURIComponent(returnTo)}`;
    }
  }, [fetchUser]);

  const logout = useCallback(async () => {
    await fetch(`${API_BASE}/api/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
