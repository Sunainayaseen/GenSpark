import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { dashboardGet } from '../api/dashboardApi';

const LEAFLET_CSS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
const LEAFLET_JS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
const POLL_MS = 3000;
const LAHORE = [31.5204, 74.3587];

/** Load Leaflet from CDN once; resolves with the global `L`. */
function ensureLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  return new Promise((resolve, reject) => {
    if (!document.querySelector(`link[href="${LEAFLET_CSS}"]`)) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = LEAFLET_CSS;
      document.head.appendChild(link);
    }
    let script = document.querySelector(`script[src="${LEAFLET_JS}"]`);
    if (script && window.L) return resolve(window.L);
    if (!script) {
      script = document.createElement('script');
      script.src = LEAFLET_JS;
      document.body.appendChild(script);
    }
    script.addEventListener('load', () => resolve(window.L));
    script.addEventListener('error', () => reject(new Error('Failed to load Leaflet')));
  });
}

const STATUS_LABEL = {
  assigned: 'Rider assigned',
  pickup_requested: 'Pickup requested',
  approved: 'Approved for pickup',
  in_transit: 'On the way',
  delivered: 'Delivered',
};

const TrackOrder = () => {
  const { orderId } = useParams();
  const mapEl = useRef(null);
  const mapRef = useRef(null);
  const riderMarker = useRef(null);
  const dropMarker = useRef(null);
  const routeLine = useRef(null);
  const pollRef = useRef(null);

  const [tracking, setTracking] = useState(null);
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let alive = true;
    let L = null;

    ensureLeaflet()
      .then((lib) => {
        if (!alive) return;
        L = lib;
        const map = L.map(mapEl.current).setView(LAHORE, 12);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19,
          attribution: '&copy; OpenStreetMap contributors',
        }).addTo(map);
        mapRef.current = map;
        setReady(true);
        poll();
        pollRef.current = setInterval(poll, POLL_MS);
      })
      .catch(() => alive && setError('Could not load the map. Check your connection.'));

    const bikeIcon = () =>
      L &&
      L.divIcon({
        html: '<div style="font-size:28px;line-height:1">🏍️</div>',
        className: 'rider-emoji',
        iconSize: [32, 32],
        iconAnchor: [16, 16],
      });

    function render(t) {
      setTracking(t);
      const map = mapRef.current;
      if (!map || !L) return;

      if (t.dropoff && !dropMarker.current) {
        dropMarker.current = L.marker([t.dropoff.lat, t.dropoff.lng])
          .addTo(map)
          .bindPopup('Delivery address');
      }
      if (t.latitude != null) {
        const pos = [t.latitude, t.longitude];
        if (!riderMarker.current) {
          riderMarker.current = L.marker(pos, { icon: bikeIcon() }).addTo(map).bindPopup('Your rider');
          map.setView(pos, 14);
        } else {
          riderMarker.current.setLatLng(pos);
        }
        map.panTo(pos, { animate: true });
      }
      if (Array.isArray(t.route) && t.route.length > 1) {
        if (routeLine.current) routeLine.current.setLatLngs(t.route);
        else routeLine.current = L.polyline(t.route, { color: '#02457A', weight: 4, opacity: 0.7 }).addTo(map);
      }
    }

    function poll() {
      dashboardGet(`/rider/location/${orderId}`)
        .then((d) => {
          if (!alive) return;
          if (d?.success && d.tracking) {
            setError('');
            render(d.tracking);
            if (d.tracking.status === 'delivered' && pollRef.current) {
              clearInterval(pollRef.current);
              pollRef.current = null;
            }
          }
        })
        .catch((e) => {
          if (alive) setError(e?.message || 'Tracking unavailable for this order yet.');
        });
    }

    return () => {
      alive = false;
      if (pollRef.current) clearInterval(pollRef.current);
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, [orderId]);

  const status = tracking?.status;
  const active = tracking?.tracking_active;

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '1.5rem 1rem' }}>
      <h1 style={{ color: '#02457A', margin: '0 0 .25rem' }}>Track your order</h1>
      <p style={{ color: '#64748b', marginTop: 0 }}>
        Order <strong>{tracking?.order_code || `#${orderId}`}</strong> — live rider location
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 280px), 1fr))', gap: '1rem', alignItems: 'start' }}>
        <div
          ref={mapEl}
          style={{ height: 480, width: '100%', borderRadius: 8, background: '#eef2f6', boxShadow: '0 0 0 1px rgba(0,0,0,.06)' }}
        />

        <aside style={{ background: '#fff', borderRadius: 8, padding: '1rem', boxShadow: '0 0 0 1px rgba(0,0,0,.06)' }}>
          <div style={{ marginBottom: '1rem' }}>
            <span
              style={{
                fontSize: '.75rem',
                fontWeight: 700,
                padding: '4px 12px',
                borderRadius: 999,
                color: status === 'delivered' ? '#065f46' : '#1e40af',
                background: status === 'delivered' ? '#ecfdf5' : '#eff6ff',
              }}
            >
              {STATUS_LABEL[status] || (active ? 'Tracking…' : 'Waiting for rider')}
            </span>
          </div>

          <div style={{ display: 'flex', gap: '1rem', marginBottom: '.5rem' }}>
            <div>
              <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#02457A' }}>
                {tracking?.eta_minutes != null ? tracking.eta_minutes : '—'}
              </div>
              <div style={{ fontSize: '.75rem', color: '#64748b' }}>ETA (min)</div>
            </div>
            <div>
              <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#065f46' }}>
                {tracking?.distance_remaining_km != null ? tracking.distance_remaining_km : '—'}
              </div>
              <div style={{ fontSize: '.75rem', color: '#64748b' }}>Distance (km)</div>
            </div>
          </div>

          {tracking?.progress != null && (
            <div style={{ margin: '.75rem 0' }}>
              <div style={{ height: 8, background: '#e2e8f0', borderRadius: 999, overflow: 'hidden' }}>
                <div style={{ width: `${Math.round(tracking.progress * 100)}%`, height: '100%', background: '#02457A' }} />
              </div>
            </div>
          )}

          {!ready && !error && <p style={{ color: '#94a3b8', fontSize: '.85rem' }}>Loading map…</p>}
          {error && <p style={{ color: '#b91c1c', fontSize: '.85rem' }}>{error}</p>}
          {ready && !error && !tracking?.latitude && (
            <p style={{ color: '#64748b', fontSize: '.85rem' }}>
              Your rider hasn’t started sharing location yet. This page updates automatically.
            </p>
          )}
        </aside>
      </div>
    </div>
  );
};

export default TrackOrder;
