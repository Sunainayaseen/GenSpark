import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { dashboardGet } from '../api/dashboardApi';
import { findBlockingOrder } from '../utils/orderGuards';

/**
 * When the user has a master order in pending / admin-review, they cannot place another
 * (enforced in POST /api/orders/place). This hook supports checkout/cart UI.
 */
const CHECK_TIMEOUT_MS = 10000;

export function useBlockingOrder() {
  const { isLoggedIn } = useAuth();
  const [blockingOrder, setBlockingOrder] = useState(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    if (!isLoggedIn) {
      setBlockingOrder(null);
      setChecking(false);
      return;
    }
    let cancelled = false;
    (async () => {
      setChecking(true);
      try {
        const res = await Promise.race([
          dashboardGet('/orders?mine=1'),
          new Promise((_, reject) => {
            setTimeout(() => reject(new Error('timeout')), CHECK_TIMEOUT_MS);
          }),
        ]);
        const list = Array.isArray(res?.orders) ? res.orders : [];
        if (!cancelled) setBlockingOrder(findBlockingOrder(list) || null);
      } catch {
        if (!cancelled) setBlockingOrder(null);
      } finally {
        if (!cancelled) setChecking(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isLoggedIn]);

  return { blockingOrder, checkingBlocking: checking };
}
