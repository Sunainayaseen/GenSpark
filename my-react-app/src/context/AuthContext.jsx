import { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { getApiUrl } from '../utils/flaskBase';
import { loginWithApi } from '../api/authApi';
import {
  loadAuthSession,
  saveAuthSession,
  clearAuthSession,
  getAuthHeaders,
  publishAuthSession,
  getStoredToken,
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

// Splitting this hook into its own file would require updating every one of
// its consumers' imports across the app; the rule only affects dev Fast
// Refresh, not production behavior.
// eslint-disable-next-line react-refresh/only-export-components
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

      // No JWT: still try cookie session (/me). Production needs token for cart API.
      if (!token) {
        if (serverUser) {
          setUserState(serverUser);
          saveAuthSession(serverUser, null);
        } else if (serverUser === false) {
          setUserState(null);
          clearAuthSession();
        } else {
          setUserState(normalizedStored);
        }
        clearTimeout(timeout);
        finish();
        return;
      }

      if (serverUser) {
        publishAuthSession(serverUser, token);
        setUserState(serverUser);
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

  const establishSession = useCallback((rawUser, token) => {
    const jwt = token || rawUser?.token || rawUser?.access_token || rawUser?.jwt || null;
    const { token: _t, access_token: _a, jwt: _j, ...rest } = rawUser || {};
    const normalized = normalizeUser(rest);
    if (!normalized) return false;
    publishAuthSession(normalized, jwt);
    setUserState(normalized);
    setAuthReady(true);
    return Boolean(jwt);
  }, []);

  const login = useCallback((userOrEmail, passwordOrNull, role = 'buyer') => {
    if (userOrEmail && typeof userOrEmail === 'object' && userOrEmail.email) {
      establishSession(userOrEmail, userOrEmail.token || userOrEmail.access_token || userOrEmail.jwt);
      return;
    }
    if (import.meta.env.DEV) {
      const normalized = normalizeUser({
        email: userOrEmail,
        name: String(userOrEmail).split('@')[0],
        role: role || 'buyer',
        id: Date.now().toString(),
      });
      setUserState(normalized);
      saveAuthSession(normalized, null);
      setAuthReady(true);
    }
  }, [establishSession]);

  const loginFromApi = useCallback(async (email, password) => {
    const { user, token } = await loginWithApi(email, password);
    establishSession(user, token);
    return { user: normalizeUser(user), token: getStoredToken() };
  }, [establishSession]);

  const signup = useCallback((name, email, password, role = 'buyer') => {
    login({ name, email, role: role || 'buyer', id: Date.now().toString() });
  }, [login]);

  const logout = useCallback(() => {
    setUserState(null);
    clearAuthSession();
    setAuthReady(true);
  }, []);

  const updateUser = useCallback((partial) => {
    setUserState((prev) => {
      if (!prev) return null;
      const next = { ...prev, ...partial };
      const { token } = loadAuthSession();
      saveAuthSession(next, token);
      return next;
    });
  }, []);

  const isBuyer = user?.role === 'buyer' || user?.role === 'customer';
  const isVendor = user?.role === 'vendor';
  const isAdmin = user?.role === 'admin';
  const token = getStoredToken();

  const value = useMemo(
    () => ({
      user,
      token,
      login,
      loginFromApi,
      signup,
      logout,
      updateUser,
      authReady,
      isBuyer,
      isVendor,
      isAdmin,
      isLoggedIn: !!user,
    }),
    [user, token, login, loginFromApi, signup, logout, updateUser, authReady, isBuyer, isVendor, isAdmin]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
