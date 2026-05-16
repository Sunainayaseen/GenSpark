import { useId } from 'react';

/**
 * Category-themed SVG placeholders when DB has no image_url or image fails to load.
 */
export default function ComponentMediaPlaceholder({ kind = 'generic' }) {
  const uid = useId().replace(/:/g, '');
  const stroke = 'rgba(148, 163, 184, 0.55)';
  const fill = 'rgba(56, 189, 248, 0.12)';
  const accent = 'rgba(56, 189, 248, 0.65)';
  const gradId = `ph-grad-${uid}`;

  const wrap = (children) => (
    <svg
      className="components-card-placeholder-svg"
      viewBox="0 0 120 80"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="120" y2="80" gradientUnits="userSpaceOnUse">
          <stop stopColor="rgba(15, 23, 42, 0.92)" />
          <stop offset="1" stopColor="rgba(30, 41, 59, 0.88)" />
        </linearGradient>
      </defs>
      <rect width="120" height="80" rx="8" fill={`url(#${gradId})`} />
      {children}
    </svg>
  );

  switch (kind) {
    case 'gpu':
      return wrap(
        <>
          <rect x="18" y="22" width="84" height="36" rx="4" stroke={stroke} strokeWidth="1.5" fill={fill} />
          <circle cx="38" cy="40" r="6" stroke={accent} strokeWidth="1.5" />
          <path d="M52 36h40M52 40h32M52 44h28" stroke={stroke} strokeWidth="1.2" strokeLinecap="round" />
          <rect x="78" y="32" width="16" height="16" rx="2" stroke={accent} strokeWidth="1.2" />
        </>
      );
    case 'cpu':
      return wrap(
        <>
          <rect x="40" y="28" width="40" height="40" rx="4" stroke={accent} strokeWidth="1.5" fill={fill} />
          <path d="M40 36h-8M40 44h-8M40 52h-8M40 60h-8M80 36h8M80 44h8M80 52h8M80 60h8M48 28v-8M56 28v-8M64 28v-8M72 28v-8M48 68v8M56 68v8M64 68v8M72 68v8" stroke={stroke} strokeWidth="1.2" />
          <rect x="52" y="40" width="16" height="16" rx="2" stroke={stroke} strokeWidth="1.2" />
        </>
      );
    case 'ram':
      return wrap(
        <>
          <rect x="28" y="26" width="64" height="28" rx="3" stroke={accent} strokeWidth="1.5" fill={fill} />
          <path d="M36 54v8M44 54v8M52 54v8M60 54v8M68 54v8M76 54v8M84 54v8" stroke={stroke} strokeWidth="2" strokeLinecap="round" />
          <path d="M32 34h56" stroke={stroke} strokeWidth="1" opacity="0.6" />
        </>
      );
    case 'storage':
      return wrap(
        <>
          <rect x="30" y="30" width="60" height="24" rx="3" stroke={accent} strokeWidth="1.5" fill={fill} />
          <rect x="36" y="36" width="48" height="6" rx="1" stroke={stroke} strokeWidth="1" />
          <circle cx="42" cy="48" r="2" fill={accent} />
          <path d="M48 48h44" stroke={stroke} strokeWidth="1" strokeLinecap="round" />
        </>
      );
    case 'motherboard':
      return wrap(
        <>
          <rect x="22" y="20" width="76" height="44" rx="3" stroke={accent} strokeWidth="1.5" fill={fill} />
          <rect x="48" y="32" width="24" height="20" rx="2" stroke={stroke} strokeWidth="1.2" />
          <circle cx="34" cy="30" r="3" stroke={stroke} strokeWidth="1" />
          <circle cx="86" cy="52" r="3" stroke={stroke} strokeWidth="1" />
        </>
      );
    case 'psu':
      return wrap(
        <>
          <rect x="26" y="26" width="68" height="32" rx="4" stroke={accent} strokeWidth="1.5" fill={fill} />
          <circle cx="42" cy="42" r="10" stroke={stroke} strokeWidth="1.2" />
          <path d="M78 36h12M78 42h12M78 48h12" stroke={stroke} strokeWidth="1.2" strokeLinecap="round" />
        </>
      );
    case 'case':
      return wrap(
        <>
          <rect x="38" y="18" width="44" height="48" rx="3" stroke={accent} strokeWidth="1.5" fill={fill} />
          <circle cx="60" cy="32" r="8" stroke={stroke} strokeWidth="1.2" />
          <path d="M46 50h28M46 56h20" stroke={stroke} strokeWidth="1.2" strokeLinecap="round" />
        </>
      );
    case 'cooling':
      return wrap(
        <>
          <circle cx="60" cy="40" r="22" stroke={accent} strokeWidth="1.5" fill={fill} />
          <circle cx="60" cy="40" r="14" stroke={stroke} strokeWidth="1.2" />
          <path d="M60 18v8M60 54v8M38 40h-8M82 40h8M44 26l-6-6M76 54l6 6" stroke={stroke} strokeWidth="1.2" strokeLinecap="round" />
        </>
      );
    case 'monitor':
      return wrap(
        <>
          <rect x="22" y="16" width="76" height="44" rx="4" stroke={accent} strokeWidth="1.5" fill={fill} />
          <path d="M30 26h60M30 34h48" stroke={stroke} strokeWidth="1" strokeLinecap="round" />
          <path d="M60 60v8M52 68h16" stroke={stroke} strokeWidth="1.5" strokeLinecap="round" />
        </>
      );
    case 'peripheral':
      return wrap(
        <>
          <rect x="28" y="36" width="64" height="22" rx="3" stroke={accent} strokeWidth="1.5" fill={fill} />
          <path d="M36 44h48M40 50h8M52 50h8M64 50h8" stroke={stroke} strokeWidth="1.2" strokeLinecap="round" />
          <circle cx="60" cy="26" r="8" stroke={accent} strokeWidth="1.2" />
        </>
      );
    default:
      return wrap(
        <>
          <rect x="28" y="24" width="64" height="36" rx="4" stroke={accent} strokeWidth="1.5" fill={fill} />
          <path d="M40 36h40M40 44h32M40 52h24" stroke={stroke} strokeWidth="1.2" strokeLinecap="round" />
          <circle cx="88" cy="32" r="6" stroke={stroke} strokeWidth="1.2" />
        </>
      );
  }
}
