import { useState, useCallback } from 'react';

import './ImageDetectOverlay.css';

const DISPLAY_CONFIRM_THRESHOLD_PCT = 80;

const labelForDetection = (d) => {
  const conf = Math.min(Math.max(Number(d.confidence) ?? 0, 0), 100);
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

/**
 * Responsive image with SVG overlay in original pixel space (viewBox = natural image).
 * Expects Flask `/api/detect/component` fields: xyxy, class_name, confidence (%), optional image_width/height.
 */
export default function ImageDetectOverlay({
  src,
  detections = [],
  naturalWidth,
  naturalHeight,
  alt = 'Uploaded image',
}) {
  const [intrinsic, setIntrinsic] = useState({ w: naturalWidth || 0, h: naturalHeight || 0 });

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

  return (
    <div className="image-detect-frame">
      <img src={src} alt={alt} className="image-detect-img" onLoad={onImgLoad} loading="lazy" />
      {hasOverlay && (
        <svg
          className="image-detect-svg"
          viewBox={`0 0 ${nw} ${nh}`}
          preserveAspectRatio="xMidYMid meet"
          aria-hidden
        >
          {detections.map((d, i) => {
            const xy = resolveXyxy(d, nw, nh);
            if (!xy) return null;
            const [x1, y1, x2, y2] = xy;
            const rw = Math.max(0, x2 - x1);
            const rh = Math.max(0, y2 - y1);
            const { title, sub, pct } = labelForDetection(d);
            const stroke = strokeForDetection(d);
            const chipY = Math.max(0, y1 - 22);
            const chipH = 20;
            const line1 = sub ? `${title} ${pct.toFixed(1)}% · ${sub}` : `${title} ${pct.toFixed(1)}%`;

            return (
              <g key={`det-${i}`}>
                <rect
                  x={x1}
                  y={y1}
                  width={rw}
                  height={rh}
                  fill="none"
                  stroke={stroke}
                  strokeWidth={2}
                  rx={3}
                  vectorEffect="non-scaling-stroke"
                />
                <rect
                  x={x1}
                  y={chipY}
                  width={Math.min(Math.max(0, nw - x1 - 4), 240)}
                  height={chipH}
                  fill="rgba(15, 23, 42, 0.88)"
                  rx={3}
                />
                <text
                  x={x1 + 6}
                  y={chipY + 14}
                  fill="#f8fafc"
                  fontSize="11"
                  fontWeight="600"
                  fontFamily="system-ui, sans-serif"
                >
                  {line1}
                </text>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}
