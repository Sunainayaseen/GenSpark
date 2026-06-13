/**
 * Socket.IO client singleton for real-time notifications.
 *
 * Dev: connects same-origin — Vite proxies /socket.io → Flask :5000 (no CORS).
 * Prod: connects to the API base (Railway) which allows the Vercel origin.
 *
 * Usage:
 *   import { connectSocket, disconnectSocket, onNotification } from '../realtime/socket';
 *   connectSocket(user);                 // after login
 *   const off = onNotification(fn);      // subscribe; call off() to unsubscribe
 *   disconnectSocket();                  // on logout
 */
import { io } from 'socket.io-client';
import { LIVE_API_URL } from '../config/deployUrls';

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
    });
  }
  return socket;
}

/** Connect (if needed) and join this user's private + role rooms. */
export function connectSocket(user) {
  if (!user?.id) return null;
  const s = getSocket();
  const join = () => s.emit('join', { user_id: user.id, role: user.role || user.role_name || '' });
  if (s.connected) join();
  else {
    s.once('connect', join);
    if (!s.active) s.connect();
  }
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
