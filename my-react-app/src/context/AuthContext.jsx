import { createContext, useContext, useState, useEffect } from 'react';
import { getApiUrl } from '../utils/flaskBase';
import {
  loadAuthSession,
  saveAuthSession,
  clearAuthSession,
  getAuthHeaders,
} from '../utils/authStorage';

const AuthContext = createContext();

function normalizeUser(raw) {
  if (!raw?.email) return null;
  return {
    id: raw.id,
    name: raw.name || raw.email.split('@')[0],
    email: raw.email,
    role: raw.role || 'customer',
    must_change_password: Boolean(raw.must_change_password),
  };
}

/**
 * Validate session with backend. Returns user, false if token invalid, null if network/skip.
 */
async function fetchSessionUser(token) {
  const headers = getAuthHeaders();
  try {
    const res = await fetch(getApiUrl('/me'), {
      credentials: 'include',
      headers,
    });
    const data = await res.json().catch(() => null);
    if (data?.success && data.user) {
      return normalizeUser(data.user);
    }
    if (token) return false;
    return null;
  } catch (_) {
    return null;
  }
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};

export const AuthProvider = ({ children }) => {
  const initial = loadAuthSession();
  const [user, setUserState] = useState(() => normalizeUser(initial.user));
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const { user: storedUser, token } = loadAuthSession();
      if (!storedUser?.email) {
        if (!cancelled) setAuthReady(true);
        return;
      }

      if (!token) {
        if (!cancelled) setAuthReady(true);
        return;
      }

      const serverUser = await fetchSessionUser(token);
      if (cancelled) return;

      if (serverUser) {
        setUserState(serverUser);
        saveAuthSession(serverUser, token);
      } else if (serverUser === false) {
        setUserState(null);
        clearAuthSession();
      }
      setAuthReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /** Login with API user (+ optional JWT token) or legacy email/password mock. */
  const login = (userOrEmail, passwordOrNull, role = 'buyer') => {
    if (userOrEmail && typeof userOrEmail === 'object' && userOrEmail.email) {
      const { token, ...rest } = userOrEmail;
      const normalized = normalizeUser(rest);
      setUserState(normalized);
      saveAuthSession(normalized, token || null);
      return;
    }
    const normalized = normalizeUser({
      email: userOrEmail,
      name: String(userOrEmail).split('@')[0],
      role: role || 'buyer',
      id: Date.now().toString(),
    });
    setUserState(normalized);
    saveAuthSession(normalized, null);
  };

  const signup = (name, email, password, role = 'buyer') => {
    login({ name, email, role: role || 'buyer', id: Date.now().toString() });
  };

  const logout = () => {
    setUserState(null);
    clearAuthSession();
  };

  const updateUser = (partial) => {
    setUserState((prev) => {
      if (!prev) return null;
      const next = { ...prev, ...partial };
      const { token } = loadAuthSession();
      saveAuthSession(next, token);
      return next;
    });
  };

  const isBuyer = user?.role === 'buyer' || user?.role === 'customer';
  const isVendor = user?.role === 'vendor';
  const isAdmin = user?.role === 'admin';

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        signup,
        logout,
        updateUser,
        authReady,
        isBuyer,
        isVendor,
        isAdmin,
        isLoggedIn: !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
