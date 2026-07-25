import { createContext, useContext, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from './AuthContext';
import { dashboardDelete, dashboardGet, dashboardPost, dashboardPut } from '../api/dashboardApi';
import { AUTH_UPDATED_EVENT, getStoredToken } from '../utils/authStorage';

const CartContext = createContext();

// Splitting this hook into its own file would require updating every one of
// its consumers' imports across the app; the rule only affects dev Fast
// Refresh, not production behavior.
// eslint-disable-next-line react-refresh/only-export-components
export const useCart = () => {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error('useCart must be used within CartProvider');
  }
  return context;
};

// Mirrors Dashboard/app/api/ai_build_routes.py's _REC_SLOT_RULES category map —
// the same definition of "this is a PC-build part" used to decide which catalog
// categories the recommender/build-options endpoints treat as a build slot.
// Assembly is done by the supplying vendor, so only THESE categories are subject
// to the single-vendor-per-build rule; standalone accessories are unaffected.
const BUILD_CATEGORY_NAMES = new Set([
  'Processor', 'CPU', 'GPU', 'Graphics Card', 'Motherboard', 'RAM',
  'Storage', 'PSU', 'Power Supply', 'Case', 'Cabinet',
]);

const mapApiCartItems = (items) =>
  (Array.isArray(items) ? items : []).map((it) => ({
    id: it.cart_item_id,
    product_id: it.component_id,
    item_type: it.item_type || 'component',
    title: it.component_name || it.name,
    name: it.component_name || it.name,
    category: it.category || null,
    price: Number(it.price || 0),
    image_url: it.image_url,
    stock: it.stock,
    quantity: it.quantity,
    subtotal: Number(it.subtotal || 0),
    vendor_id: it.vendor_id,
    vendor_name: it.vendor_name || 'Unassigned',
    pc_build_id: it.pc_build_id || null,
  }));

/** All build-category items in the cart must share one vendor — assembly is done
 * by the supplying vendor, so a build split across vendors can't be assembled. */
const computeBuildVendorConflict = (items) => {
  const buildItems = (items || []).filter((it) => BUILD_CATEGORY_NAMES.has(it.category));
  const vendorIds = [...new Set(buildItems.map((it) => it.vendor_id).filter(Boolean))];
  const hasConflict = vendorIds.length > 1;
  if (!hasConflict) {
    return {
      hasConflict: false,
      vendorName: buildItems.length ? buildItems[0].vendor_name : null,
      conflictingItemIds: [],
    };
  }
  // Items NOT matching the majority vendor are the ones to highlight/swap.
  const counts = new Map();
  buildItems.forEach((it) => counts.set(it.vendor_id, (counts.get(it.vendor_id) || 0) + 1));
  const majorityVendorId = [...counts.entries()].sort((a, b) => b[1] - a[1])[0][0];
  const conflictingItemIds = buildItems
    .filter((it) => it.vendor_id !== majorityVendorId)
    .map((it) => it.id);
  return { hasConflict: true, vendorName: null, conflictingItemIds };
};

export const CartProvider = ({ children }) => {
  const [serverCartItems, setServerCartItems] = useState([]);
  const [vendorGroups, setVendorGroups] = useState([]);
  const [isCartOpen, setIsCartOpen] = useState(false);

  const { user, authReady } = useAuth();

  const [cartLoading, setCartLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const toastTimerRef = useRef(null);

  const pushToast = useCallback((type, message) => {
    setToast({ type, message });
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    const ms = type === 'error' ? 6000 : 2500;
    toastTimerRef.current = setTimeout(() => setToast(null), ms);
  }, []);

  /** Apply cart payload from POST/PUT responses (same request session as add-to-cart). */
  const applyCartPayload = useCallback((cartPayload) => {
    if (!cartPayload || typeof cartPayload !== 'object') return false;
    const items = mapApiCartItems(cartPayload.items);
    const groups = Array.isArray(cartPayload.vendor_groups) ? cartPayload.vendor_groups : [];
    setVendorGroups(groups);
    setServerCartItems(items);
    return true;
  }, []);

  const refreshCart = useCallback(async ({ keepOnError = true } = {}) => {
    try {
      setCartLoading(true);
      const res = await dashboardGet('/cart');
      if (res?.cart) {
        applyCartPayload(res.cart);
      }
    } catch (err) {
      console.error('Failed to refresh cart', err);
      if (err?.status === 401) {
        pushToast('error', 'Please sign in again to view your cart.');
      }
      // Do not wipe cart after a successful add — GET /cart can miss session on cross-origin.
      if (!keepOnError) {
        setServerCartItems([]);
        setVendorGroups([]);
      }
    } finally {
      setCartLoading(false);
    }
  }, [applyCartPayload, pushToast]);

  useEffect(() => {
    if (!authReady) return;
    refreshCart({ keepOnError: false });
  }, [authReady, user?.id, refreshCart]);

  useEffect(() => {
    const onAuthUpdated = () => {
      refreshCart({ keepOnError: false });
    };
    window.addEventListener(AUTH_UPDATED_EVENT, onAuthUpdated);
    return () => window.removeEventListener(AUTH_UPDATED_EVENT, onAuthUpdated);
  }, [refreshCart]);

  const cartItems = useMemo(() => serverCartItems, [serverCartItems]);

  const cartTotal = useMemo(
    () => cartItems.reduce((sum, item) => sum + (item.subtotal || (item.price || 0) * item.quantity), 0),
    [cartItems]
  );

  const cartCount = useMemo(() => cartItems.reduce((sum, item) => sum + item.quantity, 0), [cartItems]);

  // opts.silent suppresses per-item toasts — used for bulk adds (e.g. a whole
  // prebuilt build) where the caller shows a single summary instead.
  const addToCart = useCallback(async (product, quantity = 1, opts = {}) => {
    const { silent = false } = opts;
    const itemType = product?.item_type || product?.type || 'component';
    const itemId = product?.id;
    if (!itemId) {
      if (!silent) pushToast('error', 'Invalid product');
      return false;
    }
    try {
      const res = await dashboardPost('/add-to-cart', {
        item_type: itemType,
        item_id: itemId,
        quantity,
        vendor_id: product?.vendor_id || null,
      });
      if (!res?.success) throw new Error(res?.error || res?.message || 'Failed to add to cart');
      // Update navbar count immediately from POST body (same session as add-to-cart).
      const applied = applyCartPayload(res.cart);
      if (!applied) {
        await refreshCart({ keepOnError: true });
      }
      let msg = 'Added to cart';
      if (res?.assigned_vendor?.shop_name) {
        msg = `Added to cart — vendor: ${res.assigned_vendor.shop_name}`;
      } else if (Array.isArray(res?.assigned_vendors) && res.assigned_vendors.length > 1) {
        msg = `Added to cart — ${res.assigned_vendors.length} items assigned to vendors`;
      }
      if (!silent) pushToast('success', msg);
      if (getStoredToken()) {
        refreshCart({ keepOnError: true }).catch(() => {});
      }
      return true;
    } catch (err) {
      const msg = err?.data?.error || err?.data?.message || err.message || 'Add to cart failed';
      if (!silent) pushToast('error', msg);
      return false;
    }
  }, [pushToast, refreshCart, applyCartPayload]);

  // Adds a whole PC build at once, resolved server-side to ONE vendor (assembly is
  // done by the supplying vendor — a build can never be split across vendors).
  // Pass `vendorId` to pin the build to a specific (full-coverage) vendor the user
  // picked; omit it to auto-pick the cheapest full-coverage vendor.
  // Returns {ok, vendor, error, code, missingComponentIds} so callers can show the
  // exact validation message instead of a generic toast.
  const addBuildToCart = useCallback(async (components, vendorId = null) => {
    try {
      const res = await dashboardPost('/cart/add-build', { components, vendor_id: vendorId });
      if (!res?.success) {
        return {
          ok: false,
          error: res?.error || 'Failed to add build to cart',
          code: res?.code || null,
          missingComponentIds: res?.missing_component_ids || [],
        };
      }
      const applied = applyCartPayload(res.cart);
      if (!applied) await refreshCart({ keepOnError: true });
      return { ok: true, vendor: res.vendor || null };
    } catch (err) {
      return {
        ok: false,
        error: err?.data?.error || err?.data?.message || err.message || 'Add to cart failed',
        code: err?.data?.code || null,
        missingComponentIds: err?.data?.missing_component_ids || [],
      };
    }
  }, [applyCartPayload, refreshCart]);

  // Read-only: which vendors can fully supply this exact set of components, so a
  // vendor-picker UI can be shown before committing via addBuildToCart. Does not
  // touch the cart.
  const getBuildVendorOptions = useCallback(async (components) => {
    try {
      const res = await dashboardPost('/cart/build-coverage', { components });
      if (!res?.success) {
        return { ok: false, error: res?.error || 'Failed to check vendor availability', vendors: [] };
      }
      return {
        ok: true,
        vendors: res.vendors || [],
        coversAll: Boolean(res.covers_all),
        missingComponentIds: res.missing_component_ids || [],
      };
    } catch (err) {
      return {
        ok: false,
        error: err?.data?.error || err?.data?.message || err.message || 'Failed to check vendor availability',
        vendors: [],
      };
    }
  }, []);

  const removeFromCart = useCallback(async (cart_item_id) => {
    try {
      const res = await dashboardDelete('/remove-item', { cart_item_id });
      if (!res?.success) throw new Error(res?.error || res?.message || 'Failed to remove item');
      if (!applyCartPayload(res.cart)) await refreshCart();
      else refreshCart().catch(() => {});
      pushToast('success', 'Item removed');
      return true;
    } catch (err) {
      const msg = err?.data?.error || err?.data?.message || err.message || 'Remove failed';
      pushToast('error', msg);
      return false;
    }
  }, [pushToast, refreshCart, applyCartPayload]);

  const updateQuantity = useCallback(async (cart_item_id, quantity) => {
    try {
      const res = await dashboardPut('/update-cart', { cart_item_id, quantity });
      if (!res?.success) throw new Error(res?.error || res?.message || 'Failed to update cart');
      if (!applyCartPayload(res.cart)) await refreshCart();
      else refreshCart().catch(() => {});
      return true;
    } catch (err) {
      const msg = err?.data?.error || err?.data?.message || err.message || 'Update failed';
      pushToast('error', msg);
      return false;
    }
  }, [pushToast, refreshCart, applyCartPayload]);

  const clearCart = useCallback(async () => {
    try {
      const res = await dashboardPost('/cart/clear', {});
      if (!res?.success) throw new Error(res?.error || res?.message || 'Failed to clear cart');
      if (!applyCartPayload(res.cart)) await refreshCart();
      else refreshCart().catch(() => {});
      pushToast('success', 'Cart cleared');
      return true;
    } catch (err) {
      const msg = err?.data?.error || err?.data?.message || err.message || 'Clear failed';
      pushToast('error', msg);
      return false;
    }
  }, [pushToast, refreshCart, applyCartPayload]);

  const applyCartFromServer = useCallback((cartPayload) => {
    return applyCartPayload(cartPayload);
  }, [applyCartPayload]);

  const buildVendorConflict = useMemo(() => computeBuildVendorConflict(cartItems), [cartItems]);

  const value = useMemo(
    () => ({
      cartItems,
      vendorGroups,
      addToCart,
      addBuildToCart,
      getBuildVendorOptions,
      removeFromCart,
      updateQuantity,
      clearCart,
      refreshCart,
      applyCartFromServer,
      cartTotal,
      cartCount,
      buildVendorConflict,
      isCartOpen,
      setIsCartOpen,
      cartLoading,
      toast,
      pushToast,
    }),
    [
      cartItems,
      vendorGroups,
      addToCart,
      addBuildToCart,
      getBuildVendorOptions,
      removeFromCart,
      updateQuantity,
      clearCart,
      refreshCart,
      buildVendorConflict,
      applyCartFromServer,
      cartTotal,
      cartCount,
      isCartOpen,
      cartLoading,
      toast,
      pushToast,
    ]
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
};

