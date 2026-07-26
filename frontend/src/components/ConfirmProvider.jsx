import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';
import './ConfirmProvider.css';

/**
 * App-wide replacement for native window.confirm / window.alert.
 *
 *   const { confirm, notify } = useConfirm();
 *   if (!(await confirm({ title, message, danger: true }))) return;   // modal
 *   notify('Saved', { type: 'success' });                            // toast
 *
 * Promise-based so call sites read almost like the native API. Rendered through a
 * portal on document.body, so it overlays everything and never clips inside cards.
 */
const ConfirmContext = createContext(null);

// Provider + hook live together (same pattern as the app's context files).
// eslint-disable-next-line react-refresh/only-export-components
export function useConfirm() {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error('useConfirm must be used within <ConfirmProvider>');
  return ctx;
}

let toastSeq = 0;

export function ConfirmProvider({ children }) {
  const [dialog, setDialog] = useState(null);
  const [toasts, setToasts] = useState([]);
  const resolverRef = useRef(null);

  const close = useCallback((result) => {
    setDialog(null);
    const resolve = resolverRef.current;
    resolverRef.current = null;
    if (resolve) resolve(result);
  }, []);

  const confirm = useCallback(
    (options = {}) =>
      new Promise((resolve) => {
        resolverRef.current = resolve;
        setDialog({
          title: options.title || 'Are you sure?',
          message: options.message || '',
          confirmText: options.confirmText || 'Confirm',
          cancelText: options.cancelText || 'Cancel',
          danger: Boolean(options.danger),
        });
      }),
    []
  );

  const notify = useCallback((message, opts = {}) => {
    const id = (toastSeq += 1);
    const type = opts.type || 'info';
    const duration = opts.duration ?? (type === 'error' ? 5000 : 3000);
    setToasts((list) => [...list, { id, message: String(message || ''), type }]);
    if (duration > 0) {
      setTimeout(() => setToasts((list) => list.filter((t) => t.id !== id)), duration);
    }
    return id;
  }, []);

  // ESC = cancel.
  useEffect(() => {
    if (!dialog) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') close(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [dialog, close]);

  const value = useMemo(() => ({ confirm, notify }), [confirm, notify]);

  return (
    <ConfirmContext.Provider value={value}>
      {children}

      {dialog
        ? createPortal(
            <div className="gs-confirm-overlay" role="presentation" onMouseDown={() => close(false)}>
              <div
                className="gs-confirm-dialog"
                role="alertdialog"
                aria-modal="true"
                aria-labelledby="gs-confirm-title"
                onMouseDown={(e) => e.stopPropagation()}
              >
                <h2 id="gs-confirm-title" className="gs-confirm-title">
                  {dialog.title}
                </h2>
                {dialog.message ? <p className="gs-confirm-message">{dialog.message}</p> : null}
                <div className="gs-confirm-actions">
                  <button
                    type="button"
                    className="gs-confirm-btn gs-confirm-btn--ghost"
                    onClick={() => close(false)}
                    autoFocus={dialog.danger}
                  >
                    {dialog.cancelText}
                  </button>
                  <button
                    type="button"
                    className={`gs-confirm-btn ${dialog.danger ? 'gs-confirm-btn--danger' : 'gs-confirm-btn--primary'}`}
                    onClick={() => close(true)}
                    autoFocus={!dialog.danger}
                  >
                    {dialog.confirmText}
                  </button>
                </div>
              </div>
            </div>,
            document.body
          )
        : null}

      {toasts.length > 0
        ? createPortal(
            <div className="gs-toast-stack" aria-live="polite">
              {toasts.map((t) => (
                <div key={t.id} className={`gs-toast gs-toast--${t.type}`} role="status">
                  {t.message}
                </div>
              ))}
            </div>,
            document.body
          )
        : null}
    </ConfirmContext.Provider>
  );
}
