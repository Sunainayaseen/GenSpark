/** Saved delivery addresses — GenSpark Flask API (/api/addresses). */
import { dashboardGet, dashboardPost, dashboardPut, dashboardDelete } from './dashboardApi';

export async function listAddresses() {
  const res = await dashboardGet('/addresses');
  return Array.isArray(res?.addresses) ? res.addresses : [];
}

export function createAddress(body) {
  return dashboardPost('/addresses', body);
}

export function updateAddress(id, body) {
  return dashboardPut(`/addresses/${id}`, body);
}

export function deleteAddress(id) {
  return dashboardDelete(`/addresses/${id}`);
}

export function setDefaultAddress(id) {
  return dashboardPost(`/addresses/${id}/default`, {});
}
