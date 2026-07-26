import { useState, useCallback, useMemo } from 'react';

import { useCart } from '../context/CartContext';
import { formatPKR } from '../utils/format';
import './ImageDetectOverlay.css';

const DISPLAY_CONFIRM_THRESHOLD_PCT = 45; // match backend + Chatbot (45)

const labelForDetection = (d) => {
  // Number(x) returns NaN (not null/undefined) for a missing confidence, so `??`
  // never actually falls back — use `||` so a missing/invalid value reads as 0
  // instead of rendering "NaN%" in the overlay badge.
  const conf = Math.min(Math.max(Number(d.confidence) || 0, 0), 100);
  if (d.type === 'UNKNOWN' || d.name === 'Unknown Component') {
    return { title: 'Unknown', sub: d.rawGuess ? `≈ ${d.rawGuess}` : '', pct: conf };
  }
  if (conf < DISPLAY_CONFIRM_THRESHOLD_PCT) {
    return { title: 'Unknown', sub: d.rawGuess ? `≈ ${d.rawGuess}` : '', pct: conf };
  }
  return { title: d.name || d.class_name || 'Component', sub: '', pct: conf };
};

const strokeForDetection = (d) => {
  const c = labelForDetection(d);
  if (c.title === 'Unknown') return '#f59e0b';
  const name = (d.class_name || '').toLowerCase();
  if (name === 'mouse') return '#22d3ee';
  if (name === 'keyboard') return '#a78bfa';
  if (name === 'monitor') return '#34d399';
  if (name === 'ram') return '#fb923c';
  return '#38bdf8';
};

/** xyxy from API (pixel space) or derive from normalized YOLO `box` + image size. */
const resolveXyxy = (d, nw, nh) => {
  if (Array.isArray(d.xyxy) && d.xyxy.length >= 4) {
    return d.xyxy.map((v) => Number(v));
  }
  const b = d.box;
  if (!b || !nw || !nh) return null;
  const xc = Number(b.xCenter);
  const yc = Number(b.yCenter);
  const bw = Number(b.width);
  const bh = Number(b.height);
  return [
    (xc - bw / 2) * nw,
    (yc - bh / 2) * nh,
    (xc + bw / 2) * nw,
    (yc + bh / 2) * nh,
  ];
};

const matchesOf = (d) => (Array.isArray(d?.matches) ? d.matches : []);

/**
 * Responsive image with SVG overlay in original pixel space (viewBox = natural image).
 * Boxes whose detection resolved to in-stock catalog components become clickable and
 * open a popover with name / price / Add to Cart.
 * Expects Flask `/api/detect/component` fields: xyxy, class_name, confidence (%),
 * optional image_width/height, and `matches` (in-stock components from the DB).
 */
export default function ImageDetectOverlay({
  src,
  detections = [],
  naturalWidth,
  naturalHeight,
  alt = 'Uploaded image',
}) {
  const [intrinsic, setIntrinsic] = useState({ w: naturalWidth || 0, h: naturalHeight || 0 });
  const [activeIndex, setActiveIndex] = useState(null);
  const [addingId, setAddingId] = useState(null);
  const [addedIds, setAddedIds] = useState(() => new Set());

  const { addToCart } = useCart();

  const onImgLoad = useCallback(
    (e) => {
      const { naturalWidth: w, naturalHeight: h } = e.currentTarget;
      if (!naturalWidth && w && h) setIntrinsic({ w, h });
    },
    [naturalWidth]
  );

  const nw = Number(naturalWidth || intrinsic.w) || 0;
  const nh = Number(naturalHeight || intrinsic.h) || 0;
  const hasOverlay = detections.length > 0 && nw > 0 && nh > 0;

  const activeDet = activeIndex != null ? detections[activeIndex] : null;
  const activeMatches = matchesOf(activeDet);

  // Position the popover relative to the active box (percentages map cleanly onto
  // the frame since the SVG viewBox == natural image size). Flip side/edge near borders.
  // activeDet is a plain array-index lookup (detections[activeIndex]), not an
  // independently memoized value, so the React Compiler declines to verify this
  // further — the plain useMemo below is correct as-is.
  const popStyle = useMemo(() => {
    if (!activeDet || !nw || !nh) return null;
    const xy = resolveXyxy(activeDet, nw, nh);
    if (!xy) return null;
    const [x1, y1, x2, y2] = xy;
    const anchorRight = x1 / nw > 0.55;
    const anchorTop = y2 / nh > 0.62;
    const style = {};
    if (anchorRight) style.right = `${Math.max(0, (1 - x2 / nw) * 100)}%`;
    else style.left = `${Math.max(0, (x1 / nw) * 100)}%`;
    if (anchorTop) style.bottom = `${Math.max(0, (1 - y1 / nh) * 100)}%`;
    else style.top = `${Math.min(98, (y2 / nh) * 100)}%`;
    return style;
  }, [activeDet, nw, nh]); // eslint-disable-line react-hooks/preserve-manual-memoization

  const handleAdd = async (m) => {
    if (!m?.id || addingId) return;
    setAddingId(m.id);
    const ok = await addToCart({ ...m, item_type: 'component' });
    setAddingId(null);
    if (ok) {
      setAddedIds((prev) => {
        const next = new Set(prev);
        next.add(m.id);
        return next;
      });
    }
  };

  return (
    <div className="image-detect-frame">
      <img src={src} alt={alt} className="image-detect-img" onLoad={onImgLoad} loading="lazy" />
      {hasOverlay && (
        <svg
          className="image-detect-svg"
          viewBox={`0 0 ${nw} ${nh}`}
          preserveAspectRatio="xMidYMid meet"
        >
          {detections.map((d, i) => {
            const xy = resolveXyxy(d, nw, nh);
            if (!xy) return null;
            const [x1, y1, x2, y2] = xy;
            const rw = Math.max(0, x2 - x1);
            const rh = Math.max(0, y2 - y1);
            const { title, sub, pct } = labelForDetection(d);
            const stroke = strokeForDetection(d);
            const matchCount = matchesOf(d).length;
            const clickable = matchCount > 0;
            const isActive = activeIndex === i;
            const chipY = Math.max(0, y1 - 22);
            const chipH = 20;
            const base = sub ? `${title} ${pct.toFixed(1)}% · ${sub}` : `${title} ${pct.toFixed(1)}%`;
            const line1 = clickable ? `${base} · ${matchCount} in stock ▸` : base;
            const chipW = Math.min(Math.max(0, nw - x1 - 4), clickable ? 280 : 240);

            return (
              <g
                key={`det-${i}`}
                style={{ cursor: clickable ? 'pointer' : 'default' }}
                onClick={clickable ? () => setActiveIndex(isActive ? null : i) : undefined}
              >
                {/* transparent hit area so the whole box is clickable, not just the stroke */}
                {clickable && (
                  <rect
                    x={x1}
                    y={y1}
                    width={rw}
                    height={rh}
                    fill="#000"
                    fillOpacity={0}
                    pointerEvents="all"
                  />
                )}
                <rect
                  x={x1}
                  y={y1}
                  width={rw}
                  height={rh}
                  fill="none"
                  stroke={stroke}
                  strokeWidth={isActive ? 4 : 2}
                  rx={3}
                  vectorEffect="non-scaling-stroke"
                  pointerEvents="none"
                />
                <rect
                  x={x1}
                  y={chipY}
                  width={chipW}
                  height={chipH}
                  fill={isActive ? stroke : 'rgba(15, 23, 42, 0.88)'}
                  rx={3}
                  pointerEvents="none"
                />
                <text
                  x={x1 + 6}
                  y={chipY + 14}
                  fill="#f8fafc"
                  fontSize="11"
                  fontWeight="600"
                  fontFamily="system-ui, sans-serif"
                  pointerEvents="none"
                >
                  {line1}
                </text>
              </g>
            );
          })}
        </svg>
      )}

      {activeDet && (
        <>
          <button
            type="button"
            className="detect-popover-backdrop"
            aria-label="Close product list"
            onClick={() => setActiveIndex(null)}
          />
          <div className="detect-popover" style={popStyle || undefined} role="dialog">
            <div className="detect-popover-head">
              <span className="detect-popover-title">
                {labelForDetection(activeDet).title} — in stock
              </span>
              <button
                type="button"
                className="detect-popover-close"
                aria-label="Close"
                onClick={() => setActiveIndex(null)}
              >
                ×
              </button>
            </div>

            {activeMatches.length === 0 ? (
              <p className="detect-popover-empty">No in-stock matches found.</p>
            ) : (
              <ul className="detect-match-list">
                {activeMatches.map((m) => {
                  const added = addedIds.has(m.id);
                  const busy = addingId === m.id;
                  return (
                    <li className="detect-match-row" key={m.id}>
                      {m.image_url ? (
                        <img
                          className="detect-match-thumb"
                          src={m.image_url}
                          alt=""
                          onError={(e) => {
                            e.currentTarget.style.display = 'none';
                          }}
                        />
                      ) : (
                        <span className="detect-match-thumb detect-match-thumb--ph" aria-hidden />
                      )}
                      <div className="detect-match-info">
                        <span className="detect-match-name" title={m.name}>
                          {m.name}
                        </span>
                        <span className="detect-match-meta">
                          {formatPKR(m.price)} · {Number(m.stock) || 0} in stock
                        </span>
                      </div>
                      <button
                        type="button"
                        className={`detect-match-add${added ? ' is-added' : ''}`}
                        onClick={() => handleAdd(m)}
                        disabled={busy || added}
                      >
                        {added ? 'Added ✓' : busy ? '…' : 'Add'}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}
