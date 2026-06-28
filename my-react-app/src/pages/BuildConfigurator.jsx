import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { useCart } from '../context/CartContext';
import { dashboardGet } from '../api/dashboardApi';
import { resolveBuildParts, addResolvedBuildToCart } from '../utils/buildResolver';
import { ASSEMBLY_FEE, textNeedsAssembly } from '../utils/assemblyFee';
import './BuildConfigurator.css';

/** Generic catalog search term per slot — powers the "Find alternatives" action. */
const SLOT_SEARCH_TERM = {
  cpu: 'processor',
  gpu: 'graphics card',
  motherboard: 'motherboard',
  ram: 'ram',
  storage: 'ssd',
  psu: 'power supply',
  case: 'case',
};

const SHIPPING_FEE = 2000;

const STATUS_BADGE = {
  out_of_stock: { text: 'Out of stock', color: '#b45309', bg: '#fef3c7' },
  not_found: { text: 'Not in catalog', color: '#b91c1c', bg: '#fee2e2' },
  skipped: { text: 'Included', color: '#047857', bg: '#d1fae5' },
  pending: { text: 'Checking…', color: '#475569', bg: '#e2e8f0' },
};

const StatusBadge = ({ status }) => {
  const cfg = STATUS_BADGE[status];
  if (!cfg) return null;
  return (
    <span
      style={{
        fontSize: '0.72rem',
        fontWeight: 600,
        padding: '2px 8px',
        borderRadius: 999,
        color: cfg.color,
        background: cfg.bg,
        whiteSpace: 'nowrap',
      }}
    >
      {cfg.text}
    </span>
  );
};

const BuildConfigurator = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { selectedBuild } = useApp();
  const { addToCart } = useCart();

  // --- Build resolution (curated prebuilt -> real catalog components) ---
  const [resolution, setResolution] = useState(null);
  const [resolving, setResolving] = useState(false);
  const [resolveError, setResolveError] = useState('');
  const [adding, setAdding] = useState(false);
  const [addResult, setAddResult] = useState(null);

  // Re-resolve only when the build's parts actually change.
  const partsKey = useMemo(() => JSON.stringify(selectedBuild?.parts || []), [selectedBuild]);

  useEffect(() => {
    const parts = selectedBuild?.parts;
    if (!Array.isArray(parts) || parts.length === 0) {
      setResolution(null);
      setResolving(false);
      return undefined;
    }

    let alive = true;
    setResolving(true);
    setResolveError('');
    setAddResult(null);
    resolveBuildParts(parts)
      .then((res) => {
        if (alive) setResolution(res);
      })
      .catch((err) => {
        if (alive) setResolveError(err?.message || 'Could not load live pricing from inventory.');
      })
      .finally(() => {
        if (alive) setResolving(false);
      });
    return () => {
      alive = false;
    };
  }, [partsKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const summary = resolution?.summary;
  const slots = resolution?.slots || [];
  // Charge estimate must reflect what actually enters the cart: in-stock resolved parts
  // only (out-of-stock parts are listed but never added → never charged).
  const partsSubtotal = Number(summary?.addableTotal ?? summary?.total ?? 0);
  const hasAddable = Number(summary?.addableCount || 0) > 0;
  // Assembly fee applies only to an assemble-able PC (a CPU + a motherboard in the
  // cart) — identical rule to Checkout.jsx cartNeedsAssembly + backend fees.py. This
  // stops a component-only build from showing a +5000 fee it won't be charged.
  const buildNeedsAssembly = useMemo(
    () =>
      textNeedsAssembly(
        slots
          .filter((s) => s.status === 'resolved')
          .map((s) => (s.component?.name || s.label || '').toLowerCase())
          .join(' | ')
      ),
    // depend on `resolution` (stable until it's actually re-set), not the locally
    // derived `slots` (a fresh [] literal every render when resolution.slots is falsy)
    [resolution]
  );
  const assemblyFee = buildNeedsAssembly ? ASSEMBLY_FEE : 0;
  const shippingFee = hasAddable ? SHIPPING_FEE : 0;
  const finalTotal = partsSubtotal + assemblyFee + shippingFee;
  const canAdd = !resolving && !adding && hasAddable;

  // Stock chip colour reflects reality: green = all matched, amber = partial, red = none.
  // Denominator excludes skipped slots (e.g. iGPU build's GPU) so an all-in-stock
  // build never shows a misleading "6/7".
  const inStockCount = Number(summary?.resolvedCount || 0);
  const applicableCount = Number(summary?.applicableCount ?? slots.length);
  const stockChipClass = !summary
    ? 'cfg-chip--muted'
    : inStockCount === 0
      ? 'cfg-chip--bad'
      : inStockCount < applicableCount
        ? 'cfg-chip--warn'
        : 'cfg-chip--ok';

  const performAdd = async () => {
    if (!resolution) return null;
    setAdding(true);
    try {
      const result = await addResolvedBuildToCart(resolution.slots, addToCart, { silent: true });
      setAddResult(result);
      return result;
    } catch (err) {
      setAddResult({ added: 0, failed: [], error: err?.message || 'Add to cart failed' });
      return null;
    } finally {
      setAdding(false);
    }
  };

  const handleAddToCart = async () => {
    const result = await performAdd();
    if (result && result.added > 0) navigate('/cart');
  };

  const handleAddAndChooseVendor = async () => {
    const result = await performAdd();
    if (result && result.added > 0) navigate('/vendor-assignment');
  };

  // --- Header-search browse mode (/configurator?q=...) ---
  const query = new URLSearchParams(location.search).get('q') || '';
  const normalizedQuery = query.trim();

  const [dbComponents, setDbComponents] = useState([]);
  const [dbLoading, setDbLoading] = useState(false);
  const [dbError, setDbError] = useState('');
  const [vendorSuggestions, setVendorSuggestions] = useState({});
  const [addingId, setAddingId] = useState(null);

  useEffect(() => {
    if (!normalizedQuery) {
      setDbComponents([]);
      setDbError('');
      return undefined;
    }

    let alive = true;
    setDbLoading(true);
    setDbError('');
    dashboardGet(`/components/search?q=${encodeURIComponent(normalizedQuery)}&limit=50&vendor_summary=1`)
      .then((data) => {
        if (alive) setDbComponents(Array.isArray(data?.components) ? data.components : []);
      })
      .catch((err) => {
        if (alive) {
          setDbError(err?.message || 'Failed to load components');
          setDbComponents([]);
        }
      })
      .finally(() => {
        if (alive) setDbLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [normalizedQuery]);

  const handleSuggestVendors = async (componentOption) => {
    if (!componentOption?.id) return;
    try {
      const res = await dashboardGet(`/components/${componentOption.id}/vendors`);
      const list = Array.isArray(res?.vendors) ? res.vendors : [];
      setVendorSuggestions((prev) => ({ ...prev, [componentOption.id]: list }));
    } catch {
      setVendorSuggestions((prev) => ({ ...prev, [componentOption.id]: [] }));
    }
  };

  const handleAddComponentToCart = async (componentOption, vendorId = null) => {
    if (!componentOption?.id) return;
    setAddingId(componentOption.id);
    try {
      await addToCart({
        id: componentOption.id,
        name: componentOption.name,
        title: componentOption.name,
        price: Number(componentOption.price || 0),
        stock: Number(componentOption.stock || 0),
        image_url: componentOption.image_url,
        item_type: 'component',
        vendor_id: vendorId ?? undefined,
      });
    } finally {
      setAddingId(null);
    }
  };

  const searchOptions = useMemo(
    () =>
      dbComponents.map((c) => ({
        id: c.id,
        name: c.name,
        brand: c.brand || '',
        price: Number(c.price || 0),
        category: c.category || '',
        stock: Number(c.stock || 0),
      })),
    [dbComponents]
  );

  const hasBuild = Array.isArray(selectedBuild?.parts) && selectedBuild.parts.length > 0;

  // While resolving, fall back to the requested parts so the layout is stable.
  const displayRows = slots.length
    ? slots
    : (selectedBuild?.parts || []).map((p) => ({
        slot: String(p.name || '').toLowerCase(),
        label: p.name,
        requested: p.value,
        status: 'pending',
        component: null,
      }));

  const searchSection = normalizedQuery ? (
    <div className="compatible-parts">
      <h3>Search results for “{normalizedQuery}”</h3>

      {dbLoading && <div className="no-results">Loading components…</div>}
      {!dbLoading && dbError && (
        <div className="no-results" role="alert">
          {dbError}
        </div>
      )}

      {!dbLoading && !dbError && (
        <div className="parts-options">
          {searchOptions.length === 0 ? (
            <div className="no-results" role="status">
              No matching components found for “{normalizedQuery}”.
            </div>
          ) : (
            searchOptions.map((opt) => (
              <div key={opt.id} className="part-option">
                <div className="option-name">{opt.name}</div>
                <div className="option-brand">{opt.brand}</div>
                <div className="option-price">PKR {opt.price.toLocaleString('en-US')}</div>
                <div className="option-warning">
                  {opt.stock > 0 ? `In stock: ${opt.stock}` : 'Out of stock'}
                </div>
                <button
                  type="button"
                  className="btn btn-secondary add-component-btn"
                  onClick={() => handleSuggestVendors(opt)}
                >
                  Suggest Available Vendors
                </button>
                <button
                  type="button"
                  className="btn btn-primary add-component-btn"
                  onClick={() => handleAddComponentToCart(opt)}
                  disabled={opt.stock <= 0 || addingId === opt.id}
                >
                  {opt.stock <= 0 ? 'Out of Stock' : addingId === opt.id ? 'Adding…' : 'Add Component to Cart'}
                </button>
                {Array.isArray(vendorSuggestions[opt.id]) && (
                  <div className="vendor-suggestions-list">
                    {vendorSuggestions[opt.id].length === 0 ? (
                      <div className="vendor-suggestion-empty">
                        No approved vendor currently has this component.
                      </div>
                    ) : (
                      vendorSuggestions[opt.id].map((v) => (
                        <div key={v.id} className="vendor-suggestion-item">
                          <div className="vendor-suggestion-main">
                            <span className="vendor-shop">{v.shop_name}</span>
                            <span className="vendor-meta">
                              {v.city || 'N/A'} {v.phone ? `• ${v.phone}` : ''}
                            </span>
                          </div>
                          <span className="vendor-stock">Stock: {v.available_quantity}</span>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            style={{ marginTop: 6 }}
                            onClick={() => handleAddComponentToCart(opt, v.id)}
                          >
                            Add from this vendor
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  ) : null;

  return (
    <div className="configurator-page">
      <div className="container">
        <header className="config-page-header">
          <div className="config-page-header-main">
            <p className="config-page-eyebrow">Configure</p>
            <h1 className="config-page-title">Build configurator</h1>
            <p className="config-page-lede">
              We match each part to live inventory, then add the build to your cart with real PKR pricing.
            </p>
            {hasBuild ? (
              <div className="config-build-chip" title="Current build">
                <span className="config-build-chip-label">Build</span>
                <span className="config-build-chip-name">{selectedBuild.title}</span>
              </div>
            ) : null}
          </div>
          <button type="button" className="config-back-btn" onClick={() => navigate('/builds')}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
            <span>Back to Prebuilt PCs</span>
          </button>
        </header>

        {hasBuild ? (
          <div className="configurator-grid">
            <section className="compatibility-panel config-panel" aria-labelledby="compat-heading">
              <div className="config-panel-head">
                <h2 id="compat-heading" className="config-panel-title">
                  Compatibility &amp; estimate
                </h2>
                <p className="config-panel-desc">
                  Quick checks before you commit. Final validation happens at checkout.
                </p>
              </div>

              <div className="compatibility-status" role="status">
                <span className="cfg-chip cfg-chip--ok">Compatible</span>
                <span className="cfg-chip cfg-chip--ok">Power OK</span>
                {resolving ? (
                  <span className="cfg-chip cfg-chip--muted">Checking inventory…</span>
                ) : summary ? (
                  <span className={`cfg-chip ${stockChipClass}`}>
                    {summary.resolvedCount}/{applicableCount} in stock
                  </span>
                ) : null}
              </div>

              {summary && (summary.missingCount > 0 || summary.outOfStockCount > 0) ? (
                <div className="cfg-gap-note" role="status">
                  {summary.missingCount > 0 ? (
                    <p>
                      <strong>Not in catalog:</strong> {summary.missingLabels.join(', ')}
                    </p>
                  ) : null}
                  {summary.outOfStockCount > 0 ? (
                    <p>
                      <strong>Out of stock:</strong> {summary.outOfStockLabels.join(', ')}
                    </p>
                  ) : null}
                  <p className="cfg-gap-hint">Use “Find alternatives” on a part to pick an in-stock match.</p>
                </div>
              ) : null}

              <div className="price-breakdown">
                <h3 className="price-breakdown-title">Price estimate</h3>
                <div className="price-item">
                  <span className="price-item-label">Parts subtotal</span>
                  <span className="price-item-value">
                    {resolving ? 'Checking…' : `PKR ${partsSubtotal.toLocaleString('en-US')}`}
                  </span>
                </div>
                {assemblyFee > 0 ? (
                  <div className="price-item">
                    <span className="price-item-label">Assembly</span>
                    <span className="price-item-value">PKR {assemblyFee.toLocaleString('en-US')}</span>
                  </div>
                ) : null}
                {shippingFee > 0 ? (
                  <div className="price-item">
                    <span className="price-item-label">Shipping (est.)</span>
                    <span className="price-item-value">PKR {shippingFee.toLocaleString('en-US')}</span>
                  </div>
                ) : null}
                <div className="price-item total">
                  <span className="price-item-label">Estimated total</span>
                  <span className="price-item-value">
                    {resolving ? '—' : `PKR ${finalTotal.toLocaleString('en-US')}`}
                  </span>
                </div>
              </div>

              <div className="config-cta-group">
                <button
                  type="button"
                  className="btn btn-primary btn-lg config-cta-primary"
                  onClick={handleAddToCart}
                  disabled={!canAdd}
                >
                  {adding
                    ? 'Adding to cart…'
                    : resolving
                      ? 'Checking inventory…'
                      : `Add build to cart${summary?.addableCount ? ` (${summary.addableCount})` : ''}`}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-lg config-cta-secondary"
                  onClick={handleAddAndChooseVendor}
                  disabled={!canAdd}
                >
                  Add &amp; choose vendor
                </button>

                {resolveError ? (
                  <p className="cfg-inline-msg cfg-inline-msg--error" role="alert">
                    {resolveError}
                  </p>
                ) : null}

                {addResult ? (
                  <p className="cfg-inline-msg" role="status">
                    {addResult.added > 0
                      ? `Added ${addResult.added} component${addResult.added === 1 ? '' : 's'} to your cart.`
                      : 'These parts aren’t in stock yet — pick alternatives from the catalog.'}
                  </p>
                ) : null}
              </div>
            </section>

            <section className="filters-panel config-panel" aria-labelledby="build-components-heading">
              <div className="config-build-components">
                <h2 id="build-components-heading" className="config-build-components-title">
                  Configured components
                </h2>
                <p className="config-build-components-lede">Matched from live catalog inventory.</p>
                <ul className="config-build-components-list">
                  {displayRows.map((row) => (
                    <li key={`${row.slot}-${row.label}`} className="config-build-component-row">
                      <span className="config-build-component-slot">{row.label}</span>
                      <span className="config-build-component-value">
                        {row.component?.name || row.requested || '—'} <StatusBadge status={row.status} />
                      </span>
                      {row.status === 'resolved' && Number(row.component?.price) > 0 ? (
                        <span className="config-build-component-price">
                          PKR {Number(row.component.price).toLocaleString('en-US')}
                        </span>
                      ) : (
                        <span className="config-build-component-price config-build-component-price--pending">
                          —
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>

              {searchSection}
            </section>
          </div>
        ) : normalizedQuery ? (
          <section className="filters-panel config-panel" aria-label="Component search">
            {searchSection}
          </section>
        ) : (
          <section className="config-panel" aria-label="No build selected">
            <div className="config-panel-head">
              <h2 className="config-panel-title">No build selected yet</h2>
              <p className="config-panel-desc">
                Choose a prebuilt PC to configure, price, and add to your cart.
              </p>
            </div>
            <button type="button" className="btn btn-primary btn-lg" onClick={() => navigate('/builds')}>
              Browse Prebuilt PCs
            </button>
          </section>
        )}
      </div>
    </div>
  );
};

export default BuildConfigurator;
