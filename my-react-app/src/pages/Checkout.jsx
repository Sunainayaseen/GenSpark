import { useMemo, useState, useCallback, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { loadStripe } from '@stripe/stripe-js';
import { Elements } from '@stripe/react-stripe-js';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';
import { useBlockingOrder } from '../hooks/useBlockingOrder';
import { dashboardPost } from '../api/dashboardApi';
import { listAddresses } from '../api/addressesApi';
import CheckoutForm from '../components/CheckoutForm';
import { useConfirm } from '../components/ConfirmProvider';
import { ASSEMBLY_FEE, cartNeedsAssembly } from '../utils/assemblyFee';
import './Checkout.css';

const stripePublishableKey = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY || '';
const stripePromise = stripePublishableKey ? loadStripe(stripePublishableKey) : null;

const initialAddress = () => ({
  fullName: '',
  phone: '',
  addressLine1: '',
  addressLine2: '',
  city: '',
  province: '',
  postalCode: '',
});

const buildShippingAddress = (a) => {
  const lines = [
    a.fullName.trim(),
    a.phone.trim(),
    [a.addressLine1.trim(), a.addressLine2.trim()].filter(Boolean).join(', '),
    [a.city.trim(), a.province.trim()].filter(Boolean).join(', '),
  ].filter(Boolean);
  if (a.postalCode.trim()) lines.push(`Postal code: ${a.postalCode.trim()}`);
  return lines.join('\n');
};

const Checkout = () => {
  const navigate = useNavigate();
  const { user, isLoggedIn } = useAuth();
  const { notify } = useConfirm();
  const { blockingOrder, checkingBlocking } = useBlockingOrder();
  const { cartItems, vendorGroups, cartTotal, clearCart, cartLoading, buildVendorConflict } = useCart();

  const [address, setAddress] = useState(initialAddress);
  const [savedAddresses, setSavedAddresses] = useState([]);
  const [selectedAddrId, setSelectedAddrId] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('cod');

  // Load the user's saved addresses; auto-fill the default one for convenience.
  useEffect(() => {
    if (!isLoggedIn) { setSavedAddresses([]); return; }
    let alive = true;
    listAddresses()
      .then((rows) => {
        if (!alive) return;
        setSavedAddresses(rows);
        const def = rows.find((r) => r.is_default) || rows[0];
        if (def) { setSelectedAddrId(String(def.id)); applySavedAddress(def); }
      })
      .catch(() => {});
    return () => { alive = false; };
  }, [isLoggedIn]);

  const applySavedAddress = (a) => {
    if (!a) return;
    setAddress((prev) => ({
      ...prev,
      fullName: a.full_name || prev.fullName,
      phone: a.phone || prev.phone,
      addressLine1: a.line1 || '',
      addressLine2: '',
      city: a.city || '',
      postalCode: a.postal_code || '',
    }));
    setFormErrors({});
  };

  const onPickSaved = (e) => {
    const id = e.target.value;
    setSelectedAddrId(id);
    if (id === '') { setAddress(initialAddress()); return; }   // "New address"
    const a = savedAddresses.find((x) => String(x.id) === id);
    applySavedAddress(a);
  };
  const [formErrors, setFormErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const shipping = useMemo(() => (cartItems.length > 0 ? 2000 : 0), [cartItems.length]);
  const assembly = useMemo(() => (cartNeedsAssembly(cartItems) ? ASSEMBLY_FEE : 0), [cartItems]);
  const grandTotal = cartTotal + shipping + assembly;
  const itemCount = useMemo(
    () => cartItems.reduce((sum, item) => sum + (item.quantity || 0), 0),
    [cartItems],
  );

  const stripeCartItems = useMemo(
    () =>
      cartItems.map((item) => ({
        product_id: item.product_id || item.component_id || item.id,
        quantity: item.quantity,
        price: item.price,
        vendor_id: item.vendor_id ?? null,
      })),
    [cartItems],
  );

  const handleStripeSuccess = async (dbRes) => {
    await clearCart().catch(() => {});
    navigate('/order-success', {
      replace: true,
      state: {
        orderId: dbRes.order_id,
        orderNumber: dbRes.order_number,
        totalAmount: grandTotal,
      },
    });
  };

  const handleAddressChange = (e) => {
    const { name, value } = e.target;
    setAddress((prev) => ({ ...prev, [name]: value }));
    if (formErrors[name]) {
      setFormErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
  };

  const validate = useCallback(() => {
    const err = {};
    if (!address.fullName.trim()) err.fullName = 'Full name is required';
    if (!address.phone.trim()) err.phone = 'Phone number is required';
    if (!address.addressLine1.trim()) err.addressLine1 = 'Street address is required';
    if (!address.city.trim()) err.city = 'City is required';
    setFormErrors(err);
    return Object.keys(err).length === 0;
  }, [address]);

  const validateForStripe = useCallback(() => validate(), [validate]);

  const handlePlaceOrder = async (e) => {
    e.preventDefault();
    if (submitting || blockingOrder) return;
    if (!validate()) return;
    setSubmitting(true);
    try {
      const shippingAddress = buildShippingAddress(address);
      const res = await dashboardPost('/orders/place', {
        payment_method: paymentMethod,
        shipping_address: shippingAddress,
      });

      const placed = res?.order;
      navigate('/order-success', {
        replace: true,
        state: {
          orderId: placed?.id,
          orderNumber: placed?.order_number,
          totalAmount: placed?.total_amount,
        },
      });
      clearCart().catch(() => {});
    } catch (err) {
      notify(err?.data?.error || err?.message || 'Order placement failed', { type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  const openSignIn = () => {
    navigate({ pathname: '/checkout', search: '?login=1' });
  };

  if (cartLoading) {
    return (
      <div className="checkout-page">
        <div className="container">
          <div className="checkout-empty">
            <p>Loading your cart…</p>
          </div>
        </div>
      </div>
    );
  }

  if (cartItems.length === 0) {
    return (
      <div className="checkout-page">
        <div className="container">
          <div className="checkout-empty">
            <h1>Checkout</h1>
            <p>Your cart is empty. Add components or a predefined PC before checkout.</p>
            <div className="checkout-empty-actions">
              <button type="button" className="btn btn-primary" onClick={() => navigate('/builds')}>
                Browse predefined PCs
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => navigate('/my-orders')}>
                View my orders
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!isLoggedIn || !user) {
    return (
      <div className="checkout-page">
        <div className="container checkout-auth-prompt">
          <div className="checkout-header">
            <h1>Checkout</h1>
            <p>Sign in to enter your shipping details and place your order.</p>
          </div>
          <div className="checkout-auth-card">
            <h2>Account required</h2>
            <p className="checkout-auth-copy">
              Orders are tied to your account for tracking and support. Log in to continue, or create an
              account from the sign-in window.
            </p>
            <div className="checkout-auth-actions">
              <button type="button" className="btn btn-primary btn-lg" onClick={openSignIn}>
                Sign in to continue
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => navigate('/cart')}>
                Back to cart
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="checkout-page">
      <div className="container">
        <header className="checkout-header">
          <div className="checkout-header-top">
            <div>
              <h1>Checkout</h1>
              <p>Secure delivery details and payment. Your order is reviewed before vendors ship.</p>
            </div>
            <span className="checkout-item-badge" aria-label={`${itemCount} items in cart`}>
              {itemCount} {itemCount === 1 ? 'item' : 'items'}
            </span>
          </div>
          <ol className="checkout-steps" aria-label="Checkout progress">
            <li className="is-active">
              <span className="step-num">1</span>
              Shipping
            </li>
            <li className={paymentMethod === 'online' ? 'is-active' : ''}>
              <span className="step-num">2</span>
              Payment
            </li>
            <li>
              <span className="step-num">3</span>
              Review
            </li>
          </ol>
        </header>

        {blockingOrder ? (
          <div className="checkout-pending-alert" role="alert">
            <strong>Order waiting for admin</strong>
            <p>
              You can place another order only after admin approves or rejects your current one.{' '}
              <button type="button" className="link-inline" onClick={() => navigate(`/order/${blockingOrder.id}`)}>
                View order {blockingOrder.order_number ? `#${blockingOrder.order_number}` : `#${blockingOrder.id}`}
              </button>
            </p>
          </div>
        ) : null}

        <form onSubmit={handlePlaceOrder} noValidate>
          {checkingBlocking ? (
            <p className="checkout-checking" aria-live="polite">
              Verifying if you can place a new order…
            </p>
          ) : null}
          <div className="checkout-grid">
            <fieldset
              className="checkout-fieldset checkout-fieldset-main"
              disabled={Boolean(blockingOrder)}
            >
          <div className="checkout-main">
            <section className="checkout-card" aria-labelledby="ship-heading">
              <h2 id="ship-heading">Shipping address</h2>
              <p className="checkout-section-hint">We will use this for delivery and order updates.</p>

              {savedAddresses.length > 0 && (
                <div className="checkout-saved-addr">
                  <label htmlFor="savedAddr">Use a saved address</label>
                  <div className="checkout-saved-row">
                    <select id="savedAddr" value={selectedAddrId} onChange={onPickSaved} className="checkout-saved-select">
                      <option value="">+ Enter a new address</option>
                      {savedAddresses.map((a) => (
                        <option key={a.id} value={a.id}>
                          {(a.label ? `${a.label} — ` : '') + (a.line1 || '') + (a.city ? `, ${a.city}` : '')}{a.is_default ? ' (default)' : ''}
                        </option>
                      ))}
                    </select>
                    <Link to="/my-orders" className="checkout-saved-manage">Manage</Link>
                  </div>
                </div>
              )}

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="fullName">Full name</label>
                  <input
                    id="fullName"
                    name="fullName"
                    autoComplete="name"
                    value={address.fullName}
                    onChange={handleAddressChange}
                    className={formErrors.fullName ? 'input-error' : ''}
                    placeholder="Your full name"
                  />
                  {formErrors.fullName ? <span className="field-error">{formErrors.fullName}</span> : null}
                </div>
                <div className="form-group">
                  <label htmlFor="phone">Phone</label>
                  <input
                    id="phone"
                    name="phone"
                    type="tel"
                    autoComplete="tel"
                    value={address.phone}
                    onChange={handleAddressChange}
                    className={formErrors.phone ? 'input-error' : ''}
                    placeholder="+92 …"
                  />
                  {formErrors.phone ? <span className="field-error">{formErrors.phone}</span> : null}
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="addressLine1">Address line 1</label>
                <input
                  id="addressLine1"
                  name="addressLine1"
                  autoComplete="address-line1"
                  value={address.addressLine1}
                  onChange={handleAddressChange}
                  className={formErrors.addressLine1 ? 'input-error' : ''}
                  placeholder="House / street / area"
                />
                {formErrors.addressLine1 ? <span className="field-error">{formErrors.addressLine1}</span> : null}
              </div>

              <div className="form-group">
                <label htmlFor="addressLine2">Address line 2 (optional)</label>
                <input
                  id="addressLine2"
                  name="addressLine2"
                  autoComplete="address-line2"
                  value={address.addressLine2}
                  onChange={handleAddressChange}
                  placeholder="Apartment, building, landmark"
                />
              </div>

              <div className="form-row form-row-3">
                <div className="form-group">
                  <label htmlFor="city">City</label>
                  <input
                    id="city"
                    name="city"
                    autoComplete="address-level2"
                    value={address.city}
                    onChange={handleAddressChange}
                    className={formErrors.city ? 'input-error' : ''}
                    placeholder="Lahore"
                  />
                  {formErrors.city ? <span className="field-error">{formErrors.city}</span> : null}
                </div>
                <div className="form-group">
                  <label htmlFor="province">Province / region (optional)</label>
                  <input
                    id="province"
                    name="province"
                    value={address.province}
                    onChange={handleAddressChange}
                    placeholder="Punjab"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="postalCode">Postal code (optional)</label>
                  <input
                    id="postalCode"
                    name="postalCode"
                    autoComplete="postal-code"
                    value={address.postalCode}
                    onChange={handleAddressChange}
                    placeholder="54000"
                  />
                </div>
              </div>
            </section>

            <section className="checkout-card" aria-labelledby="pay-heading">
              <h2 id="pay-heading">Payment method</h2>
              <div className="payment-options" role="radiogroup" aria-label="How you will pay">
                <label
                  className={`payment-card ${paymentMethod === 'cod' ? 'is-selected' : ''}`}
                  htmlFor="pay-cod"
                >
                  <input
                    type="radio"
                    id="pay-cod"
                    name="paymentMethod"
                    value="cod"
                    checked={paymentMethod === 'cod'}
                    onChange={() => setPaymentMethod('cod')}
                  />
                  <span className="payment-card-body">
                    <span className="payment-title">Cash on delivery</span>
                    <span className="payment-desc">Pay 30% in advance to confirm your order, and the remaining amount on delivery. This ensures a secure and verified experience.</span>
                  </span>
                </label>

                <label
                  className={`payment-card ${paymentMethod === 'online' ? 'is-selected' : ''}`}
                  htmlFor="pay-online"
                >
                  <input
                    type="radio"
                    id="pay-online"
                    name="paymentMethod"
                    value="online"
                    checked={paymentMethod === 'online'}
                    onChange={() => setPaymentMethod('online')}
                  />
                  <span className="payment-card-body">
                    <span className="payment-title">Online payment</span>
                    <span className="payment-desc">Card, bank transfer, or digital wallet. Secure processing.</span>
                  </span>
                </label>
              </div>

              {paymentMethod === 'online' ? (
                stripePromise ? (
                  <Elements stripe={stripePromise}>
                    <CheckoutForm
                      amount={grandTotal}
                      userId={user.id}
                      cartItems={stripeCartItems}
                      shippingAddress={buildShippingAddress(address)}
                      shippingFee={shipping}
                      onValidate={validateForStripe}
                      onSuccess={handleStripeSuccess}
                      currencyLabel="PKR"
                      disabled={buildVendorConflict.hasConflict}
                    />
                  </Elements>
                ) : (
                  <div className="payment-notice" role="status">
                    <strong>Stripe not configured</strong>
                    <p>
                      Add <code>VITE_STRIPE_PUBLISHABLE_KEY</code> to <code>my-react-app/.env</code> and{' '}
                      <code>STRIPE_SECRET_KEY</code> to the Flask backend <code>.env</code>, then restart both
                      servers.
                    </p>
                  </div>
                )
              ) : null}
            </section>
          </div>
            </fieldset>

          <aside className="checkout-summary" aria-label="Order summary">
            <div className="checkout-summary-header">
              <h2>Order summary</h2>
              <span className="checkout-summary-count">{itemCount} items</span>
            </div>

            <ul className="checkout-trust" aria-label="Checkout guarantees">
              <li>Secure checkout</li>
              <li>PKR pricing</li>
              <li>Admin verified</li>
            </ul>

            {buildVendorConflict.hasConflict ? (
              <p className="checkout-vendor-conflict" role="alert">
                All selected components must be sourced from a single vendor because
                assembly is performed by the supplying vendor. Please choose
                components from one vendor only.
              </p>
            ) : buildVendorConflict.vendorName ? (
              <p className="checkout-vendor-summary">
                Build vendor: <strong>{buildVendorConflict.vendorName}</strong>
              </p>
            ) : null}

            <ul className="checkout-summary-items">
              {vendorGroups.length > 0
                ? vendorGroups.map((group) => (
                    <li key={String(group.vendor_id || 0)} className="checkout-summary-vendor">
                      <div className="checkout-summary-vendor-name">{group.vendor_name}</div>
                      <ul>
                        {(group.items || []).map((item) => (
                          <li
                            key={item.cart_item_id}
                            className={`checkout-summary-line${
                              buildVendorConflict.conflictingItemIds.includes(item.cart_item_id)
                                ? ' checkout-summary-line--conflict'
                                : ''
                            }`}
                          >
                            <span className="checkout-summary-line-title">
                              {item.component_name || item.name} × {item.quantity}
                            </span>
                            <span className="checkout-summary-line-price">
                              PKR {Number(item.subtotal || 0).toLocaleString('en-US')}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </li>
                  ))
                : cartItems.map((item) => (
                    <li key={item.id} className="checkout-summary-line">
                      <span className="checkout-summary-line-title">
                        {item.title || item.name} × {item.quantity}
                      </span>
                      <span className="checkout-summary-line-price">
                        PKR {((item.subtotal ?? (item.price || 0) * item.quantity) || 0).toLocaleString('en-US')}
                      </span>
                    </li>
                  ))}
            </ul>

            <div className="summary-divider" />

            <div className="summary-totals">
              <div className="summary-row">
                <span>Subtotal</span>
                <span>PKR {cartTotal.toLocaleString('en-US')}</span>
              </div>
              <div className="summary-row">
                <span>Shipping (estimate)</span>
                <span>PKR {shipping.toLocaleString('en-US')}</span>
              </div>
              {assembly > 0 ? (
                <div className="summary-row">
                  <span>Assembly service</span>
                  <span>PKR {assembly.toLocaleString('en-US')}</span>
                </div>
              ) : null}
              <div className="summary-row total">
                <span>Total</span>
                <span>PKR {grandTotal.toLocaleString('en-US')}</span>
              </div>
            </div>

            <p className="summary-note">All amounts in PKR. Shipping may be adjusted after admin approval.</p>

            {paymentMethod !== 'online' ? (
              <button
                type="submit"
                className="btn btn-primary btn-lg"
                disabled={submitting || Boolean(blockingOrder) || buildVendorConflict.hasConflict}
              >
                {submitting ? 'Placing order…' : 'Place order'}
              </button>
            ) : (
              <p className="checkout-stripe-hint">
                Complete card payment in the payment section. Stock updates after payment is confirmed.
              </p>
            )}
            <button type="button" className="btn btn-secondary" onClick={() => navigate('/cart')}>
              Back to cart
            </button>
          </aside>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Checkout;
