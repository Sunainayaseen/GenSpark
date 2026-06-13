import { createContext, useContext, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from './AuthContext';
import { dashboardDelete, dashboardGet, dashboardPost, dashboardPut } from '../api/dashboardApi';
import { AUTH_UPDATED_EVENT, getStoredToken } from '../utils/authStorage';

const CartContext = createContext();

export const useCart = () => {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error('useCart must be used within CartProvider');
  }
  return context;
};

export const CartProvider = ({ children }) => {
  const [serverCartItems, setServerCartItems] = useState([]);
  const [vendorGroups, setVendorGroups] = useState([]);
  const [isCartOpen, setIsCartOpen] = useState(false);

  const { user, authReady } = useAuth();

  const [cartLoading, setCartLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const toastTimerRef = useRef(null);

  const pushToast = (type, message) => {
    setToast({ type, message });
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    const ms = type === 'error' ? 6000 : 2500;
    toastTimerRef.current = setTimeout(() => setToast(null), ms);
  };

  const mapApiCartItems = (items) =>
    (Array.isArray(items) ? items : []).map((it) => ({
      id: it.cart_item_id,
      product_id: it.component_id,
      item_type: it.item_type || 'component',
      title: it.component_name || it.name,
      name: it.component_name || it.name,
      price: Number(it.price || 0),
      image_url: it.image_url,
      stock: it.stock,
      quantity: it.quantity,
      subtotal: Number(it.subtotal || 0),
      vendor_id: it.vendor_id,
      vendor_name: it.vendor_name || 'Unassigned',
      pc_build_id: it.pc_build_id || null,
    }));

  /** Apply cart payload from POST/PUT responses (same request session as add-to-cart). */
  const applyCartPayload = (cartPayload) => {
    if (!cartPayload || typeof cartPayload !== 'object') return false;
    const items = mapApiCartItems(cartPayload.items);
    const groups = Array.isArray(cartPayload.vendor_groups) ? cartPayload.vendor_groups : [];
    setVendorGroups(groups);
    setServerCartItems(items);
    return true;
  };

  const refreshCart = useCallback(async ({ keepOnError = true } = {}) => {
    try {
      setCartLoading(true);
      const res = await dashboardGet('/cart');
      if (res?.cart) {
        applyCartPayload(res.cart);
      }
    } catch (err) {
      // eslint-disable-next-line no-console
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
  }, []);

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
  const addToCart = async (product, quantity = 1, opts = {}) => {
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
  };

  const removeFromCart = async (cart_item_id) => {
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
  };

  const updateQuantity = async (cart_item_id, quantity) => {
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
  };

  const clearCart = async () => {
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
  };

  const applyCartFromServer = useCallback((cartPayload) => {
    return applyCartPayload(cartPayload);
  }, []);

  return (
    <CartContext.Provider
      value={{
        cartItems,
        vendorGroups,
        addToCart,
        removeFromCart,
        updateQuantity,
        clearCart,
        refreshCart,
        applyCartFromServer,
        cartTotal,
        cartCount,
        isCartOpen,
        setIsCartOpen,
        cartLoading,
        toast,
        pushToast,
      }}
    >
      {children}
    </CartContext.Provider>
  );
};

