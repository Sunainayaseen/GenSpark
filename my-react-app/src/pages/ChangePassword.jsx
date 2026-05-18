import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getApiUrl } from '../utils/flaskBase';
import { getStoredToken } from '../utils/authStorage';
import './ChangePassword.css';

/**
 * First-login screen when admin added user/vendor with one-time password.
 * User must set a new password; email is shown (readonly).
 */
export default function ChangePassword() {
  const { user, updateUser, authReady } = useAuth();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setError('');
    setLoading(false);
  }, []);

  useEffect(() => {
    setError('');
  }, [user?.email]);

  useEffect(() => {
    if (authReady && !user?.email) {
      navigate('/', { replace: true });
    }
  }, [authReady, user?.email, navigate]);

  if (!authReady || !user?.email) {
    return (
      <div className="change-password-page change-password-page--loading" aria-busy="true">
        <p className="change-password-loading">Loading…</p>
      </div>
    );
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (newPassword.length < 6) {
      setError('New password must be at least 6 characters.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('New password and confirm do not match.');
      return;
    }

    const token = getStoredToken();
    const canUseOtpFallback = Boolean(user?.must_change_password);

    if (!token && !canUseOtpFallback) {
      setError('Session expired. Please sign out, sign in again, then update your password.');
      return;
    }

    const headers = { 'Content-Type': 'application/json' };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    setLoading(true);
    try {
      const res = await fetch(getApiUrl('/change-password'), {
        method: 'POST',
        headers,
        body: JSON.stringify({
          email: user.email,
          current_password: currentPassword,
          new_password: newPassword,
        }),
        credentials: 'include',
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data.error || 'Failed to update password.');
        return;
      }
      updateUser({ must_change_password: false });
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.message || 'Network error.');
    } finally {
      setLoading(false);
    }
  };

  const onFieldChange = (setter) => (e) => {
    setter(e.target.value);
    if (error) setError('');
  };

  return (
    <div className="change-password-page">
      <div className="change-password-shell">
        <div className="change-password-card">
          <h1>Change your password</h1>
          <p className="change-password-subtitle">
            Your account was created by an admin. Please set a new password for{' '}
            <strong>{user.email}</strong>.
          </p>
          <form onSubmit={handleSubmit} className="change-password-form" noValidate>
            <div className="form-group">
              <label htmlFor="cp-email">Email</label>
              <input
                id="cp-email"
                type="email"
                value={user.email}
                readOnly
                className="form-control readonly"
                aria-readonly
              />
            </div>
            <div className="form-group">
              <label htmlFor="cp-current">Current password (one-time password from admin)</label>
              <input
                id="cp-current"
                type="password"
                value={currentPassword}
                onChange={onFieldChange(setCurrentPassword)}
                placeholder="Enter current password"
                required
                className="form-control"
                autoComplete="current-password"
              />
            </div>
            <div className="form-group">
              <label htmlFor="cp-new">New password</label>
              <input
                id="cp-new"
                type="password"
                value={newPassword}
                onChange={onFieldChange(setNewPassword)}
                placeholder="At least 6 characters"
                required
                minLength={6}
                className="form-control"
                autoComplete="new-password"
              />
            </div>
            <div className="form-group">
              <label htmlFor="cp-confirm">Confirm new password</label>
              <input
                id="cp-confirm"
                type="password"
                value={confirmPassword}
                onChange={onFieldChange(setConfirmPassword)}
                placeholder="Confirm new password"
                required
                minLength={6}
                className="form-control"
                autoComplete="new-password"
              />
            </div>
            {error ? (
              <p className="change-password-error" role="alert">
                {error}
              </p>
            ) : null}
            <button
              type="submit"
              className="btn btn-primary change-password-submit"
              disabled={loading}
              aria-busy={loading}
            >
              {loading ? 'Updating…' : 'Update password'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
