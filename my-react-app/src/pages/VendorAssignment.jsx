import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { useCart } from '../context/CartContext';
import './VendorAssignment.css';
import { resolveBuildParts } from '../utils/buildResolver';

// GenSpark has no warehouse — a PC build must be fulfilled entirely by ONE
// vendor (assembly is done by the supplying vendor). This page therefore only
// ever offers vendors that have every resolved part of `selectedBuild` in
// stock; it never lets a build get split across vendors.
const VendorAssignment = () => {
  const navigate = useNavigate();
  const { selectedBuild } = useApp();
  const { addBuildToCart, getBuildVendorOptions, cartItems } = useCart();

  const [selectedVendor, setSelectedVendor] = useState(null);
  const [eligibleVendors, setEligibleVendors] = useState([]);
  const [resolvedComponents, setResolvedComponents] = useState([]);
  const [unavailable, setUnavailable] = useState(false);
  const [vendorsLoading, setVendorsLoading] = useState(false);
  const [vendorsError, setVendorsError] = useState(null);
  const [placing, setPlacing] = useState(false);
  const [confirmError, setConfirmError] = useState('');

  const loadEligibleVendors = async () => {
    const parts = selectedBuild?.parts;
    if (!Array.isArray(parts) || parts.length === 0) {
      setEligibleVendors([]);
      setResolvedComponents([]);
      setUnavailable(false);
      return;
    }

    setVendorsLoading(true);
    setVendorsError(null);
    setUnavailable(false);
    setSelectedVendor(null);
    try {
      const { slots } = await resolveBuildParts(parts);
      const resolved = slots.filter((s) => s.status === 'resolved' && s.component?.id);
      const components = resolved.map((s) => ({ component_id: s.component.id, quantity: 1 }));
      setResolvedComponents(components);

      if (!components.length) {
        setEligibleVendors([]);
        setUnavailable(true);
        return;
      }

      const result = await getBuildVendorOptions(components);
      if (!result.ok) {
        setVendorsError(result.error || 'Failed to check vendor availability');
        setEligibleVendors([]);
        return;
      }
      setEligibleVendors(result.vendors);
      setUnavailable(!result.coversAll || result.vendors.length === 0);
    } catch (err) {
      console.error('Failed to resolve build / load vendors', err);
      setVendorsError(err.message || 'Failed to load vendors');
    } finally {
      setVendorsLoading(false);
    }
  };

  useEffect(() => {
    loadEligibleVendors();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedBuild]);

  useEffect(() => {
    // Keep CTA usable: default to the cheapest eligible vendor (list is
    // already sorted cheapest-first by the backend).
    if (!selectedVendor && eligibleVendors.length > 0) {
      setSelectedVendor(eligibleVendors[0]);
    }
  }, [eligibleVendors, selectedVendor]);

  const handleConfirmOrder = async () => {
    setConfirmError('');

    // No build in context (e.g. cart was already populated elsewhere) — just
    // forward to checkout with whatever's already in the cart.
    if (!resolvedComponents.length) {
      if (Array.isArray(cartItems) && cartItems.length > 0) {
        navigate('/checkout', { replace: true });
      } else {
        setConfirmError('Your cart is empty. Pick a build first.');
      }
      return;
    }

    const vendor = selectedVendor || (eligibleVendors.length > 0 ? eligibleVendors[0] : null);
    if (!vendor) {
      setConfirmError('Please select a vendor.');
      return;
    }

    setPlacing(true);
    try {
      const result = await addBuildToCart(resolvedComponents, vendor.id);
      if (result.ok) {
        navigate('/checkout', { replace: true });
      } else {
        setConfirmError(
          result.code === 'VENDOR_CONFLICT'
            ? 'This vendor no longer has every part in stock. Please pick another vendor.'
            : result.error || 'Unable to continue to payment right now. Please try again.'
        );
        // Stock may have just changed under us — refresh the eligible list.
        loadEligibleVendors();
      }
    } catch (_) {
      setConfirmError('Unable to continue to payment right now. Please try again.');
    } finally {
      setPlacing(false);
    }
  };

  const selectedVendorTotal = selectedVendor?.total_price;
  const totalPrice =
    typeof selectedVendorTotal === 'number' && selectedVendorTotal > 0
      ? selectedVendorTotal
      : selectedBuild?.parts?.reduce((sum, part) => sum + (part.price || 0), 0) || selectedBuild?.price || 0;
  const assemblyFee = selectedBuild?.parts?.length ? 5000 : 0;
  const shipping = selectedBuild?.parts?.length ? 2000 : 0;
  const finalTotal = totalPrice + assemblyFee + shipping;

  const hasBuild = Array.isArray(selectedBuild?.parts) && selectedBuild.parts.length > 0;

  return (
    <div className="vendor-assignment-page">
      <div className="container">
        <div className="page-header vendor-page-header">
          <h1>Finish your order</h1>
        </div>

        <div className="assignment-grid">
          <div className="vendors-panel">
            <h2 className="vendors-panel-title">Choose a vendor</h2>
            <p className="vendors-panel-sub">
              {hasBuild
                ? 'Vendors with 100% of this build’s parts in stock · cheapest first'
                : 'No build selected — continue with your current cart.'}
            </p>

            <div className="vendors-list-wrap">
              {vendorsLoading && (
                <div className="info-message">Checking vendor stock...</div>
              )}
              {vendorsError && !vendorsLoading && (
                <div className="error-message">{vendorsError}</div>
              )}
              {!vendorsLoading && !vendorsError && hasBuild && unavailable && (
                <div className="error-message">
                  This build is currently unavailable because no vendor has all required components in stock.
                </div>
              )}
              {!vendorsLoading && !vendorsError && !hasBuild && (
                <div className="info-message">No build selected — your existing cart will be used.</div>
              )}
              {!vendorsLoading && !vendorsError && hasBuild && !unavailable && eligibleVendors.length > 0 && (
                <div className="vendors-table" role="group">
                  <div className="vendors-list-head" id="vendors-list-head">
                    <span className="vendors-col-radio" aria-hidden="true" />
                    <span className="vendors-col-vendor">Vendor</span>
                    <span className="vendors-col-meta">City &amp; price</span>
                  </div>
                  <div
                    className="vendors-list-scroll"
                    role="listbox"
                    aria-labelledby="vendors-list-head"
                  >
                  {eligibleVendors.map((vendor) => {
                    const label = vendor.shop_name || 'Vendor';
                    const initial = String(label).trim().charAt(0).toUpperCase() || 'V';
                    const selected = selectedVendor?.id === vendor.id;
                    return (
                      <div
                        key={vendor.id}
                        role="option"
                        aria-selected={selected}
                        tabIndex={0}
                        className={`vendor-row ${selected ? 'vendor-row--selected' : ''}`}
                        onClick={() => setSelectedVendor(vendor)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            setSelectedVendor(vendor);
                          }
                        }}
                      >
                        <span className="vendor-radio" aria-hidden="true">
                          {selected && (
                            <svg viewBox="0 0 16 16" width="10" height="10">
                              <path
                                fill="currentColor"
                                d="M6.2 11.2 3 8l-1.2 1.2 4.4 4.4L14.6 5.2 13.4 4z"
                              />
                            </svg>
                          )}
                        </span>
                        <div className="vendor-row-main">
                          <span className="vendor-avatar" aria-hidden>
                            {initial}
                          </span>
                          <div className="vendor-row-text">
                            <span className="vendor-name">{label}</span>
                            <span className="vendor-badge">All parts in stock</span>
                            {vendor.avg_rating ? (
                              <span className="vendor-rating">
                                ★ {vendor.avg_rating.toFixed(1)}
                                <span className="vendor-rating-count"> ({vendor.rating_count})</span>
                              </span>
                            ) : null}
                          </div>
                        </div>
                        <div className="vendor-row-meta">
                          <span>{vendor.city || '—'}</span>
                          <span className="vendor-row-phone">
                            PKR {Number(vendor.total_price || 0).toLocaleString('en-US')}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="payment-panel">
            <h2 className="payment-panel-title">Order summary</h2>
            <div className="order-summary">
              <div className="summary-item">
                <span>Build total</span>
                <span>PKR {totalPrice.toLocaleString('en-US')}</span>
              </div>
              {assemblyFee > 0 && (
                <div className="summary-item">
                  <span>Assembly fee</span>
                  <span>PKR {assemblyFee.toLocaleString('en-US')}</span>
                </div>
              )}
              {shipping > 0 && (
                <div className="summary-item">
                  <span>Shipping</span>
                  <span>PKR {shipping.toLocaleString('en-US')}</span>
                </div>
              )}
              <div className="summary-item total">
                <span>Total</span>
                <span>PKR {finalTotal.toLocaleString('en-US')}</span>
              </div>
            </div>

            <p className="payment-method-hint" style={{ marginBottom: 12 }}>
              You’ll pick a payment method (cash on delivery or card) on the next step.
            </p>

            <button
              type="button"
              className="btn btn-primary btn-lg vendor-place-order-btn"
              onClick={handleConfirmOrder}
              disabled={
                placing ||
                vendorsLoading ||
                (hasBuild && (unavailable || eligibleVendors.length === 0)) ||
                (!hasBuild && (!Array.isArray(cartItems) || cartItems.length === 0))
              }
            >
              {placing ? 'Continuing…' : 'Continue to checkout'}
            </button>
            {confirmError ? (
              <p className="error-message" role="alert" style={{ marginTop: 10 }}>
                {confirmError}
              </p>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
};

export default VendorAssignment;
