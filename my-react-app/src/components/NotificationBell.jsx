import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { dashboardGet, dashboardPost } from '../api/dashboardApi';
import { connectSocket, onNotification } from '../realtime/socket';
import './HeaderUserMenu.css';

function timeAgo(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 604800) return `${Math.floor(s / 86400)}d ago`;
  try { return d.toLocaleDateString('en-PK', { day: '2-digit', month: 'short' }); } catch (_) { return ''; }
}

/** Header notification bell: unread badge + dropdown list, live via Socket.IO. */
const NotificationBell = () => {
  const { user, isLoggedIn } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const ref = useRef(null);

  const load = () => {
    dashboardGet('/notifications?limit=12')
      .then((d) => {
        if (d?.success) {
          setItems(Array.isArray(d.notifications) ? d.notifications : []);
          setUnread(Number(d.unread) || 0);
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    if (!isLoggedIn || !user?.id) { setItems([]); setUnread(0); return undefined; }
    load();
    connectSocket(user);
    const off = onNotification((n) => {
      if (!n) return;
      setItems((list) => [{ is_read: false, ...n, id: n.id ?? Date.now() }, ...list].slice(0, 20));
      setUnread((u) => u + 1);
    });
    return off;
  }, [isLoggedIn, user?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    if (open) document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const toggle = () => { setOpen((o) => !o); if (!open) load(); };

  const markAll = () => {
    dashboardPost('/notifications/read-all', {}).catch(() => {});
    setItems((l) => l.map((n) => ({ ...n, is_read: true })));
    setUnread(0);
  };

  // Only order notifications carry an order id; 'delivery' notifications carry a
  // delivery id (rider side), so they must NOT deep-link to /order/<id>.
  const ORDER_TYPES = new Set(['order_update', 'admin_alert']);

  const openItem = (n) => {
    if (typeof n.id === 'number') dashboardPost(`/notifications/${n.id}/read`, {}).catch(() => {});
    if (!n.is_read) setUnread((u) => Math.max(0, u - 1));
    setItems((l) => l.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)));
    setOpen(false);
    if (n.related_id && ORDER_TYPES.has(n.type)) navigate(`/order/${n.related_id}`);
  };

  if (!isLoggedIn) return null;

  return (
    <div className="hum-wrap" ref={ref}>
      <button type="button" className="hum-icon-btn" onClick={toggle} aria-label="Notifications" aria-expanded={open}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {unread > 0 && <span className="hum-badge">{unread > 9 ? '9+' : unread}</span>}
      </button>

      {open && (
        <div className="hum-dropdown hum-dropdown--notif" role="menu">
          <div className="hum-dd-head">
            <span>Notifications</span>
            {items.some((n) => !n.is_read) && (
              <button type="button" className="hum-link" onClick={markAll}>Mark all read</button>
            )}
          </div>
          <div className="hum-notif-list">
            {items.length === 0 ? (
              <div className="hum-empty">
                <span aria-hidden="true">🔔</span>
                <p>You're all caught up.</p>
              </div>
            ) : (
              items.map((n) => (
                <button
                  type="button"
                  key={n.id}
                  className={`hum-notif ${n.is_read ? '' : 'is-unread'}`}
                  onClick={() => openItem(n)}
                >
                  <span className="hum-notif-dot" aria-hidden="true" />
                  <span className="hum-notif-body">
                    <span className="hum-notif-title">{n.title}</span>
                    <span className="hum-notif-msg">{n.message}</span>
                    {n.created_at && <span className="hum-notif-time">{timeAgo(n.created_at)}</span>}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationBell;
