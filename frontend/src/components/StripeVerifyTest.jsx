import { useState } from 'react';
import { getApiPrefix } from '../utils/flaskBase';
import './StripeVerifyTest.css';

function publishableKeyHint() {
  const key = (import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY || '').trim();
  if (key.startsWith('pk_')) {
    return `${key.slice(0, 12)}…${key.slice(-4)}`;
  }
  return 'not set — add VITE_STRIPE_PUBLISHABLE_KEY=pk_test_... to frontend/.env.local, save (Ctrl+S), then restart npm run dev';
}

export default function StripeVerifyTest() {
  const publishableHint = publishableKeyHint();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState(false);

  const runVerify = async () => {
    setLoading(true);
    setMessage('');
    setError(false);
    try {
      const res = await fetch(`${getApiPrefix()}/verify-stripe`, { credentials: 'include' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(true);
        setMessage(data.error || data.message || `Request failed (${res.status})`);
        return;
      }
      const text = data.message || 'Stripe connected successfully!';
      setMessage(
        `${text} Backend secret key is valid. ` +
          (publishableHint.includes('not set')
            ? 'Save VITE_STRIPE_PUBLISHABLE_KEY in .env.local and restart Vite for checkout card UI.'
            : 'Frontend publishable key is loaded.'),
      );
    } catch (err) {
      setError(true);
      setMessage(err?.message || 'Could not reach the backend. Is Flask running on port 5000?');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="stripe-verify-page container">
      <h1>Stripe connection test</h1>
      <p className="stripe-verify-muted">
        Keys stay on your machine only (<code>backend/.env</code> + <code>frontend/.env.local</code>).
        Never paste secret keys in chat.
      </p>

      <div className="stripe-verify-card">
        <p>
          <strong>Frontend publishable key:</strong> {publishableHint}
        </p>
        <p>
          <strong>Backend probe:</strong> <code>GET /api/verify-stripe</code>
        </p>
        <button type="button" className="btn btn-primary" onClick={runVerify} disabled={loading}>
          {loading ? 'Verifying…' : 'Verify Stripe connection'}
        </button>
        {message ? (
          <p className={`stripe-verify-result ${error ? 'is-error' : 'is-ok'}`} role="status">
            {message}
          </p>
        ) : null}
      </div>
    </div>
  );
}
