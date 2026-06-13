import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { dashboardGet } from '../api/dashboardApi';
import { connectSocket, disconnectSocket, onNotification } from '../realtime/socket';

const POLL_MS = 30000;          // slow fallback only — Socket.IO is the primary path
const AUTO_DISMISS_MS = 7000;

/**
 * Real-time notification toaster.
 * Primary: Socket.IO 'notification' events (instant). Fallback: a slow poll of
 * the notifications API in case the socket is temporarily down. Dedupes by id so
 * the two paths never double-toast.
 */
const NotificationToaster = () => {
  const { isLoggedIn, user } = useAuth();
  const [toasts, setToasts] = useState([]);
  const seenIds = useRef(new Set());
  const lastSeenId = useRef(0);
  const primed = useRef(false);

  useEffect(() => {
    if (!isLoggedIn || !user?.id) {
      seenIds.current = new Set();
      lastSeenId.current = 0;
      primed.current = false;
      return undefined;
    }

    let alive = true;

    const dismiss = (id) => alive && setToasts((list) => list.filter((t) => t.key !== id));

    const show = (n) => {
      if (!alive || !n) return;
      const id = n.id ?? `t${Date.now()}`;
      if (seenIds.current.has(id)) return;        // dedupe socket vs poll
      seenIds.current.add(id);
      if (typeof n.id === 'number') lastSeenId.current = Math.max(lastSeenId.current, n.id);
      const toast = { key: id, title: n.title, message: n.message };
      setToasts((list) => [...list, toast]);
      setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
    };

    // --- Primary: Socket.IO ---
    connectSocket(user);
    const off = onNotification((payload) => show(payload));

    // --- Fallback: slow poll ---
    const poll = () => {
      dashboardGet('/notifications?limit=10')
        .then((d) => {
          if (!alive || !d?.success) return;
          const items = Array.isArray(d.notifications) ? d.notifications : [];
          if (!items.length) return;
          const maxId = Math.max(...items.map((n) => n.id));
          if (!primed.current) {
            // Baseline so we never replay history on first load.
            primed.current = true;
            lastSeenId.current = maxId;
            items.forEach((n) => seenIds.current.add(n.id));
            return;
          }
          items
            .filter((n) => n.id > lastSeenId.current)
            .sort((a, b) => a.id - b.id)
            .forEach(show);
        })
        .catch(() => {});
    };
    poll();
    const timer = setInterval(poll, POLL_MS);

    return () => {
      alive = false;
      off();
      clearInterval(timer);
      disconnectSocket();
    };
  }, [isLoggedIn, user?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!isLoggedIn || !toasts.length) return null;

  return (
    <div
      style={{
        position: 'fixed', top: 84, right: 16, zIndex: 9999,
        display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 340,
      }}
    >
      {toasts.map((t) => (
        <div
          key={t.key}
          role="status"
          onClick={() => setToasts((list) => list.filter((x) => x.key !== t.key))}
          style={{
            background: '#fff', borderLeft: '4px solid #02457A', borderRadius: 6,
            boxShadow: '0 8px 24px rgba(0,0,0,.15)', padding: '12px 14px', cursor: 'pointer',
            animation: 'gsToastIn .25s ease-out',
          }}
        >
          <div style={{ fontWeight: 700, color: '#02457A', fontSize: '.9rem', marginBottom: 2 }}>
            🔔 {t.title}
          </div>
          <div style={{ color: '#334155', fontSize: '.82rem', lineHeight: 1.35 }}>{t.message}</div>
        </div>
      ))}
      <style>{`@keyframes gsToastIn{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}`}</style>
    </div>
  );
};

export default NotificationToaster;
