/**
 * Socket.IO client singleton for real-time notifications.
 *
 * Dev: connects same-origin — Vite proxies /socket.io → Flask :5000 (no CORS).
 * Prod: connects to the API base (Railway) which allows the Vercel origin.
 *
 * Auth: the JWT is sent via the `auth` payload at connect time; the server
 * resolves the user (and therefore which rooms to join) from that token —
 * it never trusts a client-supplied user_id/role (see backend/app/realtime.py).
 *
 * Usage:
 *   import { connectSocket, disconnectSocket, onNotification } from '../realtime/socket';
 *   connectSocket(user);                 // after login
 *   const off = onNotification(fn);      // subscribe; call off() to unsubscribe
 *   disconnectSocket();                  // on logout
 */
import { io } from 'socket.io-client';
import { LIVE_API_URL } from '../config/deployUrls';
import { getStoredToken } from '../utils/authStorage';

let socket = null;

function socketUrl() {
  // Same-origin in dev → handled by the Vite ws proxy.
  if (import.meta.env.DEV) return undefined;
  const fromEnv = import.meta.env?.VITE_API_BASE;
  return (fromEnv || LIVE_API_URL || '').replace(/\/$/, '') || undefined;
}

export function getSocket() {
  if (!socket) {
    socket = io(socketUrl(), {
      path: '/socket.io',
      withCredentials: true,
      autoConnect: false,
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1500,
      auth: (cb) => cb({ token: getStoredToken() }),
    });
  }
  return socket;
}

/** Connect (if needed); the server joins this user's private + role rooms from the JWT. */
export function connectSocket(user) {
  if (!user?.id) return null;
  const s = getSocket();
  if (!s.connected && !s.active) s.connect();
  return s;
}

export function disconnectSocket() {
  if (socket) {
    try { socket.removeAllListeners('notification'); } catch { /* noop */ }
    socket.disconnect();
  }
}

/** Subscribe to 'notification' events. Returns an unsubscribe fn. */
export function onNotification(handler) {
  const s = getSocket();
  s.on('notification', handler);
  return () => s.off('notification', handler);
}
