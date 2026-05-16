/**
 * eCommerce JSON API (Flask) — /api/ecom/...
 * Requires session cookies (login via site auth).
 */

const getBase = () => {
  if (import.meta.env.VITE_API_BASE) {
    return import.meta.env.VITE_API_BASE.replace(/\/$/, '');
  }
  return '';
};

const API = `${getBase() || ''}/api/ecom`;

async function ecomRequest(path, options = {}) {
  const url = `${API}${path.startsWith('/') ? path : `/${path}`}`;
  const res = await fetch(url, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || res.statusText || 'Request failed');
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const ecomGetProducts = () => ecomRequest('/products');
export const ecomGetCart = () => ecomRequest('/cart');
export const ecomAddItem = (productId, quantity = 1) =>
  ecomRequest('/cart/items', { method: 'POST', body: JSON.stringify({ product_id: productId, quantity }) });
export const ecomRemoveItem = (itemId) => ecomRequest(`/cart/items/${itemId}`, { method: 'DELETE' });
export const ecomSendForApproval = (cartId) => ecomRequest(`/cart/${cartId}/send-for-approval`, { method: 'PUT' });
export const ecomResetRejected = (cartId) => ecomRequest(`/cart/${cartId}/reset`, { method: 'POST' });
export const ecomPlaceOrder = (body) => ecomRequest('/orders', { method: 'POST', body: JSON.stringify(body) });
export const ecomMyOrders = () => ecomRequest('/my-orders');
export const ecomGetOrder = (id) => ecomRequest(`/orders/${id}`);

// Admin
export const ecomAdminCarts = (status = 'pending_approval') =>
  ecomRequest(`/admin/carts?status=${encodeURIComponent(status)}`);
export const ecomAdminApproveCart = (cartId) => ecomRequest(`/admin/carts/${cartId}/approve`, { method: 'POST' });
export const ecomAdminRejectCart = (cartId) => ecomRequest(`/admin/carts/${cartId}/reject`, { method: 'POST' });
export const ecomAdminOrders = () => ecomRequest('/admin/orders');
export const ecomAdminSetOrderStatus = (orderId, status) =>
  ecomRequest(`/admin/orders/${orderId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
