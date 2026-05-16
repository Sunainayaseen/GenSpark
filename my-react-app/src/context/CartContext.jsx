import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from './AuthContext';
import { dashboardDelete, dashboardGet, dashboardPost, dashboardPut } from '../api/dashboardApi';

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

  const { user } = useAuth();

  const [cartLoading, setCartLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const toastTimerRef = useRef(null);

  const pushToast = (type, message) => {
    setToast({ type, message });
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    const ms = type === 'error' ? 6000 : 2500;
    toastTimerRef.current = setTimeout(() => setToast(null), ms);
  };

  const refreshCart = async () => {
    try {
      setCartLoading(true);
      const res = await dashboardGet('/cart');
      const items = Array.isArray(res?.cart?.items) ? res.cart.items : [];
      const groups = Array.isArray(res?.cart?.vendor_groups) ? res.cart.vendor_groups : [];
      setVendorGroups(groups);
      setServerCartItems(
        items.map((it) => ({
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
        }))
      );
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('Failed to refresh cart', err);
      setServerCartItems([]);
      setVendorGroups([]);
    } finally {
      setCartLoading(false);
    }
  };

  useEffect(() => {
    // Load cart on mount and after login (merge guest cart on backend).
    refreshCart();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  const cartItems = useMemo(() => serverCartItems, [serverCartItems]);

  const cartTotal = useMemo(
    () => cartItems.reduce((sum, item) => sum + (item.subtotal || (item.price || 0) * item.quantity), 0),
    [cartItems]
  );

  const cartCount = useMemo(() => cartItems.reduce((sum, item) => sum + item.quantity, 0), [cartItems]);

  const addToCart = async (product, quantity = 1) => {
    const itemType = product?.item_type || product?.type || 'component';
    const itemId = product?.id;
    if (!itemId) {
      pushToast('error', 'Invalid product');
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
      let msg = 'Added to cart';
      if (res?.assigned_vendor?.shop_name) {
        msg = `Added to cart — vendor: ${res.assigned_vendor.shop_name}`;
      } else if (Array.isArray(res?.assigned_vendors) && res.assigned_vendors.length > 1) {
        msg = `Added to cart — ${res.assigned_vendors.length} items assigned to vendors`;
      }
      pushToast('success', msg);
      await refreshCart();
      return true;
    } catch (err) {
      const msg = err?.data?.error || err?.data?.message || err.message || 'Add to cart failed';
      pushToast('error', msg);
      return false;
    }
  };

  const removeFromCart = async (cart_item_id) => {
    try {
      const res = await dashboardDelete('/remove-item', { cart_item_id });
      if (!res?.success) throw new Error(res?.error || res?.message || 'Failed to remove item');
      await refreshCart();
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
      await refreshCart();
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
      await refreshCart();
      pushToast('success', 'Cart cleared');
      return true;
    } catch (err) {
      const msg = err?.data?.error || err?.data?.message || err.message || 'Clear failed';
      pushToast('error', msg);
      return false;
    }
  };

  return (
    <CartContext.Provider
      value={{
        cartItems,
        vendorGroups,
        addToCart,
        removeFromCart,
        updateQuantity,
        clearCart,
        cartTotal,
        cartCount,
        isCartOpen,
        setIsCartOpen,
        cartLoading,
        toast,
      }}
    >
      {children}
    </CartContext.Provider>
  );
};

