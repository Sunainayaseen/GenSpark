/** Prefetch route chunks on hover / idle so header nav feels instant. */

/** Header routes are bundled eagerly in App.jsx; prefetch only secondary lazy pages. */
const ROUTE_LOADERS = {
  '/contact': () => import('../pages/Contact'),
  '/configurator': () => import('../pages/BuildConfigurator'),
  '/cart': () => import('../pages/CartPage'),
  '/checkout': () => import('../pages/Checkout'),
  '/vendor-assignment': () => import('../pages/VendorAssignment'),
};

const prefetched = new Set();

function normalizePath(pathname) {
  if (!pathname) return '';
  if (pathname === '/') return '/';
  if (pathname.startsWith('/builds')) return '/builds';
  return pathname.split('?')[0];
}

export function prefetchRoute(pathname) {
  const key = normalizePath(pathname);
  const load = ROUTE_LOADERS[key];
  if (!load || prefetched.has(key)) return;
  prefetched.add(key);
  load().catch(() => {
    prefetched.delete(key);
  });
}

/** Warm all main header destinations after first paint. */
/** No-op for main nav (already in main bundle); keeps call sites stable. */
export function prefetchMainNavRoutes() {
  Object.keys(ROUTE_LOADERS).forEach(prefetchRoute);
}
