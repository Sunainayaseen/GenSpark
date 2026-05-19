import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { registerWithApi } from '../api/authApi';
import { getFlaskBase, getFlaskBaseFallback, normalizeVerificationUrl, setFlaskBaseUsed } from '../utils/flaskBase';
import { SITE_LOGO_SRC } from '../branding';
import './AuthModal.css';

const AuthModal = ({ isOpen, onClose, mode: initialMode = 'login', onFlaskLogin }) => {
  const { login, loginFromApi } = useAuth();
  const [mode, setMode] = useState(initialMode);
  const [registrationSuccess, setRegistrationSuccess] = useState(null);

  useEffect(() => {
    if (isOpen) {
      setMode(initialMode);
      setRegistrationSuccess(null);
    }
  }, [isOpen, initialMode]);
  const [role, setRole] = useState('buyer');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [flaskError, setFlaskError] = useState('');
  const [flaskLoading, setFlaskLoading] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
  });

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text).then(() => {
      const btn = document.querySelector(`[data-copy="${label}"]`);
      if (btn) {
        const orig = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(() => { btn.textContent = orig; }, 2000);
      }
    });
  };

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFlaskError('');
    if (mode === 'login') {
      setFlaskLoading(true);
      try {
        if (onFlaskLogin) {
          const result = await onFlaskLogin(formData.email, formData.password);
          if (!result?.email) {
            throw new Error('Login failed — no user returned from API.');
          }
          login(result);
        } else {
          await loginFromApi(formData.email, formData.password);
        }
        onClose();
      } catch (err) {
        setFlaskError(err.message || 'Login failed');
      } finally {
        setFlaskLoading(false);
      }
      return;
    }

    // Frontend registration – call Flask API to create user and send verification email
    setFlaskLoading(true);
    try {
      if (!formData.name || !formData.email) {
        throw new Error('Name and email are required.');
      }
      const data = await registerWithApi({
        name: formData.name,
        email: formData.email,
        role: role === 'vendor' ? 'vendor' : 'customer',
      });
      if (!data?.success) {
        throw new Error(data.error || data.message || 'Registration failed');
      }
      const otp = data.one_time_password;
      const rawVerificationUrl =
        typeof data.verification_url === 'string' ? data.verification_url : '';
      const verificationUrl = rawVerificationUrl
        ? normalizeVerificationUrl(rawVerificationUrl)
        : null;
      setRegistrationSuccess({ otp, verificationUrl });
      setFormData({
        name: '',
        email: '',
        password: '',
        confirmPassword: '',
      });
    } catch (err) {
      setFlaskError(err.message || 'Registration failed');
      return;
    } finally {
      setFlaskLoading(false);
    }
  };

  const handleInputChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  return (
    <div className="auth-modal-overlay" onClick={onClose}>
      <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close-btn" onClick={() => { setRegistrationSuccess(null); onClose(); }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          </svg>
        </button>

        {registrationSuccess ? (
          <div className="auth-success-view">
            <div className="auth-success-icon">
              <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
            </div>
            <h2 className="auth-success-title">Registration successful</h2>
            <p className="auth-success-desc">
              We have emailed you a verification link. Please verify your email before logging in.
            </p>
            {registrationSuccess.otp && (
              <div className="auth-success-block">
                <label>One-time password (save it for first login)</label>
                <div className="auth-success-copy-row">
                  <code className="auth-success-code">{registrationSuccess.otp}</code>
                  <button type="button" className="auth-success-copy-btn" data-copy="otp" onClick={() => copyToClipboard(registrationSuccess.otp, 'otp')}>
                    Copy
                  </button>
                </div>
              </div>
            )}
            {registrationSuccess.verificationUrl && (
              <div className="auth-success-block">
                <label>Verification link (for testing)</label>
                <div className="auth-success-copy-row">
                  <code
                    className="auth-success-code auth-success-link"
                    title={registrationSuccess.verificationUrl}
                  >
                    {registrationSuccess.verificationUrl}
                  </code>
                  <button type="button" className="auth-success-copy-btn" data-copy="link" onClick={() => copyToClipboard(registrationSuccess.verificationUrl, 'link')}>
                    Copy
                  </button>
                </div>
                <a
                  href={registrationSuccess.verificationUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="auth-success-open-link"
                  title={registrationSuccess.verificationUrl}
                >
                  Open verification link
                </a>
              </div>
            )}
            <button type="button" className="auth-submit-btn auth-success-continue" onClick={() => { setRegistrationSuccess(null); setMode('login'); }}>
              Continue to Login
            </button>
          </div>
        ) : (
          <div className="auth-modal-split">
            <div className="auth-modal-left">
              <div className="auth-modal-logo">
                <img
                  src={SITE_LOGO_SRC}
                  alt="Genspark Builds Logo"
                  className="auth-logo-image"
                />
              </div>
              <div className="modal-header">
                <h2>{mode === 'login' ? 'Welcome' : 'Create Account'}</h2>
                <p>
                  {mode === 'login'
                    ? 'Sign in to access your dashboard and continue managing your builds and orders.'
                    : 'Create your account to join as a buyer or vendor.'}
                </p>
              </div>

              <form className="auth-form" onSubmit={handleSubmit} aria-label={mode === 'login' ? 'Sign in' : 'Create account'} noValidate>
          {mode === 'signup' && (
            <div className="form-group">
              <label>Full Name</label>
              <input
                type="text"
                name="name"
                placeholder="Enter your name"
                value={formData.name}
                onChange={handleInputChange}
                required={mode === 'signup'}
              />
            </div>
          )}

          <div className="form-group">
            <label>Email</label>
            <div className="input-with-icon">
              <span className="input-icon" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
              </span>
              <input
                type="email"
                name="email"
                placeholder="Enter your email"
                value={formData.email}
                onChange={handleInputChange}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label>Password</label>
            <div className="password-input-wrap input-with-icon">
              <span className="input-icon" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              </span>
              <input
                type={showPassword ? 'text' : 'password'}
                name="password"
                placeholder="Enter your password"
                value={formData.password}
                onChange={handleInputChange}
                required
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword((p) => !p)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                tabIndex={-1}
              >
                {showPassword ? (
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                    <line x1="1" y1="1" x2="23" y2="23"/>
                  </svg>
                ) : (
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                    <circle cx="12" cy="12" r="3"/>
                  </svg>
                )}
              </button>
            </div>
          </div>

          {mode === 'signup' && (
            <div className="form-group">
              <label>Confirm Password</label>
              <div className="password-input-wrap">
                <input
                  type={showConfirmPassword ? 'text' : 'password'}
                  name="confirmPassword"
                  placeholder="Confirm your password"
                  value={formData.confirmPassword}
                  onChange={handleInputChange}
                  required={mode === 'signup'}
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowConfirmPassword((p) => !p)}
                  aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                  tabIndex={-1}
                >
                  {showConfirmPassword ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                      <line x1="1" y1="1" x2="23" y2="23"/>
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                      <circle cx="12" cy="12" r="3"/>
                    </svg>
                  )}
                </button>
              </div>
            </div>
          )}

          {mode === 'signup' && (
            <div className="form-group role-row">
              <label className="role-label">Role</label>
              <div className="role-select">
                <button
                  type="button"
                  className={`role-btn ${role === 'buyer' ? 'active' : ''}`}
                  onClick={() => setRole('buyer')}
                >
                  Buyer
                </button>
                <button
                  type="button"
                  className={`role-btn ${role === 'vendor' ? 'active' : ''}`}
                  onClick={() => setRole('vendor')}
                >
                  Vendor
                </button>
              </div>
            </div>
          )}

          {mode === 'login' && (
            <div className="form-options">
              <label className="remember-me" htmlFor="auth-remember">
                <input type="checkbox" id="auth-remember" name="remember" />
                <span>Remember me</span>
              </label>
              <a href="#forgot" className="forgot-password">Forgot Password?</a>
            </div>
          )}

          {flaskError && (
            <p className="auth-flask-error" role="alert">
              {flaskError}
            </p>
          )}
          <button
            type="submit"
            className="auth-submit-btn"
            disabled={flaskLoading}
            aria-busy={flaskLoading}
            aria-live="polite"
          >
            {flaskLoading && (
              <span className="auth-btn-spinner" aria-hidden="true" />
            )}
            <span className={flaskLoading ? 'auth-btn-text-loading' : ''}>
              {flaskLoading ? 'Signing in…' : mode === 'login' ? 'Sign in' : 'Create account'}
            </span>
          </button>

          {mode === 'login' && (
          <div className="social-login">
            <button
              type="button"
              className="social-btn social-btn-icon google"
              onClick={() => {
                const base = getFlaskBase() || getFlaskBaseFallback();
                if (base) setFlaskBaseUsed(base);
                window.location.href = getApiUrl('/auth/google');
              }}
              title="Continue with Google"
              aria-label="Continue with Google"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
            </button>
            <button
              type="button"
              className="social-btn social-btn-icon github"
              onClick={() => {
                const base = getFlaskBase() || getFlaskBaseFallback();
                if (base) setFlaskBaseUsed(base);
                window.location.href = getApiUrl('/auth/github');
              }}
              title="Continue with GitHub"
              aria-label="Continue with GitHub"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
            </button>
            <button
              type="button"
              className="social-btn social-btn-icon apple"
              title="Continue with Apple (coming soon)"
              aria-label="Continue with Apple (coming soon)"
              disabled
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M17.05 20.28c-.98.95-2.05.8-3.08.35-1.09-.46-2.09-.48-3.24 0-1.44.62-2.2.44-3.06-.35C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.49-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09l.01-.01zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z"/>
              </svg>
            </button>
            <button
              type="button"
              className="social-btn social-btn-icon microsoft"
              title="Continue with Microsoft (coming soon)"
              aria-label="Continue with Microsoft (coming soon)"
              disabled
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M2 2h9.5v9.5H2V2z" fill="#F25022"/>
                <path d="M12.5 2H22v9.5h-9.5V2z" fill="#7FBA00"/>
                <path d="M2 12.5h9.5V22H2v-9.5z" fill="#00A4EF"/>
                <path d="M12.5 12.5H22V22h-9.5v-9.5z" fill="#FFB900"/>
              </svg>
            </button>
          </div>
          )}

          <div className="auth-switch">
            {mode === 'login' ? (
              <>
                <p className="auth-switch-text">
                  If you don&apos;t have an account yet then please{' '}
                  <button type="button" onClick={() => setMode('signup')} className="auth-switch-link">
                    sign up
                  </button>.
                </p>
              </>
            ) : (
              <p className="auth-switch-text">
                Already have an account?{' '}
                <button type="button" onClick={() => setMode('login')} className="auth-switch-link">
                  Log in
                </button>
              </p>
            )}
          </div>
        </form>
            </div>

            <div className="auth-modal-panel">
              <h3 className="auth-panel-headline">AI-Powered PC Customization and Vendor Assembly Platform</h3>
              <blockquote className="auth-panel-quote">
                &ldquo;GenSpark has streamlined our vendor workflow and order management. Reliable, fast, and our team won&apos;t go back.&rdquo;
              </blockquote>
              <ul className="auth-panel-features" aria-hidden="true">
                <li>Manage inventory & components in one place</li>
                <li>Track orders and shipments end-to-end</li>
                <li>Secure payments and vendor payouts</li>
                <li>Admin & vendor dashboards with role-based access</li>
              </ul>
              <p className="auth-panel-badge">TRUSTED BY VENDORS & BUYERS</p>
              <div className="auth-panel-logos" aria-hidden="true">
                <span className="auth-panel-logo" title="Vendors">Vendors</span>
                <span className="auth-panel-logo" title="Predefined PCs">Prebuilt</span>
                <span className="auth-panel-logo" title="Components">Components</span>
                <span className="auth-panel-logo" title="Orders">Orders</span>
                <span className="auth-panel-logo" title="Payments">Payments</span>
                <span className="auth-panel-logo" title="Support">Support</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AuthModal;







