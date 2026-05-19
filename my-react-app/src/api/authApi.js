/**
 * Auth API — all requests use Railway base from flaskBase (VITE_API_BASE / production default).
 */
import { dashboardPost } from './dashboardApi';
import { getApiUrl } from '../utils/flaskBase';

/**
 * @returns {{ user: object, token: string }}
 */
export async function loginWithApi(email, password) {
  const normalizedEmail = String(email || '').trim();
  const pwd = password ?? '';
  if (!normalizedEmail || !pwd) {
    throw new Error('Email and password are required.');
  }

  const res = await fetch(getApiUrl('/login'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email: normalizedEmail, password: pwd }),
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const err = data.error || data.message || 'Login failed';
    if (res.status === 403 && /verify/i.test(String(err))) {
      throw new Error(
        'Please verify your email using the link we sent, then sign in with your one-time password.'
      );
    }
    if (res.status === 401) {
      throw new Error(
        'Invalid email or password. Use the one-time password from registration if this is your first login.'
      );
    }
    throw new Error(err);
  }

  const token = data.token || data.access_token || data.jwt;
  if (!token) {
    throw new Error('Login succeeded but no session token was returned. Please try again.');
  }
  if (!data.user?.email) {
    throw new Error('Login succeeded but user profile was missing. Please try again.');
  }

  return { user: data.user, token };
}

/**
 * @returns {{ success: boolean, one_time_password?: string, verification_url?: string, message?: string }}
 */
export async function registerWithApi({ name, email, role }) {
  return dashboardPost('/register', {
    name: String(name || '').trim(),
    email: String(email || '').trim().toLowerCase(),
    role: role === 'vendor' ? 'vendor' : 'customer',
  });
}

/**
 * @returns {{ success: boolean, message?: string }}
 */
export async function changePasswordWithApi({ email, current_password, new_password }) {
  return dashboardPost('/change-password', {
    email: String(email || '').trim(),
    current_password,
    new_password,
  });
}
