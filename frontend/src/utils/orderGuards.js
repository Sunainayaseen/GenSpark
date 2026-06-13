/** Order statuses that mean the customer must wait for admin before placing again. */
export const AWAITING_ADMIN_STATUSES = new Set(['pending', 'admin-review']);

export function findBlockingOrder(orders) {
  if (!Array.isArray(orders)) return null;
  return orders.find((o) => o?.status && AWAITING_ADMIN_STATUSES.has(String(o.status))) || null;
}
