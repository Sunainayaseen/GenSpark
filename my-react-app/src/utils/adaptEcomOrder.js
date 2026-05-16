/**
 * Adapts GET /api/ecom/orders/:id payload to the shape used by OrderStatus (PC order view).
 */
export function adaptEcomOrder(ecom) {
  if (!ecom) return null;
  const items = (ecom.items || []).map((it) => ({
    id: it.id,
    item_type: 'product',
    item_id: it.product_id,
    component_name: it.name || 'Product',
    vendor_id: null,
    quantity: it.quantity,
    unit_price: Number(it.unit_price || 0),
    total_price: Number(it.line_total ?? (it.unit_price || 0) * (it.quantity || 0)),
  }));
  const sub = items.reduce((s, it) => s + Number(it.total_price || 0), 0);
  const ship = Math.max(0, Number(ecom.total_amount || 0) - sub);
  const address = [ecom.name, ecom.phone, ecom.address, ecom.city].filter(Boolean).join(' · ');

  return {
    _source: 'ecom',
    id: ecom.id,
    order_number: ecom.order_number,
    total_amount: Number(ecom.total_amount || 0),
    items_subtotal: sub,
    shipping_fee: ship,
    status: ecom.status,
    shipping_address: address,
    created_at: ecom.created_at,
    items,
    status_history: [],
    vendor_orders: [],
    payment_method: ecom.payment_method,
  };
}

/** eCom lifecycle → index into ORDER_STAGES (approximate) */
export function ecomStageIndex(status) {
  const s = (status || '').toLowerCase();
  if (s === 'cancelled' || s === 'rejected') return -1;
  const m = { pending: 0, processing: 2, shipped: 4, delivered: 5 };
  return m[s] != null ? m[s] : 0;
}
