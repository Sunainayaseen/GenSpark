import { useEffect, useState, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ecomGetCart, ecomPlaceOrder } from '../api/ecomApi';
import './ecommerce.css';

const CheckoutPage = () => {
  const { isLoggedIn } = useAuth();
  const navigate = useNavigate();
  const [cart, setCart] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: '', phone: '', address: '', city: '', payment_method: 'cod' });
  const [err, setErr] = useState(null);

  const load = useCallback(async () => {
    if (!isLoggedIn) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const c = await ecomGetCart();
      setCart(c.cart);
    } catch (e) {
      setErr(e.data?.error || e.message);
    } finally {
      setLoading(false);
    }
  }, [isLoggedIn]);

  useEffect(() => {
    load();
  }, [load]);

  if (!isLoggedIn) {
    return (
      <div className="ecom-page container">
        <p>Sign in to checkout.</p>
        <Link to={{ pathname: '/ecom/checkout', search: '?login=1' }} className="btn btn-primary">
          Sign in
        </Link>
      </div>
    );
  }

  if (loading) return <div className="ecom-page container">Loading…</div>;

  if (cart && cart.status !== 'approved') {
    return (
      <div className="ecom-page container">
        <h1 className="ecom-title">Checkout / blocked</h1>
        <p className="ecom-muted">Checkout is only allowed when your cart status is approved.</p>
        <p className="ecom-badge ecom-badge--pending">{cart.status_label}</p>
        <p style={{ marginTop: 16 }}>
          <Link to="/ecom/cart" className="btn btn-primary">
            Back to cart
          </Link>
        </p>
      </div>
    );
  }

  if (!cart || !cart.items?.length) {
    return (
      <div className="ecom-page container">
        <p>Cart is empty. Add products from the cart first.</p>
        <Link to="/ecom/cart" className="btn btn-primary">
          Go to cart
        </Link>
      </div>
    );
  }

  const onSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setErr(null);
    try {
      const res = await ecomPlaceOrder(form);
      const id = res.order?.id;
      navigate(id ? `/ecom/success?orderId=${id}` : '/ecom/success');
    } catch (e2) {
      setErr(e2.data?.error || e2.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="ecom-page container">
      <h1 className="ecom-title">Checkout</h1>
      <p className="ecom-muted">Shipping details and order summary. Payment method for demo: COD or online label.</p>
      {err ? <p className="ecom-muted" style={{ color: 'var(--error)' }}>{err}</p> : null}
      <div className="ecom-card" style={{ maxWidth: 560 }}>
        <h2>Order summary</h2>
        {cart.items.map((it) => (
          <div key={it.id} className="ecom-line">
            <span>
              {it.name} × {it.quantity}
            </span>
            <span>PKR {Number(it.line_total || 0).toFixed(2)}</span>
          </div>
        ))}
        <p style={{ fontWeight: 800, marginTop: 8 }}>Total: PKR {Number(cart.total_amount || 0).toFixed(2)}</p>
      </div>
      <form onSubmit={onSubmit} className="ecom-form ecom-card" style={{ maxWidth: 560 }}>
        <div className="form-group">
          <label>Full name</label>
          <input
            required
            name="name"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <label>Phone</label>
          <input
            required
            name="phone"
            value={form.phone}
            onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <label>Address</label>
          <input
            required
            name="address"
            value={form.address}
            onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <label>City</label>
          <input
            required
            name="city"
            value={form.city}
            onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <label>Payment</label>
          <select
            className="form-group"
            value={form.payment_method}
            onChange={(e) => setForm((f) => ({ ...f, payment_method: e.target.value }))}
            style={{ maxWidth: 200, padding: '0.5rem' }}
          >
            <option value="cod">Cash on delivery</option>
            <option value="card">Card (demo)</option>
          </select>
        </div>
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? 'Placing…' : 'Place order'}
        </button>
        <p style={{ marginTop: 12 }}>
          <Link to="/ecom/cart" className="ecom-nav-hint">
            ← Back to cart
          </Link>
        </p>
      </form>
    </div>
  );
};

export default CheckoutPage;
