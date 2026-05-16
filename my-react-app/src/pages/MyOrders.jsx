import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { dashboardGet } from '../api/dashboardApi';
import './MyOrders.css';

const MyOrders = () => {
  const { user } = useAuth();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const res = await dashboardGet('/orders?mine=1&limit=50');
        if (!cancelled) {
          setOrders(Array.isArray(res?.orders) ? res.orders : []);
          setError('');
        }
      } catch (e) {
        if (!cancelled) {
          setOrders([]);
          setError(e?.data?.error || e?.message || 'Could not load orders');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user]);

  if (!user) {
    return (
      <div className="my-orders-page">
        <div className="container">
          <h1>My Orders</h1>
          <p>Please sign in to view your orders.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="my-orders-page">
      <div className="container">
        <h1>My Orders</h1>
        <p className="my-orders-lead">Pending → Approved → Processing → Completed (per vendor after admin approval)</p>
        {loading && <p>Loading…</p>}
        {error && <p className="my-orders-error" role="alert">{error}</p>}
        {!loading && !error && orders.length === 0 && (
          <p>No orders yet. <Link to="/builds">Browse predefined PCs</Link> or use the configurator.</p>
        )}
        <ul className="my-orders-list">
          {orders.map((o) => (
            <li key={o.id} className="my-orders-row">
              <div>
                <strong>{o.order_number || `#${o.id}`}</strong>
                <span className="my-orders-status">{o.status}</span>
              </div>
              <div className="my-orders-meta">
                PKR {Number(o.total_amount || 0).toLocaleString()}
                {o.created_at ? ` · ${new Date(o.created_at).toLocaleString('en-PK')}` : ''}
              </div>
              <Link className="btn btn-secondary btn-sm" to={`/order/${o.id}`}>Track</Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default MyOrders;
