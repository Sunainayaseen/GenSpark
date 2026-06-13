import { Link, useLocation, useNavigate } from 'react-router-dom';
import './OrderPlacedSuccess.css';

const OrderPlacedSuccess = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state || {};
  const orderId = state.orderId;
  const orderNumber = state.orderNumber;

  return (
    <div className="order-placed-page">
      <div className="container order-placed-container">
        <div className="order-placed-card" role="status" aria-live="polite">
          <div className="order-placed-icon-wrap" aria-hidden="true">
            <svg className="order-placed-check" viewBox="0 0 52 52" focusable="false">
              <circle className="order-placed-check__circle" cx="26" cy="26" r="25" fill="none" />
              <path className="order-placed-check__mark" fill="none" d="M14 27l8 8 16-18" />
            </svg>
          </div>

          <h1 className="order-placed-title">Order Placed Successfully!</h1>
          <p className="order-placed-message">
            Thank you for your purchase. Your order is now pending admin and vendor approval.
          </p>

          {(orderNumber || orderId) && (
            <p className="order-placed-ref">
              Reference:{' '}
              <strong>{orderNumber || `#${orderId}`}</strong>
            </p>
          )}

          <div className="order-placed-actions">
            <button
              type="button"
              className="btn btn-primary btn-lg"
              onClick={() => navigate('/my-orders')}
            >
              View My Orders
            </button>
            {orderId ? (
              <Link to={`/order/${orderId}`} className="btn btn-secondary btn-lg">
                Track this order
              </Link>
            ) : null}
            <Link to="/builds" className="order-placed-link">
              Continue browsing builds
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OrderPlacedSuccess;
