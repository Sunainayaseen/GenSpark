import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { dashboardGet } from '../api/dashboardApi';
import { ORDER_STAGES, getStageIndex } from '../constants/orderStages';
import { useAuth } from '../context/AuthContext';
import { connectSocket, onNotification } from '../realtime/socket';
import './OrderStatus.css';

/** Professional line-style SVG icons per lifecycle stage (inherit currentColor). */
const _svg = (children) => (
  <svg
    width="22" height="22" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"
    aria-hidden="true"
  >
    {children}
  </svg>
);
const STEP_ICONS = {
  // Order placed — document
  pending: _svg(
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <line x1="10" y1="9" x2="8" y2="9" />
    </>
  ),
  // Admin approved — shield check
  approved: _svg(
    <>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <polyline points="9 11.5 11.2 13.7 15 9.5" />
    </>
  ),
  // Vendor processing — tool/wrench
  processing: _svg(
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
  ),
  // Ready to ship — package
  ready_to_dispatch: _svg(
    <>
      <line x1="16.5" y1="9.4" x2="7.5" y2="4.21" />
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
      <line x1="12" y1="22.08" x2="12" y2="12" />
    </>
  ),
  // Dispatched — truck
  shipped: _svg(
    <>
      <rect x="1" y="3" width="15" height="13" rx="1" />
      <path d="M16 8h4l3 3v5h-7V8z" />
      <circle cx="5.5" cy="18.5" r="2.5" />
      <circle cx="18.5" cy="18.5" r="2.5" />
    </>
  ),
  // Delivered — check circle
  completed: _svg(
    <>
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </>
  ),
};

/** eCommerce orders live in /api/ecom — shape differs from PC-build orders. */
function adaptEcomOrder(e) {
  if (!e) return null;
  const items = (e.items || []).map((it) => ({
    id: it.id,
    item_type: 'product',
    item_id: it.product_id,
    component_name: it.name,
    quantity: it.quantity,
    unit_price: it.unit_price,
    total_price: it.line_total,
  }));
  const itemsSub = items.reduce((s, it) => s + Number(it.total_price || 0), 0);
  const ship = Math.max(0, Number(e.total_amount || 0) - itemsSub);
  return {
    id: e.id,
    order_number: e.order_number,
    total_amount: e.total_amount,
    items_subtotal: itemsSub,
    shipping_fee: ship,
    status: e.status,
    shipping_address: [e.name, e.phone, e.address, e.city].filter(Boolean).join(' · '),
    items,
    vendor_orders: [],
    status_history: [
      { status: e.status, notes: 'Shop order (eCommerce demo)', created_at: e.created_at },
    ],
    _source: 'ecom',
  };
}

function messageForError(err) {
  const st = err?.status;
  const server = err?.data?.error || err?.message;
  if (st === 401) return 'You need to be signed in to open this order. Use Login in the header, then try again.';
  if (st === 403) return "You don't have access to this order. It may belong to another account.";
  if (st === 404) return server || 'Order not found in the catalog.';
  return server || 'Failed to load order';
}

const formatTime = (iso) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString('en-PK', { dateStyle: 'short', timeStyle: 'short' });
  } catch (_) {
    return iso;
  }
};

/** Presentational status badge for header (no business logic). */
function statusBadgeClass(status) {
  const s = (status || '').toLowerCase();
  if (s === 'pending' || s === 'admin-review') return 'os-badge os-badge--pending';
  if (s === 'rejected' || s === 'cancelled') return 'os-badge os-badge--rejected';
  if (s === 'completed' || s === 'delivered') return 'os-badge os-badge--done';
  if (s === 'shipped') return 'os-badge os-badge--shipped';
  if (s === 'ready_to_dispatch') return 'os-badge os-badge--ready';
  if (s === 'approved' || s === 'processing' || s === 'assembly' || s === 'qa' || s === 'accepted') {
    return 'os-badge os-badge--progress';
  }
  return 'os-badge os-badge--neutral';
}

function formatStatusLabel(status) {
  if (!status) return 'Unknown';
  return String(status).replace(/_/g, ' ');
}

/** Icon + tone for timeline rows (presentation only). */
function timelineEntryMeta(message, status) {
  const text = `${message || ''} ${status || ''}`.toLowerCase();
  if (text.includes('reject') || text.includes('cancel')) {
    return { icon: '✕', tone: 'danger' };
  }
  if (text.includes('ship') || text.includes('dispatch')) {
    return { icon: '🚚', tone: 'info' };
  }
  if (text.includes('approv') || text.includes('proof') || text.includes('complete')) {
    return { icon: '✓', tone: 'success' };
  }
  if (text.includes('vendor') || text.includes('assign')) {
    return { icon: '🏪', tone: 'vendor' };
  }
  if (text.includes('process') || text.includes('assembl')) {
    return { icon: '⚙', tone: 'progress' };
  }
  return { icon: '📋', tone: 'default' };
}

/** Vendor card badge + progress (presentation only). */
function vendorStatusMeta(status) {
  const s = (status || '').toLowerCase();
  if (s === 'completed' || s === 'delivered') {
    return { label: 'Completed', badge: 'os-vendor-badge--done', progress: 100 };
  }
  if (s === 'shipped' || s === 'ready_to_dispatch') {
    return { label: formatStatusLabel(status), badge: 'os-vendor-badge--ship', progress: 90 };
  }
  if (s === 'processing' || s === 'assembly' || s === 'qa' || s === 'accepted') {
    return { label: formatStatusLabel(status), badge: 'os-vendor-badge--active', progress: 55 };
  }
  if (s === 'rejected' || s === 'cancelled') {
    return { label: formatStatusLabel(status), badge: 'os-vendor-badge--danger', progress: 0 };
  }
  return { label: formatStatusLabel(status), badge: 'os-vendor-badge--pending', progress: 25 };
}

function vendorInitials(name) {
  const parts = String(name || 'V').trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return (parts[0]?.[0] || 'V').toUpperCase();
}

const OrderStatus = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  // Bumped by the live channel (Socket.IO / poll) to silently re-fetch the order.
  const [refreshTick, setRefreshTick] = useState(0);
  const hadOrder = useRef(false);

  useEffect(() => {
    if (!id) {
      setOrder(null);
      setError('Invalid order link (missing id).');
      setLoading(false);
      return;
    }
    const loadOrder = async () => {
      // Only show the full spinner on the first load — live refreshes are silent.
      if (!hadOrder.current) setLoading(true);
      setError('');
      try {
        const res = await dashboardGet(`/orders/${id}`);
        if (res?.order) {
          setOrder(res.order);
        } else {
          setOrder(null);
          setError('Order data was empty.');
        }
      } catch (err) {
        if (err?.status === 404) {
          try {
            const res2 = await dashboardGet(`/ecom/orders/${id}`);
            if (res2?.order) {
              setOrder(adaptEcomOrder(res2.order));
            } else {
              setOrder(null);
              setError('Order not found (neither in build orders nor in shop).');
            }
          } catch (e2) {
            setOrder(null);
            setError(messageForError(e2));
          }
        } else {
          setOrder(null);
          setError(messageForError(err));
        }
      } finally {
        setLoading(false);
        hadOrder.current = true;  // subsequent live refreshes are silent
      }
    };
    loadOrder();
  }, [id, refreshTick]);

  // --- Live status updates (KFC-style): refresh on a Socket.IO notification for
  // this order, with a slow poll as a fallback. No map — just live status/timeline.
  useEffect(() => {
    if (!id) return undefined;
    if (user?.id) connectSocket(user);
    const off = onNotification((n) => {
      const rid = n?.related_id;
      if (rid == null || Number(rid) === Number(id)) {
        setRefreshTick((t) => t + 1);
      }
    });
    const timer = setInterval(() => setRefreshTick((t) => t + 1), 15000);
    return () => {
      off();
      clearInterval(timer);
    };
  }, [id, user?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const timeline = useMemo(
    () => (order?.status_history || []).map((entry) => ({
      status: entry.status,
      message: entry.notes || entry.status,
      timestamp: entry.created_at,
    })),
    [order]
  );
  const statusForBar = useMemo(() => {
    if (!order?.status) return '';
    if (order.status === 'delivered' || order.status === 'cancelled') {
      return order.status === 'delivered' ? 'completed' : 'rejected';
    }
    return order.status;
  }, [order]);

  const currentStepIndex =
    order && statusForBar === 'rejected'
      ? -1
      : order
        ? getStageIndex(statusForBar)
        : -1;

  const priceBreakdown = useMemo(() => {
    if (!order) {
      return { itemsSubtotal: 0, shipping: 0, total: 0 };
    }
    const lineSum = (order.items || []).reduce((s, it) => s + Number(it.total_price || 0), 0);
    const itemsSubtotal =
      order.items_subtotal != null && !Number.isNaN(Number(order.items_subtotal))
        ? Number(order.items_subtotal)
        : lineSum;
    let shipping = 0;
    if (order.shipping_fee != null && !Number.isNaN(Number(order.shipping_fee))) {
      shipping = Number(order.shipping_fee);
    } else {
      shipping = Math.max(0, Number(order.total_amount || 0) - itemsSubtotal);
    }
    const total = Number(order.total_amount ?? itemsSubtotal + shipping);
    return { itemsSubtotal, shipping, total };
  }, [order]);

  if (loading) {
    return (
      <div className="order-status-page">
        <div className="container">
          <div className="os-loading" aria-busy="true" aria-live="polite">
            <div className="os-loading__spinner" aria-hidden="true" />
            <p>Loading your order…</p>
          </div>
        </div>
      </div>
    );
  }

  if (!order || error) {
    return (
      <div className="order-status-page">
        <div className="container">
          <header className="os-hero">
            <div className="os-hero__main">
              <h1>Order #{id}</h1>
            </div>
          </header>
          <div className="order-not-found">
            <p>{error || 'Order not found.'}</p>
            {error && String(error).toLowerCase().includes('signed in') ? (
              <p>
                <Link
                  to={{ pathname: location.pathname, search: '?login=1' }}
                  className="btn btn-primary"
                  style={{ display: 'inline-block', marginTop: 8 }}
                >
                  Open sign in
                </Link>
              </p>
            ) : null}
            <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
              <button type="button" className="btn btn-primary" onClick={() => navigate('/my-orders')}>
                View my orders
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => navigate('/builds')}>
                Browse predefined PCs
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const isEcom = order._source === 'ecom';

  return (
    <div className="order-status-page">
      <div className="container">
        <header className="os-hero">
          <div className="os-hero__main">
            <Link to="/my-orders" className="os-back">← My orders</Link>
            <span className="os-hero__eyebrow">Order Tracking</span>
            <h1>{order.order_number || `Order #${order.id}`}</h1>
            <p className="os-hero__meta">
              <span className={statusBadgeClass(order.status)}>{formatStatusLabel(order.status)}</span>
              <span aria-hidden="true">·</span>
              <span>{isEcom ? 'Shop order' : 'Custom PC build'}</span>
            </p>
          </div>
          <div className="os-hero__facts">
            <div className="os-fact os-fact--accent">
              <span className="os-fact__label">Total</span>
              <span className="os-fact__value">PKR {priceBreakdown.total.toLocaleString()}</span>
            </div>
            <div className="os-fact">
              <span className="os-fact__label">Items</span>
              <span className="os-fact__value">{(order.items || []).length}</span>
            </div>
            <div className="os-fact">
              <span className="os-fact__label">Placed</span>
              <span className="os-fact__value">
                {order.status_history?.[0]?.created_at
                  ? new Date(order.status_history[0].created_at).toLocaleDateString('en-PK', { day: '2-digit', month: 'short' })
                  : '—'}
              </span>
            </div>
          </div>
        </header>

        <div className="order-content">
          <section className="order-card" aria-labelledby="order-summary-heading">
            <div className="order-header">
              <div className="order-header__title">
                <h2 id="order-summary-heading">{isEcom ? 'Shop order' : 'Order summary'}</h2>
                {(order.items || []).length > 0 && (
                  <span className="os-items-count">
                    {order.items.length} item{order.items.length > 1 ? 's' : ''}
                  </span>
                )}
              </div>
              <div className="order-price">PKR {priceBreakdown.total.toLocaleString()}</div>
            </div>
            {(order.items || []).length > 0 && (
              <ul className="os-items-list" aria-label="Order items">
                {order.items.map((it) => {
                  const qty = Number(it.quantity || 1);
                  const total = Number(it.total_price || 0);
                  const unit = it.unit_price != null
                    ? Number(it.unit_price)
                    : (qty ? total / qty : total);
                  return (
                    <li key={it.id ?? `${it.item_id}-${it.component_name}`}>
                      <div className="os-item-info">
                        <strong className="os-item-name">
                          {it.component_name || `Item #${it.item_id}`}
                        </strong>
                        <span className="os-item-meta">
                          Qty {qty} · PKR {Math.round(unit).toLocaleString()} each
                        </span>
                      </div>
                      <span className="os-item-total">PKR {total.toLocaleString()}</span>
                    </li>
                  );
                })}
              </ul>
            )}
            <div className="order-price-breakdown" role="table" aria-label="Order pricing">
              <div className="order-price-row">
                <span>Subtotal (items)</span>
                <span>PKR {priceBreakdown.itemsSubtotal.toLocaleString()}</span>
              </div>
              <div className="order-price-row order-price-row--shipping">
                <span>Shipping (system)</span>
                <span>PKR {priceBreakdown.shipping.toLocaleString()}</span>
              </div>
              <div className="order-price-row order-price-row--total">
                <span>Total</span>
                <span>PKR {priceBreakdown.total.toLocaleString()}</span>
              </div>
            </div>
            <div className="os-detail-grid">
              {order.shipping_address && (
                <div className="os-detail-item">
                  <span className="os-detail-item__label">Delivery</span>
                  <span className="os-detail-item__value">{order.shipping_address}</span>
                </div>
              )}
            </div>
          </section>

          <section className="status-timeline os-section" aria-labelledby="order-status-heading">
            <div className="os-section__head">
              <span className="os-section__icon" aria-hidden="true">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                  <circle cx="12" cy="10" r="3" />
                </svg>
              </span>
              <h3 id="order-status-heading">Order Status</h3>
            </div>
            {order.status === 'rejected' || order.status === 'cancelled' ? (
              <p className="order-rejected-msg" role="status">
                {order.status === 'cancelled' ? 'This order was cancelled.' : 'This order was rejected. Details appear in the timeline below.'}
              </p>
            ) : (
              <>
                <p className="os-section__hint">Follow your build from placement through delivery.</p>
                {order.status === 'ready_to_dispatch' ? (
                  <p className="os-ready-ship-banner" role="status">
                    Your build is complete. Vendors will ship to your saved address — you do not need to check out again.
                  </p>
                ) : null}
                <div className="os-stepper-wrap">
                  <div className="status-bar">
                    {ORDER_STAGES.map((step, idx) => (
                      <div
                        key={step.key}
                        className={`status-step ${idx <= currentStepIndex ? 'active' : ''} ${idx === currentStepIndex ? 'current' : ''}`}
                      >
                        <div className="step-icon">{STEP_ICONS[step.key] || step.icon}</div>
                        <div className="step-label">{step.label}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </section>

          <section className="timeline-entries os-section" aria-labelledby="timeline-heading">
            <div className="os-section__head">
              <span className="os-section__icon" aria-hidden="true">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                  <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                </svg>
              </span>
              <div>
                <h3 id="timeline-heading">Timeline &amp; Notifications</h3>
                <p className="os-section__sub">Updates as your order moves through each stage</p>
              </div>
            </div>
            <ul className="os-feed" aria-label="Order activity">
              {timeline.map((entry, idx) => {
                const meta = timelineEntryMeta(entry.message, entry.status);
                const isLatest = idx === timeline.length - 1;
                return (
                  <li
                    key={`${entry.timestamp}-${idx}`}
                    className={`os-feed-item os-feed-item--${meta.tone}${isLatest ? ' os-feed-item--latest' : ''}`}
                  >
                    <span className="os-feed-item__rail" aria-hidden="true">
                      <span className="os-feed-item__icon">{meta.icon}</span>
                    </span>
                    <div className="os-feed-item__body">
                      <div className="os-feed-item__top">
                        <p className="os-feed-item__message">{entry.message}</p>
                        {isLatest && <span className="os-feed-item__pill">Latest</span>}
                      </div>
                      <time className="os-feed-item__time" dateTime={entry.timestamp || undefined}>
                        {formatTime(entry.timestamp)}
                      </time>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>

          <section className="timeline-entries os-section" aria-labelledby="vendor-progress-heading">
            <div className="os-section__head">
              <span className="os-section__icon" aria-hidden="true">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 9l1.5-5h15L21 9" />
                  <path d="M4 9v10a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V9" />
                  <path d="M3 9h18" />
                  <path d="M9 20v-6h6v6" />
                </svg>
              </span>
              <div>
                <h3 id="vendor-progress-heading">Per-Vendor Progress</h3>
                <p className="os-section__sub">Each supplier fulfills their part of your build</p>
              </div>
            </div>
            {!order.vendor_orders?.length ? (
              <div className="os-empty-vendor">
                <div className="os-empty-vendor__icon" aria-hidden="true">
                  <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="9" />
                    <path d="M12 7v5l3 2" />
                  </svg>
                </div>
                <p>Vendor orders will appear here after admin approval.</p>
              </div>
            ) : (
              <div className="os-vendor-grid">
                {(order.vendor_orders || []).map((vo) => {
                  const shop = vo.vendor_shop_name || `Vendor #${vo.vendor_id}`;
                  const vMeta = vendorStatusMeta(vo.status);
                  return (
                    <article key={vo.id} className="os-vendor-card">
                      <header className="os-vendor-card__head">
                        <div className="os-vendor-card__identity">
                          <span className="os-vendor-card__avatar" aria-hidden="true">
                            {vendorInitials(shop)}
                          </span>
                          <div>
                            <h4 className="os-vendor-card__name">{shop}</h4>
                            <span className={`os-vendor-badge ${vMeta.badge}`}>{vMeta.label}</span>
                          </div>
                        </div>
                        <span className="os-vendor-card__amount">
                          PKR {Number(vo.total_amount || 0).toLocaleString()}
                        </span>
                      </header>
                      <div className="os-vendor-card__progress" aria-hidden="true">
                        <div
                          className="os-vendor-card__progress-fill"
                          style={{ width: `${vMeta.progress}%` }}
                        />
                      </div>
                      <p className="os-vendor-card__progress-label">
                        <span>Fulfillment</span>
                        <span>{vMeta.progress}%</span>
                      </p>
                      {(vo.items || []).length > 0 && (
                        <ul className="os-vendor-card__items">
                          {(vo.items || []).map((it, i) => (
                            <li key={it.id ?? i}>
                              <span className="os-vendor-card__item-name">{it.component_name}</span>
                              <span className="os-vendor-card__item-qty">×{it.quantity}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
};

export default OrderStatus;
