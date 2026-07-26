import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { changePasswordWithApi } from '../api/authApi';
import { loadAuthSession } from '../utils/authStorage';
import './ChangePassword.css';

export default function ChangePassword() {
  const { user, updateUser, authReady } = useAuth();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const sessionUser = useMemo(() => {
    const { user: stored } = loadAuthSession();
    return stored?.email ? stored : null;
    // re-read localStorage whenever the auth context's user changes (login/logout),
    // even though `user` itself isn't read in the body
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.email]);

  const activeUser = user?.email ? user : sessionUser;

  useEffect(() => {
    setError('');
    setLoading(false);
  }, []);

  useEffect(() => {
    setError('');
  }, [activeUser?.email]);

  useEffect(() => {
    if (!authReady) return;
    if (!activeUser?.email) {
      navigate('/', { replace: true });
    }
  }, [authReady, activeUser?.email, navigate]);

  if (!activeUser?.email) {
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

    setLoading(true);
    try {
      const data = await changePasswordWithApi({
        email: activeUser.email,
        current_password: currentPassword,
        new_password: newPassword,
      });
      if (!data?.success) {
        const msg = data?.error || data?.message || 'Failed to update password.';
        setError(msg);
        return;
      }
      updateUser({ must_change_password: false });
      navigate('/', { replace: true });
    } catch (err) {
      let msg = err?.data?.error || err?.message || 'Network error.';
      if (/failed to fetch|could not reach/i.test(String(msg))) {
        msg =
          'Network error talking to the API. Refresh the page and try again. If it persists, redeploy Railway from latest GitHub main.';
      } else if (String(msg).toLowerCase().includes('login required')) {
        msg =
          'Server is on an old build. Redeploy Railway (vendor dashboard folder), then use your one-time login password in Current password.';
      } else if (String(msg).toLowerCase().includes('current password is wrong')) {
        msg =
          'Current password is wrong. Use the one-time password from registration/admin email (the one you use to log in), not your new password.';
      }
      setError(msg);
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
            <strong>{activeUser.email}</strong>.
          </p>
          <form onSubmit={handleSubmit} className="change-password-form" noValidate>
            <div className="form-group">
              <label htmlFor="cp-email">Email</label>
              <input
                id="cp-email"
                type="email"
                value={activeUser.email}
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
