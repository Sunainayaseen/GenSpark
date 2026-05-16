import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { useCart } from '../context/CartContext';
import {
  getPrebuiltById,
  QUICK_REQUIREMENTS,
  prebuiltToConfiguratorBuild,
} from '../data/prebuiltShowcase';
import './PrebuiltDetail.css';

const PrebuiltDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { setSelectedBuild, updateRequirements } = useApp();
  const { addToCart, setIsCartOpen } = useCart();
  const [adding, setAdding] = useState(false);

  const item = useMemo(() => getPrebuiltById(id), [id]);

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

  const handleAddToCart = async () => {
    setAdding(true);
    try {
      const ok = await addToCart({ id: item.id, item_type: 'pc_build' });
      if (ok) setIsCartOpen(true);
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
              />
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
              <div className="prebuilt-detail-stat">
                <dt>Price</dt>
                <dd>PKR {item.price.toLocaleString()}</dd>
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
                {item.parts.map((part, idx) => (
                  <li key={idx} className="prebuilt-detail-spec-row">
                    <span className="prebuilt-detail-spec-label">{part.name}</span>
                    <span className="prebuilt-detail-spec-value">{part.value}</span>
                  </li>
                ))}
              </ul>
            </section>

            <p className="prebuilt-detail-cart-note">
              Add to cart links this SKU to inventory-backed parts when the same build exists in our system.
              If checkout is unavailable, use <strong>Customize</strong> to finalize components.
            </p>

            <div className="prebuilt-detail-actions">
              <button
                type="button"
                className="btn btn-primary prebuilt-detail-btn-primary"
                onClick={handleAddToCart}
                disabled={adding}
              >
                {adding ? 'Adding…' : 'Add to cart'}
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
