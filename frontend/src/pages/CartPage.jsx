import { useCart } from '../context/CartContext';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useBlockingOrder } from '../hooks/useBlockingOrder';
import { useConfirm } from '../components/ConfirmProvider';
import './CartPage.css';

const CartPage = () => {
  const { cartItems, vendorGroups, cartTotal, updateQuantity, removeFromCart, clearCart, cartLoading, toast } = useCart();
  const { confirm } = useConfirm();
  const { blockingOrder } = useBlockingOrder();
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const checkoutBlocked = Boolean(blockingOrder);

  const buildGroups = useMemo(() => {
    const groups = {};
    cartItems.forEach((item) => {
      if (!item.pc_build_id) return;
      const id = item.pc_build_id;
      if (!groups[id]) {
        groups[id] = {
          pc_build_id: id,
          componentCount: 0,
          quantity: 0,
          subtotal: 0,
        };
      }
      groups[id].componentCount += 1;
      groups[id].quantity += Number(item.quantity || 0);
      groups[id].subtotal += Number(item.subtotal || 0);
    });
    return Object.values(groups);
  }, [cartItems]);

  const handleEmpty = async () => {
    const ok = await confirm({
      title: 'Empty your cart?',
      message: 'This removes all items from your cart. This action cannot be undone.',
      confirmText: 'Empty cart',
      cancelText: 'Keep items',
      danger: true,
    });
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

        {buildGroups.length > 0 && (
          <div className="cart-build-summary">
            <h2>Custom build bundles</h2>
            <div className="cart-build-summary-grid">
              {buildGroups.map((bundle) => (
                <div key={bundle.pc_build_id} className="cart-build-summary-card">
                  <div>
                    <div className="cart-build-label">Build ID {bundle.pc_build_id}</div>
                    <div className="cart-build-meta">
                      {bundle.componentCount} components · {bundle.quantity} units
                    </div>
                  </div>
                  <div className="cart-build-subtotal">PKR {bundle.subtotal.toLocaleString()}</div>
                </div>
              ))}
            </div>
            <p className="cart-build-summary-note">
              Custom builds are bundled and fulfilled by approved vendors. Review the cart items below before checkout.
            </p>
          </div>
        )}

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

