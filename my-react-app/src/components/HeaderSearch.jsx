import { useState, useRef, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { getApiUrl, getFlaskBase, getFlaskBaseFallback } from '../utils/flaskBase';
import { getAuthHeaders } from '../utils/authStorage';

/**
 * Same component search UI as the site header (icon → pill → live results → configurator).
 * Styles: Layout.css (.header-search-*).
 */
export default function HeaderSearch({ onAfterNavigate }) {
  const location = useLocation();
  const navigate = useNavigate();
  const searchBlurTimer = useRef(null);
  const searchWrapRef = useRef(null);
  const searchInputRef = useRef(null);

  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchLiveResults, setSearchLiveResults] = useState([]);
  const [searchLiveLoading, setSearchLiveLoading] = useState(false);
  const [searchLiveError, setSearchLiveError] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);

  const headerSearchQuery =
    location.pathname === '/configurator'
      ? new URLSearchParams(location.search).get('q') || ''
      : '';
  const [searchValue, setSearchValue] = useState('');

  useEffect(() => {
    if (location.pathname === '/configurator') setSearchValue(headerSearchQuery);
    else setSearchValue('');
  }, [location.pathname, headerSearchQuery]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        isSearchOpen &&
        searchWrapRef.current &&
        !searchWrapRef.current.contains(event.target)
      ) {
        setIsSearchOpen(false);
        setSearchFocused(false);
      }
    };
    if (isSearchOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isSearchOpen]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape' && isSearchOpen) {
        setIsSearchOpen(false);
        setSearchFocused(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isSearchOpen]);

  useEffect(() => {
    if (!isSearchOpen) return;
    const id = requestAnimationFrame(() => {
      searchInputRef.current?.focus();
    });
    return () => cancelAnimationFrame(id);
  }, [isSearchOpen]);

  const commitSearch = () => {
    const q = (searchValue || '').trim();
    if (!q) return;
    navigate(`/configurator?q=${encodeURIComponent(q)}`);
    setSearchFocused(false);
    setIsSearchOpen(false);
    onAfterNavigate?.();
  };

  const handleHeaderSearchSubmit = (e) => {
    e.preventDefault();
    commitSearch();
  };

  const LIVE_SEARCH_MIN = 2;
  const LIVE_SEARCH_LIMIT = 100;

  useEffect(() => {
    const q = (searchValue || '').trim();
    if (q.length < LIVE_SEARCH_MIN) {
      setSearchLiveResults([]);
      setSearchLiveLoading(false);
      setSearchLiveError('');
      return;
    }
    setSearchLiveLoading(true);
    setSearchLiveError('');
    const t = setTimeout(async () => {
      try {
        const res = await fetch(
          `${getApiUrl('/components/search')}?q=${encodeURIComponent(q)}&limit=${LIVE_SEARCH_LIMIT}`,
          { credentials: 'include', headers: getAuthHeaders() }
        );
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.success) {
          throw new Error(data.error || data.message || 'Search failed');
        }
        setSearchLiveResults(Array.isArray(data.components) ? data.components : []);
      } catch (err) {
        setSearchLiveError(err.message || 'Components load nahi ho sake.');
        setSearchLiveResults([]);
      } finally {
        setSearchLiveLoading(false);
      }
    }, 320);
    return () => clearTimeout(t);
  }, [searchValue]);

  const showLiveDropdown =
    isSearchOpen &&
    searchFocused &&
    (searchValue || '').trim().length >= LIVE_SEARCH_MIN;

  const handleSearchResultPick = (component) => {
    const name = (component?.name || '').trim();
    if (!name) return;
    if (searchBlurTimer.current) clearTimeout(searchBlurTimer.current);
    setSearchFocused(false);
    setSearchValue(name);
    navigate(`/configurator?q=${encodeURIComponent(name)}`);
    setIsSearchOpen(false);
    onAfterNavigate?.();
  };

  const searchIconSvg = (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-4-4" />
    </svg>
  );

  const renderSearchDropdown = () =>
    showLiveDropdown ? (
      <div className="header-search-dropdown" role="listbox" aria-label="Matching components">
        {searchLiveLoading && (
          <div className="header-search-dropdown-status">Loading…</div>
        )}
        {!searchLiveLoading && searchLiveError && (
          <div className="header-search-dropdown-status header-search-dropdown-error">{searchLiveError}</div>
        )}
        {!searchLiveLoading && !searchLiveError && searchLiveResults.length === 0 && (
          <div className="header-search-dropdown-status">Koi component match nahi hua.</div>
        )}
        {!searchLiveLoading &&
          !searchLiveError &&
          searchLiveResults.map((c) => (
            <button
              key={c.id}
              type="button"
              className="header-search-dropdown-item"
              role="option"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => handleSearchResultPick(c)}
            >
              <span className="header-search-dropdown-name">{c.name}</span>
              <span className="header-search-dropdown-meta">
                {[c.brand, c.category].filter(Boolean).join(' · ')}
                {c.price != null && ` · PKR ${Number(c.price).toLocaleString()}`}
              </span>
            </button>
          ))}
      </div>
    ) : null;

  useEffect(
    () => () => {
      if (searchBlurTimer.current) clearTimeout(searchBlurTimer.current);
    },
    []
  );

  return (
    <div className="header-search header-search-wrap" ref={searchWrapRef}>
      {!isSearchOpen ? (
        <button
          type="button"
          className="header-search-icon-btn"
          aria-label="Open component search"
          aria-expanded={isSearchOpen}
          onClick={() => {
            setIsSearchOpen(true);
          }}
        >
          {searchIconSvg}
        </button>
      ) : (
        <form
          className="header-search-form header-search-pill header-search-pill--light"
          onSubmit={handleHeaderSearchSubmit}
        >
          <input
            ref={searchInputRef}
            className="header-search-input"
            type="text"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            onFocus={() => {
              if (searchBlurTimer.current) clearTimeout(searchBlurTimer.current);
              setSearchFocused(true);
            }}
            onBlur={() => {
              searchBlurTimer.current = setTimeout(() => setSearchFocused(false), 200);
            }}
            placeholder="Search CPUs, GPUs, RAM…"
            aria-label="Search components"
            autoComplete="off"
          />
          <button
            type="button"
            className="header-search-submit-icon"
            aria-label={(searchValue || '').trim() ? 'Search' : 'Close search'}
            onClick={(e) => {
              e.preventDefault();
              const q = (searchValue || '').trim();
              if (q) {
                commitSearch();
              } else {
                setIsSearchOpen(false);
                setSearchFocused(false);
              }
            }}
          >
            {searchIconSvg}
          </button>
        </form>
      )}
      {renderSearchDropdown()}
    </div>
  );
}
