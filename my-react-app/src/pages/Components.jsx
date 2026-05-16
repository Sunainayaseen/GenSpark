import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getApiUrl, getFlaskBase, getFlaskBaseFallback } from '../utils/flaskBase';
import { dashboardGet } from '../api/dashboardApi';
import { useCart } from '../context/CartContext';
import {
  resolveComponentImageUrl,
  getComponentPlaceholderKind,
  getCategoryStockImagePath,
  getCategoryStockPhotoUrl,
} from '../utils/componentImage';
import ComponentMediaPlaceholder from './ComponentMediaPlaceholder';
import './Components.css';

const LIST_LIMIT = 500;

/** Lowercased blob of searchable fields for client-side filtering. */
function componentSearchBlob(c) {
  return [c.name, c.brand, c.category, c.description].filter(Boolean).join(' ').toLowerCase();
}

/** Every whitespace-separated token must appear somewhere (order-independent). */
function matchesSearchTokens(blob, rawQuery) {
  const tokens = rawQuery
    .toLowerCase()
    .split(/\s+/)
    .map((t) => t.trim())
    .filter(Boolean);
  if (tokens.length === 0) return true;
  return tokens.every((t) => blob.includes(t));
}

function ComponentCard({
  c,
  hasVendor,
  vendorCount,
  expanded,
  vd,
  vendorLoadingId,
  apiBase,
  onAdd,
  onVendors,
}) {
  const kind = useMemo(
    () => getComponentPlaceholderKind(c.category, c.name),
    [c.category, c.name]
  );
  const stockPath = useMemo(() => getCategoryStockImagePath(kind), [kind]);
  const stockPhotoUrl = useMemo(() => getCategoryStockPhotoUrl(kind), [kind]);
  const dbUrl = resolveComponentImageUrl(c.image_url, apiBase);

  const candidates = useMemo(() => {
    const list = [];
    if (dbUrl) list.push(dbUrl);
    list.push(stockPhotoUrl);
    list.push(stockPath);
    return [...new Set(list)];
  }, [dbUrl, stockPhotoUrl, stockPath]);

  const [imgFailIdx, setImgFailIdx] = useState(0);

  useEffect(() => {
    setImgFailIdx(0);
  }, [c.id, candidates.join('|')]);

  const activeSrc = candidates[imgFailIdx] ?? null;
  const showRaster = imgFailIdx < candidates.length && activeSrc;

  return (
    <li className="components-card">
      <div className="components-card-media">
        {showRaster ? (
          <img
            src={activeSrc}
            alt={c.name || 'Component'}
            loading="lazy"
            decoding="async"
            onError={() => setImgFailIdx((i) => i + 1)}
          />
        ) : (
          <div className="components-card-placeholder-wrap">
            <ComponentMediaPlaceholder kind={kind} />
            <span className="components-card-placeholder-label">{c.category || 'Part'}</span>
          </div>
        )}
      </div>
      <div className="components-card-body">
        <h2 className="components-card-title">{c.name}</h2>
        <p className="components-card-meta">
          {[c.brand, c.category].filter(Boolean).join(' · ') || '—'}
        </p>
        {c.description && <p className="components-card-desc">{c.description}</p>}
        <div className="components-card-price-row">
          <span className="components-card-price">
            PKR {Number(c.price || 0).toLocaleString()}
          </span>
          <span className="components-card-stock">Stock (catalog): {c.stock ?? 0}</span>
        </div>
        <div
          className={`components-vendor-pill ${
            hasVendor ? 'components-vendor-pill--ok' : 'components-vendor-pill--bad'
          }`}
        >
          {hasVendor
            ? `${vendorCount} vendor${vendorCount === 1 ? '' : 's'} with stock`
            : 'No approved vendor with stock'}
        </div>
        <div className="components-card-actions">
          <button
            type="button"
            className="btn btn-primary components-add-btn"
            disabled={!hasVendor}
            onClick={() => onAdd(c)}
            title={
              hasVendor
                ? 'Add to cart (vendor assigned automatically)'
                : 'No vendor has this part in stock yet'
            }
          >
            Add to cart
          </button>
          <button
            type="button"
            className="btn btn-secondary components-details-btn"
            onClick={() => onVendors(c.id)}
            disabled={vendorLoadingId === c.id}
          >
            {vendorLoadingId === c.id
              ? 'Loading…'
              : expanded
                ? 'Hide vendors'
                : 'Who has stock?'}
          </button>
        </div>
        {expanded && (
          <div className="components-vendor-list" role="region" aria-label="Vendors">
            {vd?.error && <p className="components-vendor-error">{vd.error}</p>}
            {Array.isArray(vd) && vd.length === 0 && !vd?.error && (
              <p>No vendors with stock for this part.</p>
            )}
            {Array.isArray(vd) &&
              vd.map((v) => (
                <div key={v.id} className="components-vendor-row">
                  <strong>{v.shop_name}</strong>
                  <span>
                    {v.city ? `${v.city} · ` : ''}
                    qty {v.available_quantity}
                    {v.vendor_price != null
                      ? ` · PKR ${Number(v.vendor_price).toLocaleString()}`
                      : ''}
                  </span>
                </div>
              ))}
          </div>
        )}
      </div>
    </li>
  );
}

export default function Components() {
  const { addToCart } = useCart();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [expandedId, setExpandedId] = useState(null);
  const [vendorDetails, setVendorDetails] = useState({});
  const [vendorLoadingId, setVendorLoadingId] = useState(null);
  const searchInputRef = useRef(null);

  const apiBase = useMemo(() => getFlaskBase() || getFlaskBaseFallback() || '', []);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await dashboardGet(
        `/components/search?limit=${LIST_LIMIT}&vendor_summary=1`
      );
      if (!data?.success) {
        throw new Error(data?.error || data?.message || 'Failed to load components');
      }
      setItems(Array.isArray(data.components) ? data.components : []);
    } catch (e) {
      const base = getFlaskBase() || getFlaskBaseFallback();
      if (!base) {
        setError(
          'Backend server is not reachable. Start the Flask app (e.g. port 5000) and ensure the Vite proxy is configured.'
        );
      } else {
        setError(e.message || 'Could not load components.');
      }
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const categories = useMemo(() => {
    const s = new Set();
    items.forEach((c) => {
      if (c.category) s.add(c.category);
    });
    return Array.from(s).sort();
  }, [items]);

  const filtered = useMemo(() => {
    const q = query.trim();
    return items.filter((c) => {
      if (categoryFilter && c.category !== categoryFilter) return false;
      if (!q) return true;
      return matchesSearchTokens(componentSearchBlob(c), q);
    });
  }, [items, query, categoryFilter]);

  const hasActiveFilters = Boolean(query.trim() || categoryFilter);

  const fetchVendorsFor = async (componentId) => {
    if (vendorDetails[componentId]) {
      setExpandedId((id) => (id === componentId ? null : componentId));
      return;
    }
    setVendorLoadingId(componentId);
    try {
      const res = await fetch(getApiUrl(`/components/${componentId}/vendors`), {
        credentials: 'include',
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Could not load vendors');
      }
      setVendorDetails((prev) => ({
        ...prev,
        [componentId]: Array.isArray(data.vendors) ? data.vendors : [],
      }));
      setExpandedId(componentId);
    } catch (e) {
      setVendorDetails((prev) => ({
        ...prev,
        [componentId]: { error: e.message || 'Failed' },
      }));
      setExpandedId(componentId);
    } finally {
      setVendorLoadingId(null);
    }
  };

  const handleAdd = async (c) => {
    await addToCart(
      {
        id: c.id,
        item_type: 'component',
        name: c.name,
      },
      1
    );
  };

  return (
    <div className="components-page">
      <div className="container">
        <header className="components-header">
          <h1>Components</h1>
          <p>
            Parts added by your admin appear here. Add to cart is fulfilled by an approved vendor who
            has stock; if no vendor carries a part yet, add to cart stays disabled.
          </p>
        </header>

        <div className="components-toolbar">
          <div className="components-search" role="search" aria-label="Catalog search">
            <label className="components-search-field" htmlFor="components-catalog-search">
              <span className="components-search-icon" aria-hidden="true">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.35-4.35" />
                </svg>
              </span>
              <span className="sr-only">Search catalog by name, brand, or category</span>
              <input
                ref={searchInputRef}
                id="components-catalog-search"
                type="search"
                className={`components-search-input ${query ? 'components-search-input--has-clear' : ''}`}
                placeholder="Search parts by name, brand, category…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                autoComplete="off"
                inputMode="search"
                enterKeyHint="search"
                aria-describedby="components-search-status"
                onKeyDown={(e) => {
                  if (e.key === 'Escape') {
                    setQuery('');
                    e.currentTarget.blur();
                  }
                }}
              />
              {query ? (
                <button
                  type="button"
                  className="components-search-clear"
                  aria-label="Clear search"
                  onClick={() => {
                    setQuery('');
                    searchInputRef.current?.focus();
                  }}
                >
                  <span aria-hidden="true">×</span>
                </button>
              ) : null}
            </label>
          </div>
          <label className="components-filter-label">
            Category
            <select
              className="components-filter-select"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              aria-label="Filter by category"
            >
              <option value="">All categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </label>
          <span
            id="components-search-status"
            className="components-count"
            aria-live="polite"
          >
            {loading
              ? 'Loading…'
              : hasActiveFilters
                ? `${filtered.length} of ${items.length} match`
                : `${items.length} part${items.length === 1 ? '' : 's'}`}
          </span>
        </div>

        {error && (
          <div className="components-banner components-banner--error" role="alert">
            {error}
          </div>
        )}

        {loading && (
          <div className="components-loading" role="status" aria-live="polite">
            <span className="loading-spinner" aria-hidden="true" />
            Loading inventory…
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <div className="components-empty">
            {items.length === 0 ? (
              <p>No components in the catalog yet.</p>
            ) : (
              <>
                <p>
                  No parts match
                  {hasActiveFilters ? ' your current search or category filter' : ' these filters'}.
                </p>
                {hasActiveFilters && (
                  <button
                    type="button"
                    className="btn btn-secondary components-empty-reset"
                    onClick={() => {
                      setQuery('');
                      setCategoryFilter('');
                      searchInputRef.current?.focus();
                    }}
                  >
                    {'Clear search & category'}
                  </button>
                )}
              </>
            )}
          </div>
        )}

        <ul className="components-grid">
          {filtered.map((c) => {
            const hasVendor =
              c.has_vendor_stock === true ||
              (c.vendors_with_stock != null && c.vendors_with_stock > 0);
            const vendorCount = c.vendors_with_stock ?? (hasVendor ? 1 : 0);
            const expanded = expandedId === c.id;
            const vd = vendorDetails[c.id];

            return (
              <ComponentCard
                key={c.id}
                c={c}
                hasVendor={hasVendor}
                vendorCount={vendorCount}
                expanded={expanded}
                vd={vd}
                vendorLoadingId={vendorLoadingId}
                apiBase={apiBase}
                onAdd={handleAdd}
                onVendors={fetchVendorsFor}
              />
            );
          })}
        </ul>
      </div>
    </div>
  );
}
