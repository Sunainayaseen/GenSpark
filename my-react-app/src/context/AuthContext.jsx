import { createContext, useContext, useState, useEffect } from 'react';
import { getApiUrl } from '../utils/flaskBase';
import {
  loadAuthSession,
  saveAuthSession,
  clearAuthSession,
  getAuthHeaders,
} from '../utils/authStorage';

const AuthContext = createContext();
const SESSION_CHECK_MS = 8000;

function normalizeUser(raw) {
  if (!raw?.email) return null;
  const email = String(raw.email).trim();
  if (!email) return null;
  return {
    id: raw.id,
    name: raw.name || email.split('@')[0],
    email,
    role: raw.role || 'customer',
    must_change_password: Boolean(raw.must_change_password),
  };
}

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

    const finish = () => {
      if (!cancelled) setAuthReady(true);
    };

    const timeout = setTimeout(finish, SESSION_CHECK_MS);

    (async () => {
      const { user: storedUser, token } = loadAuthSession();

      if (!storedUser?.email) {
        clearTimeout(timeout);
        finish();
        return;
      }

      const normalizedStored = normalizeUser(storedUser);

      if (!token) {
        setUserState(normalizedStored);
        clearTimeout(timeout);
        finish();
        return;
      }

      let serverUser = null;
      try {
        serverUser = await Promise.race([
          fetchSessionUser(token),
          new Promise((resolve) => setTimeout(() => resolve(null), SESSION_CHECK_MS - 500)),
        ]);
      } catch (_) {
        serverUser = null;
      }

      if (cancelled) return;

      if (serverUser) {
        setUserState(serverUser);
        saveAuthSession(serverUser, token);
      } else if (serverUser === false) {
        if (normalizedStored?.must_change_password) {
          setUserState(normalizedStored);
        } else {
          setUserState(null);
          clearAuthSession();
        }
      } else {
        setUserState(normalizedStored);
      }

      clearTimeout(timeout);
      finish();
    })();

    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, []);

  const login = (userOrEmail, passwordOrNull, role = 'buyer') => {
    if (userOrEmail && typeof userOrEmail === 'object' && userOrEmail.email) {
      const { token, ...rest } = userOrEmail;
      const normalized = normalizeUser(rest);
      setUserState(normalized);
      saveAuthSession(normalized, token || null);
      setAuthReady(true);
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
    setAuthReady(true);
  };

  const signup = (name, email, password, role = 'buyer') => {
    login({ name, email, role: role || 'buyer', id: Date.now().toString() });
  };

  const logout = () => {
    setUserState(null);
    clearAuthSession();
    setAuthReady(true);
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
