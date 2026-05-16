import { useCart } from '../context/CartContext';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useBlockingOrder } from '../hooks/useBlockingOrder';
import './CartPage.css';

const CartPage = () => {
  const { cartItems, vendorGroups, cartTotal, updateQuantity, removeFromCart, clearCart, cartLoading, toast } = useCart();
  const { blockingOrder } = useBlockingOrder();
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const checkoutBlocked = Boolean(blockingOrder);

  const handleEmpty = async () => {
    const ok = window.confirm('Are you sure you want to empty the cart?');
    if (!ok) return;
    setBusy(true);
    try {
      await clearCart();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="cart-page">
      <div className="container">
        <div className="page-header">
          <h1>Your Cart</h1>
          <div className="cart-page-actions">
            <button className="btn btn-secondary" onClick={handleEmpty} disabled={cartItems.length === 0 || busy}>
              {busy ? 'Emptying...' : 'Empty Cart'}
            </button>
          </div>
        </div>

        {cartLoading ? (
          <div className="cart-loading">Loading cart...</div>
        ) : cartItems.length === 0 ? (
          <div className="cart-empty-state">
            <div className="empty-icon">🛒</div>
            <p>Your cart is empty.</p>
          </div>
        ) : (
          <>
            {vendorGroups.map((group) => (
              <div key={String(group.vendor_id || 0)} className="cart-table" style={{ marginBottom: 20 }}>
                <div className="cart-row" style={{ background: '#f8f9fb' }}>
                  <div className="cart-cell cart-name"><strong>Vendor: {group.vendor_name}</strong></div>
                  <div className="cart-cell cart-price"></div>
                  <div className="cart-cell cart-qty"></div>
                  <div className="cart-cell cart-subtotal"><strong>PKR {Number(group.subtotal || 0).toLocaleString()}</strong></div>
                  <div className="cart-cell cart-remove"></div>
                </div>
                {group.items.map((item) => (
                  <div className="cart-row" key={item.cart_item_id}>
                    <div className="cart-cell cart-name">
                      <div className="cart-product-title">{item.component_name || item.name}</div>
                      {item.image_url ? (
                        <img className="cart-product-image" src={item.image_url} alt={item.component_name || item.name} />
                      ) : null}
                    </div>

                    <div className="cart-cell cart-price">PKR {Number(item.price || 0).toLocaleString()}</div>

                    <div className="cart-cell cart-qty">
                      <button type="button" className="qty-btn" onClick={() => updateQuantity(item.cart_item_id, item.quantity - 1)}>−</button>
                      <span className="qty-value">{item.quantity}</span>
                      <button
                        type="button"
                        className="qty-btn"
                        onClick={() => updateQuantity(item.cart_item_id, item.quantity + 1)}
                        disabled={item.stock !== undefined && item.stock >= 0 && item.quantity >= item.stock}
                        title={item.stock !== undefined ? `Stock: ${item.stock}` : ''}
                      >
                        +
                      </button>
                    </div>

                    <div className="cart-cell cart-subtotal">
                      PKR {Number(item.subtotal || 0).toLocaleString()}
                    </div>

                    <div className="cart-cell cart-remove">
                      <button type="button" className="remove-item-btn" onClick={() => removeFromCart(item.cart_item_id)}>Remove</button>
                    </div>
                  </div>
                ))}
              </div>
            ))}

            <div className="cart-total-summary">
              <div className="cart-total-row">
                <span>Total Bill</span>
                <span className="cart-total-amount">PKR {cartTotal.toLocaleString()}</span>
              </div>
              {blockingOrder ? (
                <p className="cart-checkout-blocked-msg" role="status">
                  You have an order awaiting admin. Another checkout is available after that order is approved or
                  rejected.{' '}
                  <button
                    type="button"
                    className="link-inline"
                    onClick={() => navigate(`/order/${blockingOrder.id}`)}
                  >
                    View {blockingOrder.order_number ? `order #${blockingOrder.order_number}` : 'order'}
                  </button>
                </p>
              ) : null}
              <button
                type="button"
                className="btn btn-primary cart-checkout-btn"
                onClick={() => navigate('/checkout')}
                disabled={checkoutBlocked}
                title={checkoutBlocked ? 'Wait for admin to approve or reject your pending order' : undefined}
              >
                Proceed to Checkout
              </button>
            </div>

            {toast ? (
              <div className={`cart-inline-toast ${toast.type}`}>
                {toast.message}
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
};

export default CartPage;

