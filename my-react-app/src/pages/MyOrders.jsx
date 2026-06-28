import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { dashboardGet } from '../api/dashboardApi';
import AddressBook from '../components/AddressBook';
import './MyOrders.css';

/** status -> { label, cls } (cls drives the dot + left accent colour). */
const STATUS_META = {
  pending: { label: 'Pending', cls: 'pending' },
  'admin-review': { label: 'In Review', cls: 'pending' },
  approved: { label: 'Approved', cls: 'progress' },
  accepted: { label: 'Accepted', cls: 'progress' },
  processing: { label: 'Processing', cls: 'progress' },
  assembly: { label: 'In Assembly', cls: 'progress' },
  qa: { label: 'Quality Check', cls: 'progress' },
  ready_to_dispatch: { label: 'Ready to Ship', cls: 'ready' },
  shipped: { label: 'Dispatched', cls: 'shipped' },
  delivered: { label: 'Delivered', cls: 'done' },
  completed: { label: 'Completed', cls: 'done' },
  rejected: { label: 'Rejected', cls: 'rejected' },
  cancelled: { label: 'Cancelled', cls: 'rejected' },
};
const CLOSED = new Set(['delivered', 'completed', 'rejected', 'cancelled']);

const statusMeta = (s) =>
  STATUS_META[(s || '').toLowerCase()] || { label: (s || 'Unknown').replace(/_/g, ' '), cls: 'neutral' };

const initials = (name, email) => {
  const src = (name || email || 'U').trim();
  const p = src.split(/\s+/).filter(Boolean);
  return (p.length >= 2 ? p[0][0] + p[1][0] : src.slice(0, 2)).toUpperCase();
};

const fmtDate = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString('en-PK', { day: '2-digit', month: 'long', year: 'numeric' }); }
  catch (_) { return '—'; }
};

const Icon = ({ d, children, size = 18 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    {d ? <path d={d} /> : children}
  </svg>
);

const MyOrders = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState('orders');
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user) { setLoading(false); return undefined; }
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const res = await dashboardGet('/orders?mine=1&limit=50');
        if (!cancelled) { setOrders(Array.isArray(res?.orders) ? res.orders : []); setError(''); }
      } catch (e) {
        if (!cancelled) { setOrders([]); setError(e?.data?.error || e?.message || 'Could not load your orders.'); }
      } finally { if (!cancelled) setLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [user]);

  const role = useMemo(() => (user?.role === 'customer' ? 'buyer' : user?.role || 'buyer'), [user]);

  if (!user) {
    return (
      <div className="acc-page"><div className="container">
        <div className="acc-signin">
          <h1>My Account</h1>
          <p>Please sign in to view your profile and order history.</p>
          <Link to={{ pathname: '/', search: '?login=1' }} className="btn btn-primary">Sign in</Link>
        </div>
      </div></div>
    );
  }

  return (
    <div className="acc-page">
      <div className="container">
        <div className="acc-shell">
          {/* Sidebar */}
          <aside className="acc-sidebar">
            <div className="acc-user">
              <div className="acc-user__avatar" aria-hidden="true">{initials(user.name, user.email)}</div>
              <div className="acc-user__id">
                <strong>{user.name || user.email}</strong>
                <span>{user.email}</span>
              </div>
            </div>

            <nav className="acc-nav" aria-label="Account">
              <button type="button" className={`acc-nav__item ${tab === 'orders' ? 'is-active' : ''}`} onClick={() => setTab('orders')}>
                <Icon><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M9 21V9" /></Icon>
                <span>View Orders</span>
                <span className="acc-nav__count">{orders.length}</span>
              </button>
              <button type="button" className={`acc-nav__item ${tab === 'profile' ? 'is-active' : ''}`} onClick={() => setTab('profile')}>
                <Icon><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></Icon>
                <span>Personal Details</span>
              </button>
              <button type="button" className={`acc-nav__item ${tab === 'addresses' ? 'is-active' : ''}`} onClick={() => setTab('addresses')}>
                <Icon><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" /></Icon>
                <span>Saved Addresses</span>
              </button>
              <Link to="/change-password" className="acc-nav__item">
                <Icon><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></Icon>
                <span>Change Password</span>
              </Link>
              <button type="button" className="acc-nav__item acc-nav__item--danger" onClick={() => { logout(); navigate('/'); }}>
                <Icon><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></Icon>
                <span>Log out</span>
              </button>
            </nav>
          </aside>

          {/* Main */}
          <main className="acc-main">
            {tab === 'orders' && (
              <>
                <header className="acc-head">
                  <h1>Order history</h1>
                  <p>{orders.length} order{orders.length === 1 ? '' : 's'}</p>
                </header>

                {loading && <div className="acc-state"><div className="acc-spinner" /><p>Loading your orders…</p></div>}
                {!loading && error && <p className="acc-error" role="alert">{error}</p>}
                {!loading && !error && orders.length === 0 && (
                  <div className="acc-state">
                    <div className="acc-state__icon" aria-hidden="true">📦</div>
                    <p>You haven't placed any orders yet.</p>
                    <Link to="/builds" className="btn btn-primary btn-sm">Browse Prebuilt PCs</Link>
                  </div>
                )}

                {!loading && !error && orders.map((o) => {
                  const meta = statusMeta(o.status);
                  const active = !CLOSED.has((o.status || '').toLowerCase());
                  return (
                    <article key={o.id} className={`acc-order acc-order--${meta.cls}`}>
                      <div className="acc-order__status">
                        <span className="acc-order__dot" aria-hidden="true" />
                        {meta.label}
                        {o.created_at && <span className="acc-order__when">· {fmtDate(o.created_at)}</span>}
                      </div>
                      <div className="acc-order__body">
                        <div className="acc-order__info">
                          <strong className="acc-order__id">{o.order_number || `Order #${o.id}`}</strong>
                          <span className="acc-order__total">PKR {Number(o.total_amount || 0).toLocaleString('en-US')}</span>
                        </div>
                        <div className="acc-order__actions">
                          {active ? (
                            <Link to={`/order/${o.id}`} className="acc-btn acc-btn--primary">Track order</Link>
                          ) : (
                            <Link to={`/order/${o.id}`} className="acc-btn acc-btn--outline">View order details</Link>
                          )}
                          <Link to={`/order/${o.id}`} className="acc-btn-link">View order details</Link>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </>
            )}

            {tab === 'profile' && (
              <>
                <header className="acc-head">
                  <h1>Personal details</h1>
                  <p>Your account information</p>
                </header>
                <div className="acc-profile-card">
                  <div className="acc-field"><span className="acc-field__label">Full name</span><span className="acc-field__value">{user.name || '—'}</span></div>
                  <div className="acc-field"><span className="acc-field__label">Email address</span><span className="acc-field__value">{user.email}</span></div>
                  <div className="acc-field"><span className="acc-field__label">Account type</span><span className="acc-field__value" style={{ textTransform: 'capitalize' }}>{role}</span></div>
                  <div className="acc-profile-actions">
                    <Link to="/change-password" className="acc-btn acc-btn--outline">Change password</Link>
                  </div>
                </div>
              </>
            )}

            {tab === 'addresses' && <AddressBook />}
          </main>
        </div>
      </div>
    </div>
  );
};

export default MyOrders;
