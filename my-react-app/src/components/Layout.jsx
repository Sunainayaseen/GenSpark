import { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { getFlaskApiLoginUrl, getFlaskBase, getFlaskBaseFallback, setFlaskBaseUsed } from '../utils/flaskBase';
import HeaderSearch from './HeaderSearch';
import AuthModal from './AuthModal';
import CartDropdown from './CartDropdown';
import AIChatbot from './AIChatbot';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';
import { SITE_LOGO_SRC } from '../branding';
import './Layout.css';

const Layout = ({ children }) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authMode, setAuthMode] = useState('login');
  const [isScrolled, setIsScrolled] = useState(false);
  const location = useLocation();
  const buildsNavActive = location.pathname === '/builds' || location.pathname.startsWith('/builds/');
  const { cartCount, isCartOpen, setIsCartOpen, toast } = useCart();
  const { user, logout, isLoggedIn, login } = useAuth();
  const navigate = useNavigate();
  const cartRef = useRef(null);
  const headerRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (cartRef.current && !cartRef.current.contains(event.target)) {
        setIsCartOpen(false);
      }
      // Close mobile menu when clicking outside
      if (isMenuOpen && !event.target.closest('.nav') && !event.target.closest('.menu-toggle')) {
        setIsMenuOpen(false);
      }
    };

    if (isCartOpen || isMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isCartOpen, setIsCartOpen, isMenuOpen]);

  useEffect(() => {
    const handleScroll = () => {
      const scrollPosition = window.scrollY;
      setIsScrolled(scrollPosition > 20);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    if (isMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isMenuOpen]);

  // Admin / Vendor dashboard: auto-open login modal taake user turant login karke dashboard dekhe
  useEffect(() => {
    if (location.pathname === '/admin' || location.pathname === '/vendor/dashboard') {
      setAuthMode('login');
      setAuthModalOpen(true);
    }
  }, [location.pathname]);

  // e.g. checkout: ?login=1 opens sign-in, then clean URL
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get('login') !== '1') return;
    setAuthMode('login');
    setAuthModalOpen(true);
    params.delete('login');
    const next = params.toString();
    navigate({ pathname: location.pathname, search: next ? `?${next}` : '' }, { replace: true });
  }, [location.search, location.pathname, navigate]);

  // After OAuth redirect: ?oauth=google or ?oauth=github – fetch /api/me and sync auth, then clean URL
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const oauth = params.get('oauth');
    const authError = params.get('auth_error');
    if (authError) {
      navigate(location.pathname, { replace: true });
      return;
    }
    if (oauth !== 'google' && oauth !== 'github') return;
    const base = getFlaskBase() || getFlaskBaseFallback();
    if (!base) return;
    fetch(`${base}/api/me`, { credentials: 'include' })
      .then((res) => res.json())
      .then((data) => {
        if (data.success && data.user) {
          login(data.user);
        }
      })
      .finally(() => {
        navigate(location.pathname, { replace: true });
      });
  }, [location.search, location.pathname, navigate, login]);

  return (
    <div className="app">
      <a
        href="#main-content"
        className="skip-to-main"
        onClick={(e) => {
          e.preventDefault();
          const el = document.getElementById('main-content');
          if (el) {
            el.focus({ preventScroll: true });
            el.scrollIntoView({ behavior: 'auto', block: 'start' });
          }
        }}
      >
        Skip to main content
      </a>
      {toast ? (
        <div className={`cart-global-toast ${toast.type}`} role="status" aria-live="polite">
          {toast.message}
        </div>
      ) : null}
      <header ref={headerRef} className={`header ${isScrolled ? 'scrolled' : ''}`}>
        <div className="container">
          <div className="header-content">
            <Link to="/" className="logo">
              <img
                src={SITE_LOGO_SRC}
                alt="Genspark Builds Logo"
                className="logo-image"
                decoding="async"
                fetchPriority="high"
              />
            </Link>

            <nav
              id="site-navigation"
              className={`nav ${isMenuOpen ? 'nav-open' : ''}`}
              aria-label="Main navigation"
            >
              {isMenuOpen && (
                <button
                  type="button"
                  className="nav-close-btn"
                  onClick={() => setIsMenuOpen(false)}
                  aria-label="Close menu"
                >
                  ✕
                </button>
              )}
              <Link
                to="/"
                className={location.pathname === '/' ? 'active' : ''}
                onClick={() => setIsMenuOpen(false)}
              >
                Home
              </Link>
              <Link
                to="/builds"
                className={buildsNavActive ? 'active' : ''}
                onClick={() => setIsMenuOpen(false)}
              >
                Prebuilt PC
              </Link>
              <Link
                to="/components"
                className={location.pathname === '/components' ? 'active' : ''}
                onClick={() => setIsMenuOpen(false)}
              >
                Components
              </Link>
              <Link
                to="/chatbot"
                className={location.pathname === '/chatbot' ? 'active' : ''}
                onClick={() => setIsMenuOpen(false)}
              >
                AI Assistant
              </Link>
              <Link
                to="/about"
                className={location.pathname === '/about' ? 'active' : ''}
                onClick={() => setIsMenuOpen(false)}
              >
                About
              </Link>
              {isMenuOpen && (
                <div className="header-actions">
                  <HeaderSearch onAfterNavigate={() => setIsMenuOpen(false)} />
                  <div className="header-cart-auth">
                    <div className="cart-container" ref={cartRef}>
                      <button
                        className="cart-icon-btn"
                        onClick={() => setIsCartOpen(!isCartOpen)}
                        aria-label="Shopping Cart"
                      >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="9" cy="21" r="1"/>
                          <circle cx="20" cy="21" r="1"/>
                          <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
                        </svg>
                        {cartCount > 0 && (
                          <span className="cart-badge">{cartCount}</span>
                        )}
                      </button>
                      {isCartOpen && <CartDropdown />}
                    </div>
                    <div className="auth-buttons">
                      {isLoggedIn ? (
                        <>
                          <span className="nav-user-name">{user?.name || user?.email}</span>
                          <button type="button" className="btn btn-secondary" onClick={() => { logout(); setIsMenuOpen(false); }}>Logout</button>
                        </>
                      ) : (
                        <>
                          <button
                            className="btn btn-secondary"
                            onClick={() => {
                              setAuthMode('login');
                              setAuthModalOpen(true);
                              setIsMenuOpen(false);
                            }}
                          >
                            Login
                          </button>
                          <button
                            className="btn btn-primary"
                            onClick={() => {
                              setAuthMode('signup');
                              setAuthModalOpen(true);
                              setIsMenuOpen(false);
                            }}
                          >
                            Sign Up
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </nav>

            {!isMenuOpen && (
              <div className="header-end">
                <HeaderSearch onAfterNavigate={() => setIsMenuOpen(false)} />
                <div className="header-cart-auth">
                  <div className="cart-container" ref={cartRef}>
                    <button
                      className="cart-icon-btn"
                      onClick={() => setIsCartOpen(!isCartOpen)}
                      aria-label="Shopping Cart"
                    >
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="9" cy="21" r="1"/>
                        <circle cx="20" cy="21" r="1"/>
                        <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
                      </svg>
                      {cartCount > 0 && (
                        <span className="cart-badge">{cartCount}</span>
                      )}
                    </button>
                    {isCartOpen && <CartDropdown />}
                  </div>
                  <div className="auth-buttons">
                    {isLoggedIn ? (
                      <>
                        <span className="nav-user-name">{user?.name || user?.email}</span>
                        <button type="button" className="btn btn-secondary" onClick={logout}>Logout</button>
                      </>
                    ) : (
                      <>
                        <button
                          className="btn btn-secondary"
                          onClick={() => {
                            setAuthMode('login');
                            setAuthModalOpen(true);
                          }}
                        >
                          Login
                        </button>
                        <button
                          className="btn btn-primary"
                          onClick={() => {
                            setAuthMode('signup');
                            setAuthModalOpen(true);
                          }}
                        >
                          Sign Up
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            )}

            <button
              type="button"
              className="menu-toggle"
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              aria-expanded={isMenuOpen}
              aria-controls="site-navigation"
              aria-label={isMenuOpen ? 'Close menu' : 'Open menu'}
            >
              {isMenuOpen ? '✕' : '☰'}
            </button>
          </div>
        </div>
      </header>

      <main id="main-content" className="main-content" tabIndex={-1}>
        {children}
      </main>

      <AuthModal 
        isOpen={authModalOpen} 
        onClose={() => setAuthModalOpen(false)}
        mode={authMode}
        onFlaskLogin={async (email, password) => {
          const body = JSON.stringify({ email, password });
          const opts = {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body,
            credentials: 'include',
          };
          let flaskUrl = getFlaskApiLoginUrl();
          let res;
          try {
            res = await fetch(flaskUrl, opts);
          } catch (firstErr) {
            const fallbackBase = getFlaskBaseFallback();
            const altUrl = fallbackBase && fallbackBase !== getFlaskBase() ? `${fallbackBase}/api/login` : null;
            if (altUrl) {
              try {
                res = await fetch(altUrl, opts);
                flaskUrl = altUrl;
                setFlaskBaseUsed(fallbackBase);
              } catch (secondErr) {
                throw new Error(
                  'Flask reach nahi ho raha. "vendor dashboard" me python run.py chalao (port 5000).'
                );
              }
            } else {
              throw new Error(
                'Flask reach nahi ho raha. "vendor dashboard" me python run.py chalao (port 5000).'
              );
            }
          }
          const data = await res.json().catch(() => ({}));
          if (!res.ok) {
            const err = data.error || data.message || 'Login failed';
            if (res.status === 401 || (err && (err.includes('Invalid') || err === 'Login failed'))) {
              const isVendor = location.pathname === '/vendor/dashboard';
              throw new Error(
                isVendor
                  ? 'Invalid credentials or vendor account not configured. Please verify your login details or initialize demo data and try again.'
                  : 'Invalid email or password. Please verify your credentials and try again.'
              );
            }
            throw new Error(err);
          }
          if (location.pathname === '/vendor/dashboard') {
            window.dispatchEvent(new CustomEvent('flask-vendor-login-success'));
          } else if (location.pathname === '/admin') {
            window.dispatchEvent(new CustomEvent('flask-admin-login-success'));
          }
          return data.user || null;
        }}
      />

      <AIChatbot />

      <footer className="footer">
        <div className="container">
          <div className="footer-content">
            <div className="footer-section footer-about">
              <h4>GenSpark Builds</h4>
              <p>AI-powered PC customization platform for Pakistan. Build your perfect gaming rig with expert compatibility checks and local vendor network.</p>
              <div className="footer-logo-placeholder">
                <img
                  src={SITE_LOGO_SRC}
                  alt="Genspark Builds Logo"
                  className="footer-logo-image"
                  loading="lazy"
                  decoding="async"
                />
                <div className="footer-tagline">BUILD YOUR GAMING RIG</div>
              </div>
            </div>
            <div className="footer-section">
              <h4>Quick Links</h4>
              <Link to="/">Home</Link>
              <Link to="/chatbot">Start Build</Link>
              <Link to="/builds">Prebuilt PC</Link>
              <Link to="/configurator">Configurator</Link>
              <Link to="/about">About Us</Link>
              <Link to="/contact">Contact Us</Link>
            </div>
            <div className="footer-section footer-contact">
              <h4>Contact Us</h4>
              <div className="contact-info">
                <a href="tel:+923201436593" className="contact-item">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
                  </svg>
                  <span>+92 320 1436593</span>
                </a>
                <a href="mailto:info@gensparkbuilds.com" className="contact-item">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                    <polyline points="22,6 12,13 2,6"/>
                  </svg>
                  <span>info@gensparkbuilds.com</span>
                </a>
                <div className="contact-item">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                    <circle cx="12" cy="10" r="3"/>
                  </svg>
                  <span>Lahore, Karachi, Islamabad</span>
                </div>
                <a href="https://wa.me/923201436593" target="_blank" rel="noopener noreferrer" className="contact-item">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
                  </svg>
                  <span>WhatsApp: +92 320 1436593</span>
                </a>
              </div>
            </div>
            <div className="footer-section footer-social-section">
              <h4>Follow Us</h4>
              <div className="social-links">
                <a href="https://wa.me/923201436593" target="_blank" rel="noopener noreferrer" className="social-link" aria-label="WhatsApp">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
                  </svg>
                </a>
                <a href="https://facebook.com" target="_blank" rel="noopener noreferrer" className="social-link" aria-label="Facebook">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                  </svg>
                </a>
                <a href="https://twitter.com" target="_blank" rel="noopener noreferrer" className="social-link" aria-label="Twitter">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M23.953 4.57a10 10 0 01-2.825.775 4.958 4.958 0 002.163-2.723c-.951.555-2.005.959-3.127 1.184a4.92 4.92 0 00-8.384 4.482C7.69 8.095 4.067 6.13 1.64 3.162a4.822 4.822 0 00-.666 2.475c0 1.71.87 3.213 2.188 4.096a4.904 4.904 0 01-2.228-.616v.06a4.923 4.923 0 003.946 4.827 4.996 4.996 0 01-2.212.085 4.936 4.936 0 004.604 3.417 9.867 9.867 0 01-6.102 2.105c-.39 0-.779-.023-1.17-.067a13.995 13.995 0 007.557 2.209c9.053 0 13.998-7.496 13.998-13.985 0-.21 0-.42-.015-.63A9.935 9.935 0 0024 4.59z"/>
                  </svg>
                </a>
                <a href="https://instagram.com" target="_blank" rel="noopener noreferrer" className="social-link" aria-label="Instagram">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                  </svg>
                </a>
                <a href="https://linkedin.com" target="_blank" rel="noopener noreferrer" className="social-link" aria-label="LinkedIn">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                  </svg>
                </a>
                <a href="https://youtube.com" target="_blank" rel="noopener noreferrer" className="social-link" aria-label="YouTube">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                  </svg>
                </a>
                <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="social-link" aria-label="GitHub">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                  </svg>
                </a>
              </div>
            </div>
          </div>
          <div className="footer-bottom">
            <p>&copy; 2024 GenSpark Builds. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Layout;

