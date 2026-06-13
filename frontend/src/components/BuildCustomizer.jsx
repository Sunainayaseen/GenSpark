import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { getBuildOptions, postEvaluateCustomization } from '../api/builderApi';
import { formatPkr } from '../utils/parseBuildRecommendation';
import './BuildCustomizer.css';

// Slots the user may edit directly. Dropdowns only list parts compatible with the
// rest of the build (hard-incompatible ones are filtered out server-side).
const EDITABLE_SLOTS = [
  { key: 'cpu', label: 'CPU' },
  { key: 'gpu', label: 'GPU' },
  { key: 'motherboard', label: 'Motherboard' },
  { key: 'ram', label: 'RAM' },
  { key: 'storage', label: 'Storage' },
  { key: 'psu', label: 'PSU' },
];

const LEVEL_CLASS = {
  fully_compatible: 'is-ok',
  unnecessary: 'is-warn',
  needs_adjustments: 'is-adjust',
  incompatible: 'is-bad',
};
// Marker shown before each dropdown option so the user sees compatibility at a glance.
const STATUS_MARK = { ok: '✓', adjust: '⚠', incompatible: '✗' };
// Slots shown read-only (engine auto-manages them).
const READONLY_SLOTS = [{ key: 'case', label: 'Case' }];

function currentId(row) {
  return row?.component_id ?? row?.id ?? null;
}

const STATUS_SUB = { ok: 'Compatible', adjust: '', incompatible: '' };

/**
 * Custom, fully-styled dropdown (native <select> can't style its open list). Rendered
 * via a portal so it never clips inside the scrolling chat. Each option shows a
 * coloured ✓/⚠/✗, the part name, a compatibility note, and the price.
 */
function ComponentSelect({ options, value, disabled, onPick }) {
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState(null);
  const btnRef = useRef(null);
  const listRef = useRef(null);
  const current = options.find((o) => o.id === value) || null;

  useEffect(() => {
    if (!open) return undefined;
    if (btnRef.current) setRect(btnRef.current.getBoundingClientRect());
    const onDown = (e) => {
      if (btnRef.current?.contains(e.target) || listRef.current?.contains(e.target)) return;
      setOpen(false);
    };
    const close = () => setOpen(false);
    document.addEventListener('mousedown', onDown);
    window.addEventListener('resize', close);
    window.addEventListener('scroll', close, true);
    return () => {
      document.removeEventListener('mousedown', onDown);
      window.removeEventListener('resize', close);
      window.removeEventListener('scroll', close, true);
    };
  }, [open]);

  return (
    <div className="bc-sel">
      <button ref={btnRef} type="button" className={`bc-sel-btn ${open ? 'is-open' : ''}`}
        disabled={disabled} onClick={() => setOpen((o) => !o)}>
        <span className={`bc-sel-mark m-${current?.status || 'ok'}`}>
          {current ? STATUS_MARK[current.status] : ''}
        </span>
        <span className="bc-sel-name">{current ? current.name : '— none —'}</span>
        <span className="bc-sel-caret" aria-hidden />
      </button>
      {open && rect
        ? createPortal(
          <ul ref={listRef} className="bc-sel-list" role="listbox"
            style={{ position: 'fixed', left: rect.left, top: rect.bottom + 4, width: rect.width }}>
            {options.map((o) => (
              <li key={o.id} role="option" aria-selected={o.id === value}
                className={`bc-sel-opt status-${o.status} ${o.id === value ? 'is-current' : ''}`}
                onClick={() => { setOpen(false); if (o.id !== value) onPick(o); }}>
                <span className={`bc-sel-mark m-${o.status}`}>{STATUS_MARK[o.status]}</span>
                <span className="bc-sel-opt-text">
                  <span className="bc-sel-opt-name">{o.name}</span>
                  <span className="bc-sel-opt-sub">
                    {(o.id === value ? 'Current selection' : (STATUS_SUB[o.status] || o.note))} · {formatPkr(o.price)}
                  </span>
                </span>
              </li>
            ))}
          </ul>,
          document.body,
        )
        : null}
    </div>
  );
}

/**
 * In-chat build editor: each component row has an inline dropdown of compatible
 * parts. Changing one runs the rule engine (4-level verdict) and Apply swaps it
 * (PSU auto) into the live build, which flows to the cart. Plus rule-based
 * upgrade suggestions.
 */
export default function BuildCustomizer({ buildComponents, purpose, budget, onApply, onAddToCart, adding = false }) {
  const [options, setOptions] = useState(null);
  const [mode, setMode] = useState('beginner');
  const [verdict, setVerdict] = useState(null); // { slot, card, data }
  const [busySlot, setBusySlot] = useState(null);
  const [error, setError] = useState(null);
  const [applied, setApplied] = useState(null);

  const bySlot = useMemo(() => {
    const m = {};
    (buildComponents || []).forEach((r) => {
      const k = (r.slot || '').toLowerCase();
      if (k) m[k] = r;
    });
    return m;
  }, [buildComponents]);

  const buildIdMap = useMemo(() => {
    const m = {};
    Object.entries(bySlot).forEach(([k, r]) => {
      const id = currentId(r);
      if (id) m[k] = id;
    });
    return m;
  }, [bySlot]);

  const liveTotal = (buildComponents || []).reduce((s, r) => s + (Number(r.price) || 0), 0);

  // Refetch options only when the platform board changes (normally never mid-session).
  const boardId = currentId(bySlot.motherboard);
  useEffect(() => {
    let live = true;
    getBuildOptions(buildIdMap)
      .then((o) => live && setOptions(o))
      .catch((e) => live && setError(String(e.message || e)));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [boardId]);

  // Clear a stale verdict when the underlying build changes (e.g. after Apply).
  useEffect(() => { setVerdict(null); }, [buildComponents]);

  async function evaluate(slot, card) {
    setError(null);
    setApplied(null);
    if (!card || card.id === currentId(bySlot[slot])) { setVerdict(null); return; }
    setBusySlot(slot);
    try {
      const data = await postEvaluateCustomization({
        purpose: purpose || undefined,
        budget: budget ? String(budget) : undefined,
        build: buildIdMap,
        change: { slot, component_id: card.id },
        mode,
      });
      setVerdict({ slot, card, data });
    } catch (e) {
      setError(String(e.message || e));
      setVerdict(null);
    } finally {
      setBusySlot(null);
    }
  }

  function handleApply() {
    if (!verdict || verdict.data.level === 'incompatible') return;
    const { slot, card, data } = verdict;
    const rows = [...(buildComponents || [])];
    const upsert = (slotKey, patch) => {
      const idx = rows.findIndex((r) => (r.slot || '').toLowerCase() === slotKey);
      if (idx >= 0) rows[idx] = { ...rows[idx], ...patch };
      else rows.push({ slot: slotKey, label: slotKey.toUpperCase(), ...patch });
    };
    upsert(slot, { component_id: card.id, name: card.name, price: card.price });
    (data.dependent_changes || []).forEach((dep) => {
      const dk = (dep.slot || '').toLowerCase();
      const idx = rows.findIndex((r) => (r.slot || '').toLowerCase() === dk);
      const curPrice = idx >= 0 ? Number(rows[idx].price) || 0 : 0;
      upsert(dk, { component_id: dep.to_id, name: dep.to, price: curPrice + (Number(dep.price_delta) || 0) });
    });
    const newTotal = rows.reduce((s, r) => s + (Number(r.price) || 0), 0);
    onApply?.(rows);
    setApplied(`${slot.toUpperCase()} updated → ${card.name}. Build total now ${formatPkr(newTotal)}.`);
    setVerdict(null);
  }

  if (error && !options) {
    return (
      <div className="build-customizer build-customizer--error">
        Couldn’t load customization options. {error}
      </div>
    );
  }

  const v = verdict?.data;
  const explanation = v ? v.explanations?.[mode] || v.explanation : '';

  // Show a row for every editable slot that has options (or is already in the build).
  const rows = EDITABLE_SLOTS.filter((s) => (options?.[s.key]?.length) || bySlot[s.key]);

  return (
    <section className="build-customizer" aria-label="Customize this build">
      <div className="build-customizer-head">
        <div>
          <h4 className="build-customizer-title">Recommended components</h4>
          <span className="build-customizer-livetotal">
            Tap a dropdown to customize · Build total: <strong>{formatPkr(liveTotal)}</strong>
          </span>
        </div>
        <div className="build-customizer-mode" role="group" aria-label="Explanation detail">
          <button type="button" className={mode === 'beginner' ? 'is-active' : ''} onClick={() => setMode('beginner')}>Beginner</button>
          <button type="button" className={mode === 'advanced' ? 'is-active' : ''} onClick={() => setMode('advanced')}>Advanced</button>
        </div>
      </div>

      {/* Inline dropdown build editor */}
      {!options ? (
        <p className="build-customizer-busy">Loading components…</p>
      ) : (
        <div className="bc-editor">
          {rows.map(({ key, label }) => {
            const cur = bySlot[key];
            const opts = options[key] || [];
            const pending = verdict?.slot === key ? verdict.card : null;
            const selId = (pending?.id) ?? currentId(cur) ?? '';
            const shownPrice = pending ? pending.price : cur?.price;
            return (
              <div className={`bc-row ${pending ? 'is-pending' : ''}`} key={key}>
                <span className="bc-row-label">{label}</span>
                <div className="bc-row-select-wrap">
                  <ComponentSelect
                    options={opts}
                    value={selId || null}
                    disabled={busySlot === key || !opts.length}
                    onPick={(card) => evaluate(key, card)}
                  />
                  {busySlot === key ? <span className="bc-row-spin" aria-hidden /> : null}
                </div>
                <span className={`bc-row-price ${pending ? 'is-pending' : ''}`}>
                  {shownPrice != null ? formatPkr(shownPrice) : '—'}
                </span>
              </div>
            );
          })}

          {/* Read-only, engine-managed slots (e.g. Case) */}
          {READONLY_SLOTS.filter((s) => bySlot[s.key]).map(({ key, label }) => (
            <div className="bc-row bc-row--readonly" key={key}>
              <span className="bc-row-label">{label}</span>
              <span className="bc-row-static">{bySlot[key].name} <em>(auto)</em></span>
              <span className="bc-row-price">{formatPkr(bySlot[key].price)}</span>
            </div>
          ))}
        </div>
      )}

      {error && options ? <p className="build-customizer-err">{error}</p> : null}
      {applied ? <p className="build-customizer-applied">✓ {applied}</p> : null}

      {/* Verdict for the pending change */}
      {v ? (
        <div className={`build-customizer-verdict ${LEVEL_CLASS[v.level] || ''}`}>
          <div className="build-customizer-verdict-head">
            <span className="build-customizer-level">{v.status_label}</span>
            <span className="build-customizer-perf">Performance: {v.performance_impact}</span>
          </div>
          <p className="build-customizer-explain">{explanation}</p>
          {v.dependent_changes?.length ? (
            <ul className="build-customizer-deps">
              {v.dependent_changes.map((d, i) => (
                <li key={i}>
                  <strong>{d.slot}</strong>: {d.from || '—'} → {d.to}{' '}
                  <em>({d.auto_apply ? 'auto' : 'recommended'})</em>{' '}
                  {d.price_delta >= 0 ? '+' : '−'}{formatPkr(Math.abs(d.price_delta))}
                </li>
              ))}
            </ul>
          ) : null}
          <div className="build-customizer-budget">
            <span>Total {formatPkr(v.budget.old_total)} → <strong>{formatPkr(v.budget.new_total)}</strong></span>
            <span className={v.budget.delta >= 0 ? 'delta-up' : 'delta-down'}>
              {v.budget.delta >= 0 ? '+' : '−'}{formatPkr(Math.abs(v.budget.delta))}
            </span>
            {!v.budget.within_budget ? <span className="build-customizer-overbudget">over budget</span> : null}
          </div>
          <div className="build-customizer-actions">
            <button type="button" className="build-customizer-apply" onClick={handleApply} disabled={v.level === 'incompatible'}>
              {v.level === 'incompatible' ? 'Incompatible — Can’t Apply'
                : v.level === 'needs_adjustments' ? 'Apply & Auto-Upgrade'
                  : 'Confirm Changes'}
            </button>
            <button type="button" className="build-customizer-cancel" onClick={() => setVerdict(null)}>Keep Current Build</button>
          </div>
        </div>
      ) : null}

      {/* Add the (possibly customized) build to cart */}
      {onAddToCart ? (
        <button
          type="button"
          className="bc-cart-btn"
          disabled={adding || busySlot}
          onClick={() => onAddToCart(buildComponents)}
        >
          {adding ? (
            <span className="bc-cart-label">Adding to Cart…</span>
          ) : (
            <>
              <span className="bc-cart-label">Add Full Build to Cart</span>
              <span className="bc-cart-price">PKR {formatPkr(liveTotal)}</span>
            </>
          )}
        </button>
      ) : null}
    </section>
  );
}
