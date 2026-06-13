import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ecomGetOrder } from '../api/ecomApi';
import './ecommerce.css';

const OrderSuccess = () => {
  const [search] = useSearchParams();
  const orderId = search.get('orderId');
  const [order, setOrder] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!orderId) {
      setErr('No order id');
      return;
    }
    ecomGetOrder(orderId)
      .then((r) => setOrder(r.order))
      .catch((e) => setErr(e.data?.error || e.message));
  }, [orderId]);

  return (
    <div className="ecom-page container">
      <h1 className="ecom-title">Order placed</h1>
      {err && <p className="ecom-muted" style={{ color: 'var(--error)' }}>{err}</p>}
      {order && (
        <div className="ecom-card" style={{ maxWidth: 520 }}>
          <p>
            <strong>Order {order.order_number || `#${order.id}`}</strong> — {order.status}
          </p>
          <p>Total: PKR {Number(order.total_amount).toFixed(2)}</p>
          <p>Payment: {order.payment_method}</p>
          <h3 className="ecom-muted" style={{ marginTop: 16, fontSize: 14 }}>
            Items
          </h3>
          {(order.items || []).map((it) => (
            <div key={it.id} className="ecom-line">
              <span>
                {it.name} × {it.quantity}
              </span>
              <span>PKR {Number(it.line_total).toFixed(2)}</span>
            </div>
          ))}
        </div>
      )}
      <p className="ecom-nav-hint" style={{ marginTop: 24 }}>
        <Link to="/ecom/cart" className="btn btn-primary">
          Back to shop cart
        </Link>
        <Link to="/"> Home</Link>
        <Link to="/ecom/admin" style={{ opacity: 0.6 }}>
          Admin
        </Link>
      </p>
    </div>
  );
};

export default OrderSuccess;
