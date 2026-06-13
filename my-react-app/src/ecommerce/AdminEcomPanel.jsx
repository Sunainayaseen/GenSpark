import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  ecomAdminCarts,
  ecomAdminApproveCart,
  ecomAdminRejectCart,
  ecomAdminOrders,
  ecomAdminSetOrderStatus,
} from '../api/ecomApi';
import { useConfirm } from '../components/ConfirmProvider';
import './ecommerce.css';

const ORDER_STATUS_OPTIONS = ['pending', 'processing', 'shipped', 'delivered', 'cancelled'];

const AdminEcomPanel = () => {
  const { isLoggedIn, isAdmin, user } = useAuth();
  const { confirm } = useConfirm();
  const [carts, setCarts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  const [tab, setTab] = useState('carts');

  const loadCarts = useCallback(async () => {
    setErr(null);
    const r = await ecomAdminCarts('pending_approval');
    setCarts(r.carts || []);
  }, []);

  const loadOrders = useCallback(async () => {
    setErr(null);
    const r = await ecomAdminOrders();
    setOrders(r.orders || []);
  }, []);

  const refresh = async () => {
    try {
      if (tab === 'carts') await loadCarts();
      else await loadOrders();
      setMsg('Refreshed');
    } catch (e) {
      setErr(e.data?.error || e.message);
    }
  };

  useEffect(() => {
    if (!isLoggedIn || !isAdmin) return;
    (async () => {
      try {
        setErr(null);
        if (tab === 'carts') await loadCarts();
        else await loadOrders();
      } catch (e) {
        setErr(e.data?.error || e.message);
      }
    })();
  }, [isLoggedIn, isAdmin, tab, loadCarts, loadOrders]);

  const approve = async (id) => {
    const ok = await confirm({
      title: 'Approve cart?',
      message: 'Approve this cart so the customer can proceed to checkout?',
      confirmText: 'Approve',
    });
    if (!ok) return;
    try {
      await ecomAdminApproveCart(id);
      setMsg('Approved');
      await loadCarts();
    } catch (e) {
      setErr(e.data?.error || e.message);
    }
  };

  const reject = async (id) => {
    const ok = await confirm({
      title: 'Reject cart?',
      message: 'Reject this cart and send it back to the customer?',
      confirmText: 'Reject',
      danger: true,
    });
    if (!ok) return;
    try {
      await ecomAdminRejectCart(id);
      setMsg('Rejected');
      await loadCarts();
    } catch (e) {
      setErr(e.data?.error || e.message);
    }
  };

  const setOStatus = async (id, status) => {
    try {
      await ecomAdminSetOrderStatus(id, status);
      setMsg('Order updated');
      await loadOrders();
    } catch (e) {
      setErr(e.data?.error || e.message);
    }
  };

  if (!isLoggedIn) {
    return (
      <div className="ecom-page container">
        <p>Admin: sign in first. Use the header login, then return here.</p>
        <p>
          <Link to={{ pathname: '/ecom/admin', search: '?login=1' }} className="btn btn-primary">
            Open login
          </Link>
        </p>
        <p className="ecom-muted">Demo admin: admin@genspark.com (from your App)</p>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="ecom-page container">
        <h1>Admin (ecom)</h1>
        <p>Your account is not an admin. Logged in as: {user?.email}</p>
        <p>
          <Link to="/ecom/cart" className="btn btn-primary">
            Shop
          </Link>
        </p>
      </div>
    );
  }

  return (
    <div className="ecom-page container" style={{ maxWidth: 960 }}>
      <h1 className="ecom-title">eCommerce — Admin</h1>
      <p className="ecom-muted">Approve customer carts, then track orders. Uses Flask session + JSON.</p>
      {msg && <p style={{ color: 'green' }}>{msg}</p>}
      {err && <p style={{ color: 'var(--error)' }}>{err}</p>}

      <p className="ecom-nav-hint" style={{ marginBottom: 16 }}>
        <button
          type="button"
          className={`btn btn-sm ${tab === 'carts' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setTab('carts')}
        >
          Carts
        </button>
        <button
          type="button"
          className={`btn btn-sm ${tab === 'orders' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setTab('orders')}
        >
          Orders
        </button>
        <button type="button" className="btn btn-sm btn-secondary" onClick={refresh}>
          Refresh
        </button>
        <Link to="/ecom/cart">User cart</Link>
      </p>

      {tab === 'carts' && (
        <div className="ecom-card">
          <h2>Pending approval</h2>
          <table className="ecom-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>User</th>
                <th>Status</th>
                <th>Total</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {carts.map((c) => (
                <tr key={c.id}>
                  <td>{c.id}</td>
                  <td>
                    {c.user_name} <br />
                    <small className="ecom-muted">{c.user_email}</small>
                  </td>
                  <td>
                    {c.status} — {c.status_label}
                  </td>
                  <td>PKR {Number(c.total_amount).toFixed(2)}</td>
                  <td>
                    <button type="button" className="btn btn-success btn-sm" onClick={() => approve(c.id)}>
                      Approve
                    </button>{' '}
                    <button type="button" className="btn btn-danger btn-sm" onClick={() => reject(c.id)}>
                      Reject
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {carts.length === 0 && <p className="ecom-muted">No carts in pending_approval.</p>}
        </div>
      )}

      {tab === 'orders' && (
        <div className="ecom-card">
          <h2>All ecom orders</h2>
          <table className="ecom-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Customer</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td>
                    {o.order_number} <br />
                    <small>id {o.id}</small>
                  </td>
                  <td>PKR {Number(o.total_amount).toFixed(2)}</td>
                  <td>{o.status}</td>
                  <td>
                    {o.name} / {o.phone} / {o.city}
                  </td>
                  <td>
                    <select
                      value={o.status}
                      onChange={(e) => setOStatus(o.id, e.target.value)}
                      className="form-group"
                    >
                      {ORDER_STATUS_OPTIONS.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default AdminEcomPanel;
