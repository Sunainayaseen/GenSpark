import { useMemo, useState } from 'react';
import { CardElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { createPaymentIntent, completeStripeCheckout } from '../api/paymentApi';
import './CheckoutForm.css';

const CARD_ELEMENT_OPTIONS = {
  hidePostalCode: true,
  // Turn off the Stripe "Link" fast-checkout prompt (the email-OTP popup).
  // Users just enter their card directly — no extra modal.
  disableLink: true,
  style: {
    base: {
      fontSize: '16px',
      color: '#1e293b',
      fontFamily: 'inherit',
      lineHeight: '1.5',
      '::placeholder': { color: '#94a3b8' },
    },
    invalid: {
      color: '#dc2626',
      iconColor: '#dc2626',
    },
  },
};

function friendlyPaymentError(message) {
  if (!message) return 'Payment could not be completed. Please try again.';
  const m = message.toLowerCase();
  if (m.includes('declined')) {
    return 'Your card was declined. Try a different card or contact your bank.';
  }
  if (m.includes('insufficient')) {
    return 'Insufficient funds on this card. Try another payment method.';
  }
  if (m.includes('expired')) {
    return 'This card has expired. Use a valid expiry date.';
  }
  if (m.includes('cvc') || m.includes('security code')) {
    return 'Check the CVC (3-digit code on the back of your card).';
  }
  if (m.includes('number') && m.includes('invalid')) {
    return 'Card number looks invalid. Double-check and try again.';
  }
  return message;
}

const STEPS = [
  { id: 'validate', label: 'Checking details' },
  { id: 'intent', label: 'Connecting to Stripe' },
  { id: 'card', label: 'Confirming card' },
  { id: 'order', label: 'Saving your order' },
];

export default function CheckoutForm({
  amount,
  userId,
  cartItems,
  shippingAddress,
  shippingFee = 0,
  onValidate,
  onSuccess,
  currencyLabel = 'PKR',
  disabled = false,
}) {
  const stripe = useStripe();
  const elements = useElements();
  const [loading, setLoading] = useState(false);
  const [activeStep, setActiveStep] = useState(null);
  const [status, setStatus] = useState({ type: '', message: '' });
  const [showTestHelp, setShowTestHelp] = useState(false);

  const isDev = import.meta.env.DEV;
  const formattedAmount = useMemo(
    () => `${currencyLabel} ${Number(amount).toLocaleString('en-US')}`,
    [amount, currencyLabel],
  );

  const stripeReady = Boolean(stripe && elements);

  const handlePaymentSubmit = async (e) => {
    e.preventDefault();
    if (loading || !stripe || !elements || disabled) return;

    setStatus({ type: '', message: '' });

    if (onValidate && !onValidate()) {
      setStatus({
        type: 'error',
        message: 'Please fill in your shipping address above before paying.',
      });
      return;
    }

    const card = elements.getElement(CardElement);
    if (!card) {
      setStatus({ type: 'error', message: 'Card field is not ready. Refresh the page and try again.' });
      return;
    }

    setLoading(true);
    setActiveStep('validate');

    try {
      setActiveStep('intent');
      const intentRes = await createPaymentIntent({
        items: cartItems,
        shippingAddress,
        shippingFee,
      });
      const clientSecret = intentRes.clientSecret;

      if (!clientSecret) {
        setStatus({ type: 'error', message: 'Could not start payment. Check that the backend is running.' });
        return;
      }

      setActiveStep('card');
      const stripeResult = await stripe.confirmCardPayment(clientSecret, {
        payment_method: { card },
      });

      if (stripeResult.error) {
        setStatus({ type: 'error', message: friendlyPaymentError(stripeResult.error.message) });
        return;
      }

      if (stripeResult.paymentIntent?.status === 'succeeded') {
        setActiveStep('order');
        const dbRes = await completeStripeCheckout({
          user_id: userId,
          items: cartItems,
          total_amount: amount,
          payment_intent_id: stripeResult.paymentIntent.id,
          shipping_address: shippingAddress,
          shipping_fee: shippingFee,
        });

        if (dbRes.success) {
          setStatus({
            type: 'success',
            message: `Payment successful! Order #${dbRes.order_id} is recorded.`,
          });
          onSuccess?.(dbRes);
        } else {
          setStatus({
            type: 'error',
            message:
              dbRes.message ||
              'Payment went through but we could not save the order. Contact support with your payment receipt.',
          });
        }
      } else {
        setStatus({ type: 'error', message: 'Payment was not completed. Please try again.' });
      }
    } catch (err) {
      const raw =
        err?.response?.data?.error ||
        err?.response?.data?.message ||
        err?.message ||
        'Network error. Is the backend running on port 5000?';
      setStatus({ type: 'error', message: friendlyPaymentError(String(raw)) });
    } finally {
      setLoading(false);
      setActiveStep(null);
    }
  };

  return (
    <div className="stripe-checkout-form">
      <div className="stripe-form-header">
        <div className="stripe-form-title-row">
          <span className="stripe-lock-icon" aria-hidden="true">
            🔒
          </span>
          <div>
            <h4>Pay with card</h4>
            <p className="stripe-form-subtitle">Powered by Stripe — your card details never touch our servers.</p>
          </div>
        </div>
        <ul className="stripe-accepted" aria-label="Accepted payment methods">
          <li>Visa</li>
          <li>Mastercard</li>
          <li>Amex</li>
        </ul>
      </div>

      <label className="stripe-field-label" htmlFor="stripe-card-field">
        Card number, expiry &amp; CVC
      </label>
      <div id="stripe-card-field" className="stripe-card-wrap">
        <CardElement options={CARD_ELEMENT_OPTIONS} />
      </div>
      <p className="stripe-field-hint">Enter the name on your card in Stripe if prompted. Use the billing address you entered above.</p>

      {loading && activeStep ? (
        <ol className="stripe-progress" aria-live="polite">
          {STEPS.map((step, index) => {
            const stepIndex = STEPS.findIndex((s) => s.id === activeStep);
            const state =
              index < stepIndex ? 'done' : index === stepIndex ? 'current' : 'pending';
            return (
              <li key={step.id} className={`stripe-progress-step is-${state}`}>
                <span className="stripe-progress-dot" aria-hidden="true" />
                {step.label}
              </li>
            );
          })}
        </ol>
      ) : null}

      <button
        type="button"
        onClick={handlePaymentSubmit}
        className="btn btn-primary btn-lg stripe-pay-btn"
        disabled={!stripeReady || loading || disabled}
        aria-busy={loading}
      >
        {loading ? 'Processing payment…' : `Pay ${formattedAmount}`}
      </button>

      {!stripeReady ? (
        <p className="stripe-loading-hint" role="status">
          Loading secure payment form…
        </p>
      ) : null}

      {status.message ? (
        <div
          className={`stripe-alert stripe-alert--${status.type || 'info'}`}
          role={status.type === 'error' ? 'alert' : 'status'}
        >
          {status.message}
        </div>
      ) : null}

      <details className="stripe-after-pay">
        <summary>What happens when you pay?</summary>
        <ol>
          <li>Stripe verifies your card and charges {formattedAmount}.</li>
          <li>We save your order and reduce stock in the database.</li>
          <li>Admin reviews the order; vendors ship after approval.</li>
          <li>You can track the order from your account.</li>
        </ol>
      </details>

      {isDev ? (
        <div className="stripe-test-panel">
          <button
            type="button"
            className="stripe-test-toggle"
            onClick={() => setShowTestHelp((v) => !v)}
            aria-expanded={showTestHelp}
          >
            {showTestHelp ? 'Hide' : 'Show'} test card (development only)
          </button>
          {showTestHelp ? (
            <div className="stripe-test-body">
              <p>
                <strong>Test mode:</strong> use Stripe&apos;s fake card — no real money is charged.
              </p>
              <dl>
                <div>
                  <dt>Card number</dt>
                  <dd>
                    <code>4242 4242 4242 4242</code>
                  </dd>
                </div>
                <div>
                  <dt>Expiry</dt>
                  <dd>Any future date (e.g. 12/34)</dd>
                </div>
                <div>
                  <dt>CVC</dt>
                  <dd>Any 3 digits (e.g. 123)</dd>
                </div>
              </dl>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
