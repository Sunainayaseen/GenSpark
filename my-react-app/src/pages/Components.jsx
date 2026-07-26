import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getFlaskBase, getFlaskBaseFallback } from '../utils/flaskBase';
import { dashboardGet } from '../api/dashboardApi';
import { useCart } from '../context/CartContext';
import {
  getComponentPlaceholderKind,
  getComponentImageCandidates,
  getDisplayCategory,
  isLocalComponentPhotoUrl,
} from '../utils/componentImage';
import { COMPONENT_HERO_PHOTOS } from '../utils/componentLocalPhotos';
import ComponentMediaPlaceholder from './ComponentMediaPlaceholder';
import './Components.css';

const LIST_LIMIT = 120;

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

const ComponentCard = memo(function ComponentCard({
  c,
  hasVendor,
  vendorCount,
  apiBase,
  onAdd,
}) {
  const kind = useMemo(
    () => getComponentPlaceholderKind(c.category, c.name),
    [c.category, c.name]
  );
  // Deliberately narrower than `c` as a whole: `c` is a fresh object reference on
  // every parent render (mapped from the fetched list), so memoizing on the
  // specific fields this actually reads avoids recomputing candidates for
  // unrelated field changes.
  const candidates = useMemo(
    () => getComponentImageCandidates(c, apiBase),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- narrower than `c` on purpose, see comment above
    [c.id, c.image_url, c.category, c.name, apiBase]
  );

  const [imgFailIdx, setImgFailIdx] = useState(0);
  const [imgLoaded, setImgLoaded] = useState(false);

  // Resets the image-fallback index when the underlying component (c.id) or its
  // resolved image candidates change; equivalent to a key-reset but this card is
  // reused across a list without per-item remounting.
  const candidatesKey = candidates.join('|');
  useEffect(() => {
    setImgFailIdx(0);
    setImgLoaded(false);
  }, [c.id, candidatesKey]);

  const activeSrc = candidates[imgFailIdx] ?? null;
  const showRaster = imgFailIdx < candidates.length && activeSrc;
  const isSvg = activeSrc?.includes('.svg');
  const isProductPhoto = isLocalComponentPhotoUrl(activeSrc);

  return (
    <li className="components-card">
      <div className="components-card-media">
        <span className="components-card-category">
          {getDisplayCategory(c.category, c.name)}
        </span>
        <div
          className={`components-card-media-stage ${imgLoaded ? 'is-loaded' : ''} ${isSvg ? 'is-svg' : ''} ${isProductPhoto ? 'is-product-photo' : ''}`}
        >
          {showRaster ? (
            <>
              {!isSvg ? (
                <img
                  className="components-card-img-bg"
                  src={activeSrc}
                  alt=""
                  aria-hidden="true"
                  loading="lazy"
                  decoding="async"
                />
              ) : null}
              <img
                className={`components-card-img ${isSvg ? 'components-card-img--svg' : ''}`}
                src={activeSrc}
                alt={c.name || 'Component'}
                loading="lazy"
                decoding="async"
                onLoad={() => setImgLoaded(true)}
                onError={() => {
                  setImgLoaded(false);
                  setImgFailIdx((i) => i + 1);
                }}
              />
              {!imgLoaded ? <div className="components-card-img-shimmer" aria-hidden="true" /> : null}
            </>
          ) : (
            <div className="components-card-placeholder-wrap">
              <ComponentMediaPlaceholder kind={kind} />
            </div>
          )}
        </div>
      </div>
      <div className="components-card-body">
        <h2 className="components-card-title">{c.name}</h2>
        {c.brand ? <p className="components-card-meta">{c.brand}</p> : null}
        {c.description && <p className="components-card-desc">{c.description}</p>}
        <div className="components-card-price-row">
          <div className="components-card-price-block">
            <span className="components-card-price-label">Price</span>
            <span className="components-card-price">
              PKR {Number(c.price || 0).toLocaleString('en-US')}
            </span>
          </div>
          <span className="components-card-stock">
            Catalog stock: <strong>{c.stock ?? 0}</strong>
          </span>
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
            <svg
              className="components-add-btn-icon"
              width="17"
              height="17"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <circle cx="9" cy="21" r="1" />
              <circle cx="20" cy="21" r="1" />
              <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
            </svg>
            {hasVendor ? 'Add to cart' : 'Unavailable'}
          </button>
        </div>
      </div>
    </li>
  );
});

export default function Components() {
  const { addToCart } = useCart();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [categoryMenuOpen, setCategoryMenuOpen] = useState(false);
  const searchInputRef = useRef(null);
  const categorySelectRef = useRef(null);

  useEffect(() => {
    if (!categoryMenuOpen) return undefined;
    const handlePointerDown = (e) => {
      if (categorySelectRef.current && !categorySelectRef.current.contains(e.target)) {
        setCategoryMenuOpen(false);
      }
    };
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') setCategoryMenuOpen(false);
    };
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [categoryMenuOpen]);

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
          'Backend server is not reachable. Run START-GENSPARK-DEV.bat, then open http://localhost:5173/components'
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

  const handleAdd = useCallback(
    async (c) => {
      await addToCart(
        {
          id: c.id,
          item_type: 'component',
          name: c.name,
        },
        1
      );
    },
    [addToCart]
  );

  return (
    <div className="components-page">
      <div className="container components-page-inner">
        <header className="components-hero">
          <div className="components-hero-grid">
            <div className="components-hero-copy">
              <p className="components-hero-eyebrow">Parts catalog</p>
              <h1>Components</h1>
              <p className="components-hero-lead">
                Browse Dell, HP, and Lenovo parts with real product photos. Add to cart when an
                approved vendor has stock.
              </p>
              <ul className="components-hero-stats" aria-label="Catalog highlights">
                <li>
                  <strong>{loading ? '—' : items.length}</strong>
                  <span>Listed parts</span>
                </li>
                <li>
                  <strong>{categories.length || '—'}</strong>
                  <span>Categories</span>
                </li>
                <li>
                  <strong>PKR</strong>
                  <span>Local pricing</span>
                </li>
              </ul>
            </div>
            <div className="components-hero-visual" aria-hidden="true">
              <div className="components-hero-collage">
                {COMPONENT_HERO_PHOTOS.map((src, i) => (
                  <div
                    key={src}
                    className={`components-hero-thumb components-hero-thumb--${i + 1}`}
                  >
                    <img src={src} alt="" loading="eager" decoding="async" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </header>

        <div className="components-toolbar-panel">
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
          <div className="components-filter-label" ref={categorySelectRef}>
            <span className="components-filter-label-text">Category</span>
            <div className="components-select">
              <button
                type="button"
                className={`components-select-trigger ${categoryMenuOpen ? 'is-open' : ''}`}
                onClick={() => setCategoryMenuOpen((open) => !open)}
                onKeyDown={(e) => {
                  if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setCategoryMenuOpen(true);
                  }
                }}
                aria-haspopup="listbox"
                aria-expanded={categoryMenuOpen}
                aria-label="Filter by category"
              >
                <span className="components-select-value">{categoryFilter || 'All categories'}</span>
                <svg
                  className="components-select-chevron"
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  aria-hidden="true"
                >
                  <path d="m6 9 6 6 6-6" />
                </svg>
              </button>
              {categoryMenuOpen && (
                <ul className="components-select-menu" role="listbox" aria-label="Category">
                  <li
                    role="option"
                    aria-selected={categoryFilter === ''}
                    className={`components-select-option ${categoryFilter === '' ? 'is-selected' : ''}`}
                    onClick={() => {
                      setCategoryFilter('');
                      setCategoryMenuOpen(false);
                    }}
                  >
                    All categories
                  </li>
                  {categories.map((cat) => (
                    <li
                      key={cat}
                      role="option"
                      aria-selected={categoryFilter === cat}
                      className={`components-select-option ${categoryFilter === cat ? 'is-selected' : ''}`}
                      onClick={() => {
                        setCategoryFilter(cat);
                        setCategoryMenuOpen(false);
                      }}
                    >
                      {cat}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
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

        {!loading && categories.length > 0 && (
          <div className="components-chips" role="group" aria-label="Filter by category">
            <button
              type="button"
              className={`components-chip ${categoryFilter === '' ? 'is-active' : ''}`}
              aria-pressed={categoryFilter === ''}
              onClick={() => setCategoryFilter('')}
            >
              All categories
            </button>
            {categories.map((cat) => (
              <button
                key={cat}
                type="button"
                className={`components-chip ${categoryFilter === cat ? 'is-active' : ''}`}
                aria-pressed={categoryFilter === cat}
                onClick={() =>
                  setCategoryFilter((cur) => (cur === cat ? '' : cat))
                }
              >
                {cat}
              </button>
            ))}
          </div>
        )}
        </div>

        {error && (
          <div className="components-banner components-banner--error" role="alert">
            {error}
          </div>
        )}

        {loading && (
          <ul className="components-grid components-grid--skeleton" aria-hidden="true">
            {Array.from({ length: 8 }, (_, i) => (
              <li key={i} className="components-card components-card--skeleton">
                <div className="components-skeleton-media" />
                <div className="components-skeleton-body">
                  <div className="components-skeleton-line components-skeleton-line--lg" />
                  <div className="components-skeleton-line" />
                  <div className="components-skeleton-line components-skeleton-line--short" />
                </div>
              </li>
            ))}
          </ul>
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

        {!loading && !error && filtered.length > 0 && (
          <div className="components-grid-header">
            <h2 className="components-grid-title">Catalog</h2>
            <p className="components-grid-sub">
              {hasActiveFilters
                ? `${filtered.length} matching parts`
                : `${filtered.length} parts available`}
            </p>
          </div>
        )}

        {!loading && (
        <ul className="components-grid">
          {filtered.map((c) => {
            const hasVendor =
              c.has_vendor_stock === true ||
              (c.vendors_with_stock != null && c.vendors_with_stock > 0);
            const vendorCount = c.vendors_with_stock ?? (hasVendor ? 1 : 0);

            return (
              <ComponentCard
                key={c.id}
                c={c}
                hasVendor={hasVendor}
                vendorCount={vendorCount}
                apiBase={apiBase}
                onAdd={handleAdd}
              />
            );
          })}
        </ul>
        )}
      </div>
    </div>
  );
}
