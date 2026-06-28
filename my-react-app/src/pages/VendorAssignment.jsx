import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { useCart } from '../context/CartContext';
import './VendorAssignment.css';
import { dashboardGet, dashboardPost } from '../api/dashboardApi';
import { useConfirm } from '../components/ConfirmProvider';

const VendorAssignment = () => {
  const navigate = useNavigate();
  const { selectedBuild, userRequirements } = useApp();
  const { addToCart, cartItems } = useCart();
  const { confirm } = useConfirm();
  const [selectedVendor, setSelectedVendor] = useState(null);
  const [vendors, setVendors] = useState([]);
  const [vendorsLoading, setVendorsLoading] = useState(false);
  const [vendorsError, setVendorsError] = useState(null);
  const [vendorBlockLoading, setVendorBlockLoading] = useState(false);
  const [vendorBlockError, setVendorBlockError] = useState(null);
  const [placing, setPlacing] = useState(false);
  const [confirmError, setConfirmError] = useState('');

  useEffect(() => {
    const loadVendors = async () => {
      try {
        setVendorsLoading(true);
        setVendorsError(null);
        const res = await dashboardGet('/vendors');
        // API returns { success, count, vendors: [...] }
        const list = Array.isArray(res?.vendors) ? res.vendors : [];
        setVendors(list);
      } catch (err) {
        console.error('Failed to load vendors', err);
        setVendorsError(err.message || 'Failed to load vendors');
      } finally {
        setVendorsLoading(false);
      }
    };

    loadVendors();
  }, []);

  useEffect(() => {
    // Keep CTA usable: auto-pick first vendor when list is available.
    if (!selectedVendor && vendors.length > 0) {
      setSelectedVendor(vendors[0]);
    }
  }, [vendors, selectedVendor]);

  const refreshVendors = async () => {
    try {
      const res = await dashboardGet('/vendors');
      const list = Array.isArray(res?.vendors) ? res.vendors : [];
      setVendors(list);
    } catch (err) {
      console.error('Failed to refresh vendors', err);
    }
  };

  const handleBlockVendor = async (vendor) => {
    if (!vendor?.id) return;
    const ok = await confirm({
      title: 'Remove vendor?',
      message: `Remove "${vendor.shop_name || vendor.name}" from the assignment list?`,
      confirmText: 'Remove',
      danger: true,
    });
    if (!ok) return;

    try {
      setVendorBlockLoading(true);
      setVendorBlockError(null);
      const res = await dashboardPost(`/vendors/${vendor.id}/block`, {});
      if (!res?.success) {
        throw new Error(res?.error || res?.message || 'Failed to block vendor');
      }

      // Update UI after DB change.
      setSelectedVendor(null);
      await refreshVendors();
    } catch (err) {
      setVendorBlockError(err.message || 'Failed to block vendor');
    } finally {
      setVendorBlockLoading(false);
    }
  };

  /** Show every vendor returned from the API (all approved in DB), not filtered by city */
  const displayVendors = vendors;

  const normalizeQuery = (value) => String(value || '')
    .replace(/[•|,/()]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  const buildPartQueries = (part) => {
    const rawValue = normalizeQuery(part?.value);
    const rawName = normalizeQuery(part?.name);
    const shortValue = rawValue.split(' ').slice(0, 3).join(' ');

    const byCategory = {
      CPU: ['processor', 'cpu'],
      GPU: ['graphics card', 'gpu'],
      RAM: ['ram', 'memory'],
      Motherboard: ['motherboard'],
      Storage: ['ssd', 'storage'],
      PSU: ['power supply', 'psu'],
      Case: ['cabinet', 'case'],
    };

    const q = [
      rawValue,
      shortValue,
      rawName,
      ...(byCategory[rawName] || []),
    ]
      .map((s) => s.trim())
      .filter(Boolean);

    return [...new Set(q)];
  };

  const addBuildPartsAsComponents = async (vendorId) => {
    const parts = Array.isArray(selectedBuild?.parts) ? selectedBuild.parts : [];
    let addedCount = 0;
    const usedComponentIds = new Set();

    for (const part of parts) {
      const query = String(part?.value || part?.name || '').trim().toLowerCase();
      if (!query || query === 'integrated') continue;

      try {
        const queries = buildPartQueries(part);
        let candidates = [];

        for (const q of queries) {
          const res = await dashboardGet(`/components/search?q=${encodeURIComponent(q)}&limit=20`);
          const list = (Array.isArray(res?.components) ? res.components : [])
            .filter((c) => Number(c.stock || 0) > 0)
            .filter((c) => !usedComponentIds.has(c.id));
          if (list.length > 0) {
            candidates = list;
            break;
          }
        }

        if (candidates.length === 0) continue;

        let partAdded = false;
        for (const candidate of candidates) {
          // 1) Prefer selected vendor, 2) fallback to auto vendor assignment.
          const withSelectedVendor = await addToCart(
            {
              id: candidate.id,
              item_type: 'component',
              vendor_id: vendorId || null,
            },
            1
          );
          if (withSelectedVendor) {
            usedComponentIds.add(candidate.id);
            addedCount += 1;
            partAdded = true;
            break;
          }

          if (vendorId) {
            const withAutoVendor = await addToCart(
              {
                id: candidate.id,
                item_type: 'component',
                vendor_id: null,
              },
              1
            );
            if (withAutoVendor) {
              usedComponentIds.add(candidate.id);
              addedCount += 1;
              partAdded = true;
              break;
            }
          }
        }

        if (!partAdded) {
          continue;
        }
      } catch (_) {
        // Skip failed match and keep trying remaining parts.
      }
    }

    return addedCount > 0;
  };

  const handleConfirmOrder = async () => {
    const vendor = selectedVendor || (displayVendors.length > 0 ? displayVendors[0] : null);
    if (!vendor) return;
    setConfirmError('');

    // If cart already has items, continue directly to checkout.
    if (Array.isArray(cartItems) && cartItems.length > 0) {
      navigate('/checkout', { replace: true });
      return;
    }

    setPlacing(true);
    try {
      const ok = await addBuildPartsAsComponents(vendor?.id || null);

      if (ok) {
        navigate('/checkout', { replace: true });
      } else {
        setConfirmError('Selected build components are not available right now. Please try another build.');
      }
    } catch (_) {
      setConfirmError('Unable to continue to payment right now. Please try again.');
    } finally {
      setPlacing(false);
    }
  };

  const totalPrice = selectedBuild?.parts?.reduce((sum, part) => sum + (part.price || 0), 0) || selectedBuild?.price || 0;
  const assemblyFee = selectedVendor?.serviceCost || 5000;
  const shipping = 2000;
  const finalTotal = totalPrice + assemblyFee + shipping;

  return (
    <div className="vendor-assignment-page">
      <div className="container">
        <div className="page-header vendor-page-header">
          <h1>Finish your order</h1>
          <p className="vendor-page-lede">
            Pick who builds or ships your PC and review totals, then continue to payment.
          </p>
        </div>

        <div className="assignment-grid">
          <div className="vendors-panel">
            <h2 className="vendors-panel-title">Choose a vendor</h2>
            <p className="vendors-panel-sub">
              All approved partners from the database
              {userRequirements.city ? (
                <>
                  {' · '}
                  your preference: <strong>{userRequirements.city}</strong>
                </>
              ) : null}
              {' · '}
              tap a row to select
            </p>
            <div className="vendor-options">
              <label className="option-toggle">
                <input
                  type="radio"
                  name="assign"
                  value="auto"
                  defaultChecked
                />
                <span>Let us pick the best match</span>
              </label>
              <label className="option-toggle">
                <input
                  type="radio"
                  name="assign"
                  value="manual"
                  onChange={() => setSelectedVendor(null)}
                />
                <span>I’ll choose myself</span>
              </label>
            </div>

            <div className="vendors-list-wrap">
              {vendorsLoading && (
                <div className="info-message">Loading vendors...</div>
              )}
              {vendorsError && !vendorsLoading && (
                <div className="error-message">{vendorsError}</div>
              )}
              {vendorBlockError && (
                <div className="error-message">{vendorBlockError}</div>
              )}
              {!vendorsLoading && !vendorsError && displayVendors.length === 0 && (
                <div className="info-message">No vendors available.</div>
              )}
              {!vendorsLoading && !vendorsError && displayVendors.length > 0 && (
                <div className="vendors-table" role="group">
                  <div className="vendors-list-head" id="vendors-list-head">
                    <span className="vendors-col-vendor">Vendor</span>
                    <span className="vendors-col-meta">City &amp; phone</span>
                    <span className="vendors-col-action" aria-hidden="true" />
                  </div>
                  <div
                    className="vendors-list-scroll"
                    role="listbox"
                    aria-labelledby="vendors-list-head"
                  >
                  {displayVendors.map((vendor) => {
                    const label = vendor.shop_name || vendor.name || 'Vendor';
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
                        <div className="vendor-row-main">
                          <span className="vendor-avatar" aria-hidden>
                            {initial}
                          </span>
                          <div className="vendor-row-text">
                            <span className="vendor-name">{label}</span>
                            {(vendor.approval_status || 'approved') === 'approved' && (
                              <span className="vendor-badge">Verified</span>
                            )}
                          </div>
                        </div>
                        <div className="vendor-row-meta">
                          <span>{vendor.city || '—'}</span>
                          <span className="vendor-row-phone">{vendor.phone || '—'}</span>
                        </div>
                        {selected && (
                          <button
                            type="button"
                            className="vendor-remove-inline"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleBlockVendor(vendor);
                            }}
                            disabled={vendorBlockLoading}
                          >
                            {vendorBlockLoading ? '…' : 'Remove'}
                          </button>
                        )}
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
              <div className="summary-item">
                <span>Assembly fee</span>
                <span>PKR {assemblyFee.toLocaleString('en-US')}</span>
              </div>
              <div className="summary-item">
                <span>Shipping</span>
                <span>PKR {shipping.toLocaleString('en-US')}</span>
              </div>
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
              disabled={placing || vendorsLoading || displayVendors.length === 0}
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







