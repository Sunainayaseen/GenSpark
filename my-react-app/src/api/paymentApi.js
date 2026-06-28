/**
 * Stripe checkout pipeline — Flask /api/create-payment-intent + /api/order/complete-checkout
 */
import axios from 'axios';
import { getApiPrefix } from '../utils/flaskBase';
import { getAuthHeaders } from '../utils/authStorage';

const api = axios.create({
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
  // Bounded so a hung backend surfaces an error instead of a frozen checkout button.
  timeout: 20000,
});

api.interceptors.request.use((config) => {
  config.headers = { ...config.headers, ...getAuthHeaders() };
  return config;
});

export async function createPaymentIntent(amount) {
  const { data } = await api.post(`${getApiPrefix()}/create-payment-intent`, { amount });
  return data;
}

export async function completeStripeCheckout(payload) {
  const { data } = await api.post(`${getApiPrefix()}/order/complete-checkout`, payload);
  return data;
}
