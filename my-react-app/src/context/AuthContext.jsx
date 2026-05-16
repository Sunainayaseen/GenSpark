import { createContext, useContext, useState, useEffect } from 'react';
import { getApiUrl } from '../utils/flaskBase';

const AUTH_KEY = 'genspark_auth';

async function fetchSessionUser() {
  const res = await fetch(getApiUrl('/me'), { credentials: 'include' });
  if (!res.ok) return null;
  const data = await res.json().catch(() => null);
  if (!data?.success || !data.user) return null;
  return data.user;
}

const AuthContext = createContext();

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};

const loadStored = () => {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    if (raw) return JSON.parse(raw);
  } catch (_) {}
  return null;
};

const saveStored = (data) => {
  try {
    if (data) localStorage.setItem(AUTH_KEY, JSON.stringify(data));
    else localStorage.removeItem(AUTH_KEY);
  } catch (_) {}
};

export const AuthProvider = ({ children }) => {
  const [user, setUserState] = useState(loadStored);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const stored = loadStored();
      if (!stored?.email) return;
      const serverUser = await fetchSessionUser();
      if (cancelled) return;
      if (!serverUser) {
        setUserState(null);
        saveStored(null);
        return;
      }
      setUserState({
        id: serverUser.id,
        name: serverUser.name,
        email: serverUser.email,
        role: serverUser.role || 'customer',
        must_change_password: Boolean(serverUser.must_change_password),
      });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    saveStored(user);
  }, [user]);

  /** Login with user object from API (id, name, email, role, must_change_password) or legacy. */
  const login = (userOrEmail, passwordOrNull, role = 'buyer') => {
    if (userOrEmail && typeof userOrEmail === 'object' && userOrEmail.email) {
      setUserState({
        id: userOrEmail.id,
        name: userOrEmail.name || userOrEmail.email.split('@')[0],
        email: userOrEmail.email,
        role: userOrEmail.role || 'customer',
        must_change_password: Boolean(userOrEmail.must_change_password),
      });
    } else {
      setUserState({
        email: userOrEmail,
        name: String(userOrEmail).split('@')[0],
        role: role || 'buyer',
        id: Date.now().toString(),
      });
    }
  };

  const signup = (name, email, password, role = 'buyer') => {
    setUserState({
      email,
      name: name || email.split('@')[0],
      role,
      id: Date.now().toString(),
    });
  };

  const logout = () => setUserState(null);

  /** Update user in state (e.g. after password change: clear must_change_password). */
  const updateUser = (partial) => {
    setUserState((prev) => (prev ? { ...prev, ...partial } : null));
  };

  const isBuyer = user?.role === 'buyer';
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
