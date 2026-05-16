import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ecomGetCart, ecomRemoveItem, ecomSendForApproval, ecomResetRejected } from '../api/ecomApi';
import './ecommerce.css';

/**
 * eCommerce cart: line items, send for admin approval, then checkout when approved.
 */
const CartPage = () => {
  const { isLoggedIn } = useAuth();
  const [cart, setCart] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!isLoggedIn) {
      setLoading(false);
      return;
    }
    setErr(null);
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

  const remove = async (itemId) => {
    setBusy(true);
    try {
      const res = await ecomRemoveItem(itemId);
      setCart(res.cart);
    } catch (e) {
      setErr(e.data?.error || e.message);
    } finally {
      setBusy(false);
    }
  };

  const sendApproval = async () => {
    if (!cart) return;
    if (!window.confirm('Send this cart to admin for approval?')) return;
    setBusy(true);
    try {
      const res = await ecomSendForApproval(cart.id);
      setCart(res.cart);
    } catch (e) {
      setErr(e.data?.error || e.message);
    } finally {
      setBusy(false);
    }
  };

  const resetCart = async () => {
    if (!cart) return;
    if (!window.confirm('Clear this rejected cart and start over?')) return;
    setBusy(true);
    try {
      const res = await ecomResetRejected(cart.id);
      setCart(res.cart);
    } catch (e) {
      setErr(e.data?.error || e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!isLoggedIn) {
    return (
      <div className="ecom-page container">
        <h1 className="ecom-title">eCommerce cart</h1>
        <p className="ecom-muted">Sign in to use the shop cart and approval flow.</p>
        <Link to={{ pathname: '/ecom/cart', search: '?login=1' }} className="btn btn-primary">
          Sign in
        </Link>
        <p className="ecom-nav-hint" style={{ marginTop: 24 }}>
          <Link to="/">Home</Link>
        </p>
      </div>
    );
  }

  if (loading) {
    return <div className="ecom-page container">Loading…</div>;
  }

  const s = cart?.status;

  return (
    <div className="ecom-page container">
      <h1 className="ecom-title">eCommerce cart</h1>
      {err ? (
        <p className="ecom-muted" style={{ color: 'var(--error)' }}>
          {err}
        </p>
      ) : null}

      {cart && (
        <div className="ecom-card">
          <h2 style={{ fontSize: '1.1rem', marginBottom: 12 }}>Your order lines</h2>
          {(!cart.items || cart.items.length === 0) && <p>Cart is empty.</p>}
          {(cart.items || []).map((it) => (
            <div key={it.id} className="ecom-line">
              <span>
                {it.name} × {it.quantity}
              </span>
              <span>PKR {it.line_total?.toFixed(2) ?? (it.unit_price * it.quantity).toFixed(2)}</span>
              {s === 'active' && (
                <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => remove(it.id)}>
                  Remove
                </button>
              )}
            </div>
          ))}
          <p style={{ marginTop: 12, fontWeight: 700 }}>
            Total: PKR {Number(cart.total_amount || 0).toFixed(2)}
          </p>

          {s === 'active' && (cart.items || []).length > 0 && (
            <button type="button" className="btn btn-primary" style={{ marginTop: 8 }} disabled={busy} onClick={sendApproval}>
              Send for approval
            </button>
          )}
          {s === 'rejected' && (
            <button type="button" className="btn btn-secondary" style={{ marginTop: 8 }} disabled={busy} onClick={resetCart}>
              Start over
            </button>
          )}
          {s === 'approved' && (cart.items || []).length > 0 && (
            <Link to="/ecom/checkout" className="btn btn-primary" style={{ display: 'inline-block', marginTop: 8 }}>
              Proceed to checkout
            </Link>
          )}
        </div>
      )}
    </div>
  );
};

export default CartPage;
