/**
 * Currency formatting — single source of truth for PKR display.
 *
 * Always uses the international (en-US) thousands grouping: 189,000 / 420,000.
 * The Pakistani/Indian "lakh" grouping (1,89,000) is intentionally avoided because
 * the storefront targets a clean, international SaaS look — and because relying on
 * the runtime's default locale rendered inconsistently across browsers.
 */

/** Format a number with international thousands grouping (no currency prefix). */
export function formatNumber(amount) {
  const n = Number(String(amount).replace(/,/g, ''));
  if (!Number.isFinite(n)) return String(amount ?? '');
  return Math.round(n).toLocaleString('en-US');
}

/** Format an amount as "PKR 189,000". */
export function formatPKR(amount) {
  return `PKR ${formatNumber(amount)}`;
}
