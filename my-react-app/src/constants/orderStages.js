/**
 * GenSpark Builds – Order lifecycle stages.
 * Used in OrderStatus, VendorDashboard, AdminPanel, and notifications.
 */
export const ORDER_STAGES = [
  { key: 'pending', label: 'Pending', icon: '📋', description: 'Order placed by customer' },
  { key: 'approved', label: 'Approved', icon: '🛡️', description: 'Admin approved order' },
  { key: 'processing', label: 'Processing', icon: '🔧', description: 'Vendor orders are being processed' },
  {
    key: 'ready_to_dispatch',
    label: 'Ready to ship',
    icon: '📦',
    description: 'Admin approved proof — vendor will dispatch',
  },
  { key: 'shipped', label: 'Shipped', icon: '🚚', description: 'Order dispatched' },
  { key: 'completed', label: 'Completed', icon: '✅', description: 'Order closed / delivered' },
];

export const getStageIndex = (statusKey) =>
  ORDER_STAGES.findIndex((s) => s.key === statusKey);

export const PAYMENT_METHODS = {
  online: 'Online Payment',
  cod: 'Cash on Delivery (COD)',
};
