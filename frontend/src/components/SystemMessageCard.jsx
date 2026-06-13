import { useEffect, useState } from 'react';
import './SystemMessageCard.css';

/**
 * SystemMessageCard — a "Control Center" style system message for the AI chat.
 *
 * Hosts a titled header with a status indicator, an optional data table,
 * action buttons (e.g. Download Invoice), and a non-blocking "View Logic"
 * drawer that reveals the calculation logs behind the result.
 *
 * While the system is computing, pass `processing` to show a step tracker
 * instead of the table — so the user sees progress, never a frozen screen.
 *
 * Props
 *  - title        string            card heading (e.g. "Invoice #ORD-1042")
 *  - status       'processing'|'success'|'error'|'info'
 *  - statusLabel  string            text in the status pill
 *  - table        { columns: [{key,label,numeric?}], rows: [{...}] }
 *  - actions      [{ label, onClick, variant?: 'primary'|'ghost', icon? }]
 *  - logs         [{ step, detail?, value? }]   calculation log lines
 *  - processing   { percent?: number, steps: [{ label, state: 'done'|'active'|'pending' }] }
 */
export default function SystemMessageCard({
  title,
  status = 'info',
  statusLabel,
  table = null,
  actions = [],
  logs = [],
  processing = null,
}) {
  const [logsOpen, setLogsOpen] = useState(false);
  const isProcessing = status === 'processing' || !!processing;

  return (
    <article className={`sys-card sys-card--${status}`} aria-busy={isProcessing}>
      <header className="sys-card__head">
        <h4 className="sys-card__title">{title}</h4>
        {statusLabel && <StatusPill status={status} label={statusLabel} />}
      </header>

      <div className="sys-card__body">
        {isProcessing && processing ? (
          <ProcessingSteps percent={processing.percent} steps={processing.steps} />
        ) : (
          table && <DataTable table={table} />
        )}
      </div>

      {(actions.length > 0 || logs.length > 0) && !isProcessing && (
        <footer className="sys-card__foot">
          <div className="sys-card__actions">
            {actions.map((a, i) => (
              <button
                key={i}
                type="button"
                className={`sys-btn sys-btn--${a.variant || 'primary'}`}
                onClick={a.onClick}
              >
                {a.icon && <span className="sys-btn__icon" aria-hidden>{a.icon}</span>}
                {a.label}
              </button>
            ))}
          </div>
          {logs.length > 0 && (
            <button
              type="button"
              className="sys-card__logtoggle"
              onClick={() => setLogsOpen(true)}
              aria-haspopup="dialog"
            >
              <span className="sys-card__logtoggle-glyph" aria-hidden>{'</>'}</span>
              View logic
            </button>
          )}
        </footer>
      )}

      <CalculationLogsDrawer
        open={logsOpen}
        onClose={() => setLogsOpen(false)}
        title={title}
        logs={logs}
      />
    </article>
  );
}

function StatusPill({ status, label }) {
  return (
    <span className={`sys-pill sys-pill--${status}`}>
      <span className="sys-pill__dot" aria-hidden />
      {label}
    </span>
  );
}

function DataTable({ table }) {
  const { columns = [], rows = [] } = table;
  return (
    <div className="sys-table-wrap" role="region" aria-label="Result data" tabIndex={0}>
      <table className="sys-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.numeric ? 'is-num' : ''}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={ri}>
              {columns.map((c) => (
                <td key={c.key} className={c.numeric ? 'is-num' : ''}>{r[c.key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ProcessingSteps({ percent = null, steps = [] }) {
  return (
    <div className="sys-proc">
      {percent != null && (
        <div className="sys-proc__bar" role="progressbar" aria-valuenow={Math.round(percent)} aria-valuemin={0} aria-valuemax={100}>
          <span className="sys-proc__fill" style={{ width: `${Math.min(Math.max(percent, 0), 100)}%` }} />
        </div>
      )}
      <ol className="sys-proc__steps">
        {steps.map((s, i) => (
          <li key={i} className={`sys-proc__step is-${s.state}`}>
            <span className="sys-proc__marker" aria-hidden>
              {s.state === 'done' ? '✓' : s.state === 'active' ? <span className="sys-proc__spin" /> : i + 1}
            </span>
            <span className="sys-proc__label">{s.label}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function CalculationLogsDrawer({ open, onClose, title, logs = [] }) {
  // Close on Escape; lock body scroll while open.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  return (
    <div className={`sys-drawer ${open ? 'is-open' : ''}`} aria-hidden={!open}>
      <div className="sys-drawer__scrim" onClick={onClose} />
      <aside className="sys-drawer__panel" role="dialog" aria-modal="true" aria-label="Calculation logs">
        <header className="sys-drawer__head">
          <div>
            <p className="sys-drawer__eyebrow">Calculation logic</p>
            <h5 className="sys-drawer__title">{title}</h5>
          </div>
          <button type="button" className="sys-drawer__close" onClick={onClose} aria-label="Close logs">✕</button>
        </header>
        <div className="sys-drawer__body">
          <ol className="sys-log">
            {logs.map((l, i) => (
              <li className="sys-log__row" key={i}>
                <span className="sys-log__index">{String(i + 1).padStart(2, '0')}</span>
                <div className="sys-log__main">
                  <p className="sys-log__step">{l.step}</p>
                  {l.detail && <p className="sys-log__detail">{l.detail}</p>}
                </div>
                {l.value && <span className="sys-log__value">{l.value}</span>}
              </li>
            ))}
          </ol>
        </div>
        <footer className="sys-drawer__foot">
          <span className="sys-drawer__hint">Read-only · generated by the calculation engine</span>
        </footer>
      </aside>
    </div>
  );
}
