import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './HeaderUserMenu.css';

function initials(name, email) {
  const src = (name || email || 'U').trim();
  const parts = src.split(/\s+/).filter(Boolean);
  // Two+ words → first + last initial (e.g. "Umar Khan" → "UK").
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  // Single name → one clean letter (e.g. "Umar" → "U"), like Gmail/Google.
  return (parts[0] || src)[0].toUpperCase();
}

/** Header profile avatar + dropdown (account, orders, password, logout). */
const ProfileMenu = ({ onNavigate }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    if (open) document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  if (!user) return null;

  const role = user.role === 'customer' ? 'buyer' : (user.role || 'buyer');
  const close = () => { setOpen(false); onNavigate?.(); };

  return (
    <div className="hum-wrap" ref={ref}>
      <button
        type="button"
        className="hum-avatar-btn"
        onClick={() => setOpen((o) => !o)}
        aria-label="Account menu"
        aria-expanded={open}
        title={user.name || user.email}
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <circle cx="12" cy="8" r="3.6" />
          <path d="M4.5 19.5c0-3.9 3.4-5.9 7.5-5.9s7.5 2 7.5 5.9v.5h-15z" />
        </svg>
      </button>

      {open && (
        <div className="hum-dropdown hum-dropdown--profile" role="menu">
          <div className="hum-profile-head">
            <div className="hum-avatar-lg" aria-hidden="true">{initials(user.name, user.email)}</div>
            <div className="hum-profile-id">
              <strong>{user.name || user.email}</strong>
              <span>{user.email}</span>
              <span className="hum-role">{role}</span>
            </div>
          </div>

          <Link to="/my-orders" className="hum-item" onClick={close} role="menuitem">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3h18v4H3z" /><path d="M5 7v13h14V7" /><path d="M10 11h4" /></svg>
            My Account &amp; Orders
          </Link>
          <Link to="/change-password" className="hum-item" onClick={close} role="menuitem">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
            Change Password
          </Link>
          <button
            type="button"
            className="hum-item hum-item--danger"
            onClick={() => { close(); logout(); navigate('/'); }}
            role="menuitem"
          >
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>
            Log out
          </button>
        </div>
      )}
    </div>
  );
};

export default ProfileMenu;
