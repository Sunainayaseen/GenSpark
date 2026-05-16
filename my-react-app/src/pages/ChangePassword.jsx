import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getApiUrl, getFlaskBaseFallback, setFlaskBaseUsed } from '../utils/flaskBase';
import './ChangePassword.css';

/**
 * First-login screen when admin added user/vendor with one-time password.
 * User must set a new password; email is shown (readonly).
 */
export default function ChangePassword() {
  const { user, updateUser } = useAuth();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (!user?.email) {
    navigate('/', { replace: true });
    return null;
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
    const opts = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
      credentials: 'include',
    };
    try {
      let res = await fetch(getApiUrl('/change-password'), opts);
      if (!res.ok) {
        const fallback = getFlaskBaseFallback();
        if (fallback) {
          res = await fetch(`${fallback.replace(/\/$/, '')}/api/change-password`, opts);
          setFlaskBaseUsed(fallback);
        }
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data.error || 'Failed to update password.');
        setLoading(false);
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

  return (
    <div className="change-password-page">
      <div className="change-password-card">
        <h1>Change your password</h1>
        <p className="change-password-subtitle">
          Your account was created by an admin. Please set a new password for <strong>{user.email}</strong>.
        </p>
        <form onSubmit={handleSubmit} className="change-password-form">
          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              value={user.email}
              readOnly
              className="form-control readonly"
              aria-readonly
            />
          </div>
          <div className="form-group">
            <label>Current password (one-time password from admin)</label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="Enter current password"
              required
              className="form-control"
              autoComplete="current-password"
            />
          </div>
          <div className="form-group">
            <label>New password</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="At least 6 characters"
              required
              minLength={6}
              className="form-control"
              autoComplete="new-password"
            />
          </div>
          <div className="form-group">
            <label>Confirm new password</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm new password"
              required
              minLength={6}
              className="form-control"
              autoComplete="new-password"
            />
          </div>
          {error && <p className="change-password-error">{error}</p>}
          <button type="submit" className="btn btn-primary change-password-submit" disabled={loading}>
            {loading ? 'Updating…' : 'Update password'}
          </button>
        </form>
      </div>
    </div>
  );
}
