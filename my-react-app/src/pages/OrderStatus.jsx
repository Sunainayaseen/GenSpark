import { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { dashboardGet } from '../api/dashboardApi';
import { ORDER_STAGES, getStageIndex } from '../constants/orderStages';
import './OrderStatus.css';

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

const OrderStatus = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!id) {
      setOrder(null);
      setError('Invalid order link (missing id).');
      setLoading(false);
      return;
    }
    const loadOrder = async () => {
      setLoading(true);
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
      }
    };
    loadOrder();
  }, [id]);

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
        <div className="container"><p>Loading order...</p></div>
      </div>
    );
  }

  if (!order || error) {
    return (
      <div className="order-status-page">
        <div className="container">
          <div className="page-header">
            <h1>Order #{id}</h1>
          </div>
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
            <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              <button type="button" className="btn btn-primary" onClick={() => navigate('/builds')}>
                View predefined PCs
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
        <div className="page-header">
          <h1>{order.order_number || `Order #${order.id}`}</h1>
          {isEcom ? (
            <button type="button" className="btn btn-secondary" disabled>
              Shop order — {order.status}
            </button>
          ) : order.status === 'pending' ? (
            <button type="button" className="btn btn-secondary" disabled>Waiting for Admin Approval</button>
          ) : order.status === 'rejected' ? (
            <button type="button" className="btn btn-secondary" disabled>Rejected</button>
          ) : order.status === 'ready_to_dispatch' ? (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => navigate('/checkout')}
            >
              Place order
            </button>
          ) : order.status === 'shipped' ? (
            <button type="button" className="btn btn-secondary" disabled>Shipped</button>
          ) : order.status === 'completed' ? (
            <button type="button" className="btn btn-secondary" disabled>Completed</button>
          ) : (
            <button type="button" className="btn btn-secondary" disabled>Vendor orders in progress</button>
          )}
        </div>

        <div className="order-content">
          <div className="order-card">
            <div className="order-header">
              <h2>{isEcom ? 'Shop order' : 'GenSpark order'}</h2>
              <div className="order-price">PKR {priceBreakdown.total.toLocaleString()}</div>
            </div>
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
            <div className="order-vendor">
              <span className="vendor-label">Vendor:</span>
              <span className="vendor-name">
                {isEcom ? 'N/A (direct shop order)' : 'Multi-vendor split by admin approval'}
              </span>
            </div>
            {order.shipping_address && (
              <div className="order-payment">
                <span className="payment-label">Shipping:</span>
                <span>{order.shipping_address}</span>
              </div>
            )}
          </div>

          <div className="status-timeline">
            <h3>Order Status</h3>
            {order.status === 'rejected' || order.status === 'cancelled' ? (
              <p className="order-rejected-msg" role="status">
                {order.status === 'cancelled' ? 'This order was cancelled.' : 'This order was rejected. Details appear in the timeline below.'}
              </p>
            ) : (
              <div className="status-bar">
                {ORDER_STAGES.map((step, idx) => (
                  <div
                    key={step.key}
                    className={`status-step ${idx <= currentStepIndex ? 'active' : ''} ${idx === currentStepIndex ? 'current' : ''}`}
                  >
                    <div className="step-icon">{step.icon}</div>
                    <div className="step-label">{step.label}</div>
                    {idx < ORDER_STAGES.length - 1 && (
                      <div className={`step-connector ${idx < currentStepIndex ? 'active' : ''}`}></div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="timeline-entries">
            <h3>Timeline & Notifications</h3>
            <div className="timeline-list">
              {timeline.map((entry, idx) => (
                <div key={idx} className="timeline-entry">
                  <div className="timeline-dot"></div>
                  <div className="timeline-content">
                    <div className="timeline-header">
                      <span className="timeline-message">{entry.message}</span>
                      <span className="timeline-time">{formatTime(entry.timestamp)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="timeline-entries">
            <h3>Per-Vendor Progress</h3>
            <div className="timeline-list">
              {(order.vendor_orders || []).map((vo) => (
                <div key={vo.id} className="timeline-entry">
                  <div className="timeline-dot"></div>
                  <div className="timeline-content">
                    <div className="timeline-header">
                      <span className="timeline-message">
                        {vo.vendor_shop_name || `Vendor #${vo.vendor_id}`} — {vo.status}
                      </span>
                      <span className="timeline-time">PKR {Number(vo.total_amount || 0).toLocaleString()}</span>
                    </div>
                    <div className="whatsapp-preview">
                      <span className="whatsapp-text">
                        {(vo.items || []).map((it) => `${it.component_name} x${it.quantity}`).join(', ')}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
              {!order.vendor_orders?.length && (
                <div className="timeline-entry">
                  <div className="timeline-content">Vendor orders will appear after admin approval.</div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OrderStatus;







