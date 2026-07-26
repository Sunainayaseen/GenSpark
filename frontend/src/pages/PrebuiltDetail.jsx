import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { useCart } from '../context/CartContext';
import {
  getPrebuiltById,
  QUICK_REQUIREMENTS,
  prebuiltToConfiguratorBuild,
} from '../data/prebuiltShowcase';
import { resolveBuildParts, addResolvedBuildToCart } from '../utils/buildResolver';
import './PrebuiltDetail.css';

const PrebuiltDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { setSelectedBuild, updateRequirements } = useApp();
  const { addBuildToCart, setIsCartOpen } = useCart();
  const [adding, setAdding] = useState(false);

  const item = useMemo(() => getPrebuiltById(id), [id]);

  // ERP-backed resolution: map static parts → real catalog components.
  const [resolving, setResolving] = useState(false);
  const [resolution, setResolution] = useState(null); // { slots, summary }
  const [cartMsg, setCartMsg] = useState(null); // { type, text }

  useEffect(() => {
    if (!item?.parts) return undefined;
    let alive = true;
    setResolving(true);
    setResolution(null);
    setCartMsg(null);
    resolveBuildParts(item.parts)
      .then((result) => {
        if (alive) setResolution(result);
      })
      .catch(() => {
        if (alive) setResolution(null);
      })
      .finally(() => {
        if (alive) setResolving(false);
      });
    return () => {
      alive = false;
    };
  }, [item]);

  if (!item) {
    return (
      <div className="prebuilt-detail-page prebuilt-detail-notfound">
        <div className="prebuilt-detail-container">
          <h1>PC not found</h1>
          <p>This prebuilt configuration is not in the catalog.</p>
          <Link to="/builds" className="btn btn-primary">
            Back to Prebuilt PCs
          </Link>
        </div>
      </div>
    );
  }

  const buildForContext = () => prebuiltToConfiguratorBuild(item);

  // Match a static part row to its ERP resolution (by slot + requested value).
  const resolutionForPart = (part) => {
    if (!resolution?.slots) return null;
    const value = String(part?.value || '').trim().toLowerCase();
    return (
      resolution.slots.find(
        (s) => s.requested.toLowerCase() === value && s.label === part.name
      ) ||
      resolution.slots.find((s) => s.requested.toLowerCase() === value) ||
      null
    );
  };

  const summary = resolution?.summary || null;
  // Each status maps to a consistent pill class in PrebuiltDetail.css
  // (in = soft green, out = amber/warning, missing = red, included = neutral).
  const STATUS_BADGE = {
    resolved: { text: 'In stock', cls: 'in' },
    out_of_stock: { text: 'Out of stock', cls: 'out' },
    not_found: { text: 'Not in catalog', cls: 'missing' },
    skipped: { text: 'Included', cls: 'included' },
  };

  const handleAddToCart = async () => {
    if (!resolution?.slots?.length) {
      setCartMsg({ type: 'error', text: 'Parts are still being matched to inventory. Please wait a moment.' });
      return;
    }
    setAdding(true);
    setCartMsg(null);
    try {
      const { added, failed, vendor, error, conflict } = await addResolvedBuildToCart(
        resolution.slots,
        addBuildToCart
      );
      if (added > 0) {
        setIsCartOpen(true);
        const note = failed.length
          ? ` (${failed.length} part${failed.length > 1 ? 's' : ''} skipped: ${failed.join(', ')})`
          : '';
        const vendorNote = vendor?.shop_name ? ` — all sourced from ${vendor.shop_name}.` : '';
        setCartMsg({ type: 'success', text: `${added} component${added > 1 ? 's' : ''} added to cart.${vendorNote}${note}` });
      } else if (conflict) {
        setCartMsg({
          type: 'error',
          text: 'This Prebuilt PC is currently unavailable because no vendor has all required components in stock.',
        });
      } else if (error) {
        setCartMsg({ type: 'error', text: error });
      } else {
        setCartMsg({
          type: 'error',
          text: 'None of these parts are available in inventory yet. Use Customize to pick alternatives.',
        });
      }
    } finally {
      setAdding(false);
    }
  };

  const handleConfigure = () => {
    setSelectedBuild(buildForContext());
    navigate('/configurator');
  };

  const handleVendor = () => {
    setSelectedBuild(buildForContext());
    navigate('/vendor-assignment');
  };

  const handleAskAi = () => {
    updateRequirements(QUICK_REQUIREMENTS[item.quickKey] || QUICK_REQUIREMENTS.gaming);
    navigate('/chatbot');
  };

  // Generic catalog term per slot — opens the configurator search so the user can
  // pick an in-stock alternative for a part that isn't in the catalog / is sold out.
  const FIND_ALT_QUERY = {
    CPU: 'processor',
    GPU: 'graphics card',
    Motherboard: 'motherboard',
    RAM: 'ram',
    Storage: 'ssd',
    PSU: 'power supply',
    Case: 'case',
  };

  const handleFindAlternatives = (part) => {
    const term = FIND_ALT_QUERY[part?.name] || part?.value || part?.name || '';
    navigate(`/configurator?q=${encodeURIComponent(term)}`);
  };

  return (
    <div className="prebuilt-detail-page">
      <div className="prebuilt-detail-container">
        <nav className="prebuilt-detail-breadcrumb" aria-label="Breadcrumb">
          <Link to="/builds">Predefined PCs</Link>
          <span aria-hidden="true">/</span>
          <span className="prebuilt-detail-breadcrumb-current">{item.title}</span>
        </nav>

        <article className={`prebuilt-detail-card ${item.cardClass}`}>
          <div className="prebuilt-detail-hero">
            <div className="prebuilt-detail-accent" aria-hidden="true" />
            <div className="prebuilt-detail-image-wrap">
              <img
                className="prebuilt-detail-image"
                src={item.heroImage}
                alt={`${item.title} — ${item.category} PC`}
                loading="eager"
                decoding="async"
                onError={(e) => {
                  e.currentTarget.style.display = 'none';
                  e.currentTarget.parentElement.classList.add('prebuilt-detail-image-wrap--fallback');
                }}
              />
              <span className="prebuilt-detail-image-fallback-label" aria-hidden="true">
                {item.title}
              </span>
            </div>
            <div className="prebuilt-detail-price-chip">
              PKR {item.price.toLocaleString('en-US')}
            </div>
          </div>

          <div className="prebuilt-detail-body">
            <header className="prebuilt-detail-header">
              <p className="prebuilt-detail-category">{item.category}</p>
              <h1 className="prebuilt-detail-title">{item.title}</h1>
              <p className="prebuilt-detail-desc">{item.desc}</p>
              <p className="prebuilt-detail-summary">{item.specs}</p>
            </header>

            <dl className="prebuilt-detail-stats">
              <div className="prebuilt-detail-stat prebuilt-detail-stat--price">
                <dt>Price</dt>
                <dd>
                  {summary && summary.total > 0 ? (
                    <>
                      PKR {summary.total.toLocaleString('en-US')}
                      <span className="prebuilt-detail-stat-sub">
                        live inventory · est. PKR {item.price.toLocaleString('en-US')}
                      </span>
                    </>
                  ) : (
                    <>PKR {item.price.toLocaleString('en-US')}</>
                  )}
                </dd>
              </div>
              <div className="prebuilt-detail-stat">
                <dt>Performance</dt>
                <dd>
                  <span className="prebuilt-detail-stat-bar-wrap" role="presentation">
                    <span
                      className="prebuilt-detail-stat-bar-fill"
                      style={{ width: `${item.performanceScore}%` }}
                    />
                  </span>
                  {item.performanceScore}/100
                </dd>
              </div>
              <div className="prebuilt-detail-stat">
                <dt>Est. power</dt>
                <dd>{item.wattage}W</dd>
              </div>
              <div className="prebuilt-detail-stat">
                <dt>Vendor ETA</dt>
                <dd>{item.vendorETA}</dd>
              </div>
            </dl>

            <section className="prebuilt-detail-specs" aria-labelledby="prebuilt-specs-heading">
              <h2 id="prebuilt-specs-heading" className="prebuilt-detail-specs-heading">
                Full specifications
              </h2>
              <ul className="prebuilt-detail-specs-list">
                {item.parts.map((part, idx) => {
                  const res = resolutionForPart(part);
                  const badge = res ? STATUS_BADGE[res.status] : null;
                  const matchedName = res?.component?.name;
                  const showMatched = matchedName && matchedName.toLowerCase() !== part.value.toLowerCase();
                  return (
                    <li key={idx} className="prebuilt-detail-spec-row">
                      <span className="prebuilt-detail-spec-label">{part.name}</span>
                      <span className="prebuilt-detail-spec-value">
                        {part.value}
                        {showMatched && (
                          <span className="prebuilt-detail-spec-matched">
                            ↳ matched: {matchedName}
                          </span>
                        )}
                        {resolving && !res && (
                          <span className="prebuilt-detail-spec-matching">
                            matching inventory…
                          </span>
                        )}
                        {badge && res.status !== 'skipped' && (
                          <span className={`prebuilt-stock-badge prebuilt-stock-badge--${badge.cls}`}>
                            {badge.text}
                            {res.component?.price > 0 && ` · PKR ${res.component.price.toLocaleString('en-US')}`}
                          </span>
                        )}
                        {(res?.status === 'not_found' || res?.status === 'out_of_stock') && (
                          <button
                            type="button"
                            className="prebuilt-find-alt"
                            onClick={() => handleFindAlternatives(part)}
                            aria-label={`Find alternatives for ${part.name}`}
                          >
                            Find alternatives →
                          </button>
                        )}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </section>

            <p className="prebuilt-detail-cart-note">
              Add to cart resolves each part to live vendor inventory and adds the in-stock components individually.
              Parts not yet in the catalog are skipped — use <strong>Customize</strong> to pick alternatives.
              {summary && summary.fullyResolved && ' All parts are available.'}
              {summary && !summary.fullyResolved && summary.missingLabels?.length > 0 &&
                ` Not in catalog: ${summary.missingLabels.join(', ')}.`}
            </p>

            {cartMsg && (
              <p
                role="status"
                className={`prebuilt-detail-cart-msg prebuilt-detail-cart-msg--${cartMsg.type}`}
              >
                {cartMsg.text}
              </p>
            )}

            <div className="prebuilt-detail-actions">
              <button
                type="button"
                className="btn btn-primary prebuilt-detail-btn-primary"
                onClick={handleAddToCart}
                disabled={adding || resolving || !summary || summary.addableCount === 0}
              >
                {adding
                  ? 'Adding…'
                  : resolving
                    ? 'Checking stock…'
                    : summary && summary.addableCount === 0
                      ? 'Unavailable'
                      : 'Add to cart'}
              </button>
              <button type="button" className="btn btn-secondary" onClick={handleConfigure}>
                Customize build
              </button>
              <button type="button" className="btn btn-secondary" onClick={handleVendor}>
                Proceed to vendors
              </button>
              <button type="button" className="btn btn-secondary" onClick={handleAskAi}>
                Refine with AI
              </button>
              <Link to="/cart" className="prebuilt-detail-link-cart">
                View cart
              </Link>
            </div>
          </div>
        </article>
      </div>
    </div>
  );
};

export default PrebuiltDetail;
