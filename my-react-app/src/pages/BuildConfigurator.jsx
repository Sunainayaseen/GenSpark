import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { useCart } from '../context/CartContext';
import { dashboardGet } from '../api/dashboardApi';
import { getFlaskBase, getFlaskBaseFallback } from '../utils/flaskBase';
import { allocateMissingLinePricesFromPackage } from '../data/prebuiltShowcase';
import './BuildConfigurator.css';

const BuildConfigurator = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { selectedBuild, setSelectedBuild } = useApp();
  const { addToCart } = useCart();
  const [selectedPart, setSelectedPart] = useState(null);
  const [vendorSuggestions, setVendorSuggestions] = useState({});

  // Mock compatible parts - in real app, this would come from API
  const compatibleParts = {
    CPU: [
      { name: 'AMD Ryzen 7 5800X', price: 25000, brand: 'AMD', compatible: true },
      { name: 'AMD Ryzen 9 5900X', price: 35000, brand: 'AMD', compatible: true },
      { name: 'Intel i7-12700K', price: 30000, brand: 'Intel', compatible: true, warning: 'BIOS update required' },
    ],
    GPU: [
      { name: 'NVIDIA RTX 4070', price: 55000, brand: 'NVIDIA', compatible: true },
      { name: 'NVIDIA RTX 4080', price: 85000, brand: 'NVIDIA', compatible: true },
      { name: 'AMD RX 7800 XT', price: 50000, brand: 'AMD', compatible: true },
    ],
  };

  const build = selectedBuild || {
    id: 1,
    title: 'Custom Build',
    price: 125000,
    parts: [
      { name: 'CPU', value: 'AMD Ryzen 7 5800X', price: 25000 },
      { name: 'GPU', value: 'NVIDIA RTX 4070', price: 55000 },
      { name: 'Motherboard', value: 'ASUS B550-F', price: 15000 },
      { name: 'RAM', value: '32GB DDR4 3200MHz', price: 12000 },
      { name: 'Storage', value: '1TB NVMe SSD', price: 8000 },
      { name: 'PSU', value: '750W 80+ Gold', price: 7000 },
      { name: 'Case', value: 'Fractal Design Meshify C', price: 8000 },
    ],
  };

  /** Line PKR from parts; fill gaps from package total for catalog prebuilts */
  const partsForUi = useMemo(
    () => allocateMissingLinePricesFromPackage(build.parts || [], build.price),
    [build.parts, build.price]
  );

  const lineSubtotal = partsForUi.reduce((sum, part) => sum + Number(part.price || 0), 0);
  const totalPrice = lineSubtotal > 0 ? lineSubtotal : Number(build.price || 0);
  const assemblyFee = 5000;
  const shipping = 2000;
  const finalTotal = totalPrice + assemblyFee + shipping;

  const query = new URLSearchParams(location.search).get('q') || '';
  const normalizedQuery = query.trim().toLowerCase();

  // Map DB component categories to configurator "part keys"
  // (DB: Processor/RAM/GPU/Motherboard/Storage/PSU/Cabinet)
  // (UI: CPU/RAM/GPU/Motherboard/Storage/PSU/Case)
  const categoryToPartKey = {
    Processor: 'CPU',
    RAM: 'RAM',
    GPU: 'GPU',
    Motherboard: 'Motherboard',
    Storage: 'Storage',
    PSU: 'PSU',
    Cabinet: 'Case',
  };

  const mapCategoryToPart = (categoryName) => categoryToPartKey[categoryName] || '';

  const [dbComponents, setDbComponents] = useState([]);
  const [dbLoading, setDbLoading] = useState(false);
  const [dbError, setDbError] = useState('');

  // If user searches from header, auto-select the first part category that matches.
  useEffect(() => {
    if (!normalizedQuery) return;
    if (selectedPart) return;

    const categories = Object.keys(compatibleParts);
    for (const cat of categories) {
      const matches = compatibleParts[cat]?.some((p) => {
        const name = (p.name || '').toLowerCase();
        const brand = (p.brand || '').toLowerCase();
        return name.includes(normalizedQuery) || brand.includes(normalizedQuery);
      });
      if (matches) {
        setSelectedPart(cat);
        break;
      }
    }
  }, [normalizedQuery, selectedPart]);

  useEffect(() => {
    // Load DB components only when user has a search query.
    if (!normalizedQuery) {
      setDbComponents([]);
      setDbError('');
      return;
    }

    const controller = new AbortController();
    const load = async () => {
      setDbLoading(true);
      setDbError('');
      try {
        const base = getFlaskBase() || getFlaskBaseFallback();
        if (!base) throw new Error('Flask base URL not configured.');

        const url = `${base}/api/components/search?q=${encodeURIComponent(query.trim())}&limit=50`;
        const res = await fetch(url, {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
        });
        const data = await res.json();
        if (!res.ok || !data?.success) {
          throw new Error(data?.error || data?.message || 'Failed to load components');
        }
        setDbComponents(Array.isArray(data.components) ? data.components : []);
      } catch (e) {
        if (e?.name === 'AbortError') return;
        setDbError(e?.message || 'Failed to load components');
        setDbComponents([]);
      } finally {
        setDbLoading(false);
      }
    };

    load();
    return () => controller.abort();
  }, [normalizedQuery, query]);

  const handleSwapPart = (newPart) => {
    const updatedParts = build.parts.map(p =>
      p.name === selectedPart ? { ...p, value: newPart.name, price: newPart.price } : p
    );
    setSelectedBuild({ ...build, parts: updatedParts });
    setSelectedPart(null);
  };

  const handleSwapDbComponent = (componentOption) => {
    const partKey = mapCategoryToPart(componentOption.category);
    if (!partKey) return;
    const updatedParts = build.parts.map((p) =>
      p.name === partKey ? { ...p, value: componentOption.name, price: componentOption.price } : p
    );
    setSelectedBuild({ ...build, parts: updatedParts });
    setSelectedPart(null);
  };

  const handleSuggestVendors = async (componentOption) => {
    if (!componentOption?.id) return;
    try {
      const res = await dashboardGet(`/components/${componentOption.id}/vendors`);
      const list = Array.isArray(res?.vendors) ? res.vendors : [];
      setVendorSuggestions((prev) => ({
        ...prev,
        [componentOption.id]: list,
      }));
    } catch (_) {
      setVendorSuggestions((prev) => ({
        ...prev,
        [componentOption.id]: [],
      }));
    }
  };

  const handleAddComponentToCart = async (componentOption, vendorId = null) => {
    if (!componentOption?.id) return;
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
  };

  const dbOptions = dbComponents.map((c) => ({
    id: c.id,
    name: c.name,
    brand: c.brand || '',
    price: Number(c.price || 0),
    category: c.category || '',
    stock: Number(c.stock || 0),
    description: c.description,
  }));

  const dbOptionsForSelectedPart = selectedPart
    ? dbOptions.filter((o) => mapCategoryToPart(o.category) === selectedPart)
    : dbOptions;

  const optionsForDisplay = normalizedQuery
    ? dbOptionsForSelectedPart.length > 0
      ? dbOptionsForSelectedPart
      : dbOptions
    : (compatibleParts[selectedPart] || []);

  const showCompatibilityPanel = Boolean(selectedPart) || Boolean(normalizedQuery);

  return (
    <div className="configurator-page">
      <div className="container">
        <header className="config-page-header">
          <div className="config-page-header-main">
            <p className="config-page-eyebrow">Configure</p>
            <h1 className="config-page-title">Build configurator</h1>
            <p className="config-page-lede">
              Review your parts, confirm compatibility and pricing, then pick vendors for assembly.
            </p>
            <div className="config-build-chip" title="Current build">
              <span className="config-build-chip-label">Build</span>
              <span className="config-build-chip-name">{build.title}</span>
            </div>
          </div>
          <button
            type="button"
            className="config-back-btn"
            onClick={() => navigate('/builds')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
            <span>Back to Prebuilt PCs</span>
          </button>
        </header>

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
            <div className="compatibility-status" role="status" aria-label="Quick compatibility checks">
              <span className="compat-inline-badge">Compatible</span>
              <span className="compat-inline-sep" aria-hidden>
                ·
              </span>
              <span className="compat-inline-badge">Power OK</span>
            </div>

            <div className="price-breakdown">
              <h3 className="price-breakdown-title">Price estimate</h3>
              <div className="price-item">
                <span className="price-item-label">Parts subtotal</span>
                <span className="price-item-value">PKR {totalPrice.toLocaleString()}</span>
              </div>
              <div className="price-item">
                <span className="price-item-label">Assembly</span>
                <span className="price-item-value">PKR {assemblyFee.toLocaleString()}</span>
              </div>
              <div className="price-item">
                <span className="price-item-label">Shipping (est.)</span>
                <span className="price-item-value">PKR {shipping.toLocaleString()}</span>
              </div>
              <div className="price-item total">
                <span className="price-item-label">Estimated total</span>
                <span className="price-item-value">PKR {finalTotal.toLocaleString()}</span>
              </div>
            </div>

            <button
              type="button"
              className="btn btn-primary btn-lg config-cta-primary"
              onClick={() => navigate('/vendor-assignment')}
            >
              Choose your vendor and continue
            </button>
          </section>

          <section className="filters-panel config-panel" aria-labelledby="build-components-heading">
            <div className="config-build-components">
              <h2 id="build-components-heading" className="config-build-components-title">
                Configured components
              </h2>
              <p className="config-build-components-lede">
                Parts in your current build{selectedBuild ? '' : ' (sample)'}.
              </p>
              <ul className="config-build-components-list">
                {partsForUi.map((p) => (
                  <li key={p.name} className="config-build-component-row">
                    <span className="config-build-component-slot">{p.name}</span>
                    <span className="config-build-component-value">{p.value || '—'}</span>
                    {Number(p.price) > 0 && Number.isFinite(Number(p.price)) ? (
                      <span className="config-build-component-price">PKR {Number(p.price).toLocaleString()}</span>
                    ) : (
                      <span className="config-build-component-price config-build-component-price--pending">—</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>

            {showCompatibilityPanel && (
              <div className="compatible-parts">
                <h3>
                  {normalizedQuery ? `Search Results` : `Compatible ${selectedPart}s`}
                </h3>

                {normalizedQuery && dbLoading && <div className="no-results">Loading components…</div>}
                {normalizedQuery && !dbLoading && dbError && (
                  <div className="no-results" role="alert">
                    {dbError}
                  </div>
                )}

                {!dbLoading && (
                  <div className="parts-options">
                    {optionsForDisplay.length === 0 ? (
                      <div className="no-results" role="status">
                        No matching components found{normalizedQuery ? ` for “${query.trim()}”` : ''}.
                      </div>
                    ) : (
                      optionsForDisplay.map((opt, idx) => (
                        <div
                          key={opt.id || idx}
                          className="part-option"
                          onClick={() =>
                            normalizedQuery ? handleSwapDbComponent(opt) : handleSwapPart(opt)
                          }
                        >
                          <div className="option-name">{opt.name}</div>
                          <div className="option-brand">{opt.brand}</div>
                          <div className="option-price">PKR {Number(opt.price || 0).toLocaleString()}</div>
                          {opt.stock !== undefined && normalizedQuery && (
                            <div className="option-warning">{opt.stock > 0 ? `In stock: ${opt.stock}` : 'Out of stock'}</div>
                          )}
                          {normalizedQuery && opt.id ? (
                            <>
                              <button
                                type="button"
                                className="btn btn-secondary add-component-btn"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleSuggestVendors(opt);
                                }}
                              >
                                Suggest Available Vendors
                              </button>
                              <button
                                type="button"
                                className="btn btn-primary add-component-btn"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleAddComponentToCart(opt);
                                }}
                                disabled={Number(opt.stock || 0) <= 0}
                              >
                                {Number(opt.stock || 0) <= 0 ? 'Out of Stock' : 'Add Component to Cart'}
                              </button>
                              {Array.isArray(vendorSuggestions[opt.id]) && (
                                <div className="vendor-suggestions-list">
                                  {vendorSuggestions[opt.id].length === 0 ? (
                                    <div className="vendor-suggestion-empty">No approved vendor currently has this component.</div>
                                  ) : (
                                    vendorSuggestions[opt.id].map((v) => (
                                      <div key={v.id} className="vendor-suggestion-item">
                                        <div className="vendor-suggestion-main">
                                          <span className="vendor-shop">{v.shop_name}</span>
                                          <span className="vendor-meta">{v.city || 'N/A'} {v.phone ? `• ${v.phone}` : ''}</span>
                                        </div>
                                        <span className="vendor-stock">Stock: {v.available_quantity}</span>
                                        <button
                                          type="button"
                                          className="btn btn-secondary btn-sm"
                                          style={{ marginTop: 6 }}
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            handleAddComponentToCart(opt, v.id);
                                          }}
                                        >
                                          Add from this vendor
                                        </button>
                                      </div>
                                    ))
                                  )}
                                </div>
                              )}
                            </>
                          ) : null}
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
};

export default BuildConfigurator;







