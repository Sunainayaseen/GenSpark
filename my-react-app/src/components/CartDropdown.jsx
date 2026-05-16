import { useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { useBlockingOrder } from '../hooks/useBlockingOrder';
import './CartDropdown.css';

const CartDropdown = () => {
  const { cartItems, removeFromCart, updateQuantity, cartTotal, setIsCartOpen } = useCart();
  const { blockingOrder } = useBlockingOrder();
  const navigate = useNavigate();
  const checkoutBlocked = Boolean(blockingOrder);

  const handleCheckout = () => {
    if (blockingOrder) return;
    setIsCartOpen(false);
    navigate('/checkout');
  };

  const handleViewCart = () => {
    setIsCartOpen(false);
    navigate('/cart');
  };

  return (
    <div className="cart-dropdown">
      <div className="cart-header">
        <h3>Shopping Cart</h3>
        <button className="cart-close-btn" onClick={() => setIsCartOpen(false)}>
          ✕
        </button>
      </div>

      <div className="cart-items">
        {cartItems.length === 0 ? (
          <div className="cart-empty">
            <div className="empty-icon" aria-hidden="true">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="empty-cart-icon"
              >
                <circle cx="8" cy="21" r="1" />
                <circle cx="19" cy="21" r="1" />
                <path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12" />
              </svg>
            </div>
            <p>Your cart is empty</p>
            <button className="btn btn-primary" onClick={() => setIsCartOpen(false)}>
              Start Shopping
            </button>
          </div>
        ) : (
          <>
            {cartItems.map((item) => (
              <div key={item.id} className="cart-item">
                <div className="cart-item-info">
                  <h4>{item.title || item.name}</h4>
                  <p className="cart-item-price">PKR {(item.price || 0).toLocaleString()}</p>
                </div>
                <div className="cart-item-controls">
                  <button
                    className="quantity-btn"
                    onClick={() => updateQuantity(item.id, item.quantity - 1)}
                  >
                    −
                  </button>
                  <span className="quantity">{item.quantity}</span>
                  <button
                    className="quantity-btn"
                    onClick={() => updateQuantity(item.id, item.quantity + 1)}
                  >
                    +
                  </button>
                  <button
                    className="remove-btn"
                    onClick={() => removeFromCart(item.id)}
                    title="Remove"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            ))}
          </>
        )}
      </div>

      {cartItems.length > 0 && (
        <div className="cart-footer">
          <div className="cart-total">
            <span>Total:</span>
            <span className="total-amount">PKR {cartTotal.toLocaleString()}</span>
          </div>
          <div className="cart-footer-actions">
            {blockingOrder ? (
              <p className="cart-dropdown-blocked-hint" role="status">
                Complete or wait for admin on your pending order first.
              </p>
            ) : null}
            <button className="btn btn-secondary btn-lg" onClick={handleViewCart}>
              View Cart
            </button>
            <button
              className="btn btn-primary btn-lg checkout-btn"
              onClick={handleCheckout}
              disabled={checkoutBlocked}
              title={checkoutBlocked ? 'You have an order awaiting admin approval' : undefined}
            >
              Proceed to Checkout
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default CartDropdown;

