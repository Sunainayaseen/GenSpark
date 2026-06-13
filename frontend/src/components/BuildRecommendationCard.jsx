import { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  parseBuildRecommendationMarkdown,
  clarifyIntegratedGraphicsMarkdown,
  formatPkr,
} from '../utils/parseBuildRecommendation';
import { checkBuildCompatibility } from '../utils/buildCompatibility';
import './BuildRecommendationCard.css';

const CHECK_ICON = { pass: '✓', fail: '✗', warn: '⚠', skip: '–' };

export default function BuildRecommendationCard({
  markdown,
  purpose,
  budget,
  buildComponents = null,
  compatibility = null,
  onAddToCart = null,
  adding = false,
  // When an editable customizer renders the parts table + cart below, suppress the
  // card's own static parts table and cart CTA to avoid a duplicate, stale copy.
  editable = false,
}) {
  const md = useMemo(() => clarifyIntegratedGraphicsMarkdown(markdown), [markdown]);
  const parsed = useMemo(() => parseBuildRecommendationMarkdown(md), [md]);
  // Long sections stay collapsed by default — keep the card short & scannable.
  const [showChecks, setShowChecks] = useState(false);
  const [showWhy, setShowWhy] = useState(false);
  const [showSummary, setShowSummary] = useState(false);
  const addableCount = Array.isArray(buildComponents)
    ? buildComponents.filter((c) => c?.component_id ?? c?.id).length
    : 0;
  const canAdd = typeof onAddToCart === 'function' && addableCount > 0;

  if (!parsed.isBuildRecommendation || !parsed.stats) {
    return (
      <div className="build-rec-fallback ai-recommendation-markdown chat-markdown">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{md}</ReactMarkdown>
      </div>
    );
  }

  const { stats, summary, parts, reasoning } = parsed;
  const totalDisplay = stats.totalPkr ? formatPkr(stats.totalPkr) : null;
  const compat = checkBuildCompatibility(parts);

  // Prefer the backend's deterministic rule-based verdict; fall back to the
  // client-side name heuristic only when the API didn't return one.
  const backend =
    compatibility && Array.isArray(compatibility.checks) ? compatibility : null;
  const score = backend ? backend.score : compat.score;
  const hasConflict = backend ? !backend.compatible : compat.hasConflict;
  const verdictText = backend
    ? backend.compatible
      ? 'Compatible · validated by rule engine'
      : 'Incompatible — see checks below'
    : compat.verdict;
  const checks = backend ? backend.checks : [];
  const failures = backend ? backend.failures || [] : [];

  return (
    <article className="build-rec-premium" aria-label="PC build recommendation">
      <div className="build-rec-top">
        {totalDisplay ? (
          <div className="build-rec-total-card">
            <span className="build-rec-total-label">Estimated build total</span>
            <p className="build-rec-total-amount">
              <span className="build-rec-total-currency">PKR</span>
              {totalDisplay}
            </p>
            {(purpose || budget) && (
              <p className="build-rec-total-meta">
                {purpose ? <span>{purpose}</span> : null}
                {budget ? <span>Target {budget}</span> : null}
              </p>
            )}
          </div>
        ) : null}
      </div>

      <section className="build-rec-compat">
        <div className="build-rec-compat-head">
          <span className="build-rec-compat-title">
            Compatibility score
            {backend ? <span className="build-rec-compat-engine"> · rule-based</span> : null}
          </span>
          <span className={`build-rec-compat-pct ${hasConflict ? 'is-warn' : 'is-ok'}`}>
            {score}%
          </span>
        </div>
        <div className="build-rec-compat-bar">
          <div
            className={`build-rec-compat-fill ${hasConflict ? 'is-warn' : 'is-ok'}`}
            style={{ width: `${score}%` }}
          />
        </div>
        <span className="build-rec-compat-verdict">{verdictText}</span>
      </section>

      {backend ? (
        <section className="build-rec-section build-rec-checks">
          <button
            type="button"
            className={`build-rec-collapse ${hasConflict ? 'is-warn' : 'is-ok'}`}
            onClick={() => setShowChecks((s) => !s)}
            aria-expanded={showChecks}
          >
            <span className="build-rec-collapse-label">
              {hasConflict
                ? `⚠ ${failures.length} compatibility issue${failures.length === 1 ? '' : 's'}`
                : `✓ All ${checks.length} compatibility checks passed`}
            </span>
            <span className="build-rec-collapse-caret">{showChecks ? 'Hide' : 'Details'}</span>
          </button>
          {/* Issues are always visible; the full passing list hides behind the toggle. */}
          {failures.length > 0 ? (
            <ul className="build-rec-checks-failures">
              {failures.map((f, i) => (
                <li key={`f-${i}`}>
                  <strong>✗ {f.rule}:</strong> {f.detail}
                  {Array.isArray(f.suggestions) && f.suggestions.length > 0 ? (
                    <span className="build-rec-checks-alts">
                      {' '}Alternatives: {f.suggestions.slice(0, 3).join(', ')}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
          {showChecks ? (
            <ul className="build-rec-checks-list">
              {checks.map((c, i) => (
                <li key={`c-${i}`} className={`build-rec-check is-${c.status}`}>
                  <span className="build-rec-check-icon" aria-hidden>
                    {CHECK_ICON[c.status] || '•'}
                  </span>
                  <span className="build-rec-check-rule">{c.rule}</span>
                  <span className="build-rec-check-detail">{c.detail}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      {summary ? (
        <section className="build-rec-section">
          <p className={`build-rec-summary-text ${showSummary ? '' : 'is-clamped'}`}>{summary}</p>
          {summary.length > 160 ? (
            <button type="button" className="build-rec-morelink" onClick={() => setShowSummary((s) => !s)}>
              {showSummary ? 'Show less' : 'Read more'}
            </button>
          ) : null}
        </section>
      ) : null}

      {parts.length > 0 && !editable ? (
        <section className="build-rec-section">
          <h3 className="build-rec-section-title">Recommended components</h3>
          <div className="build-rec-table-wrap">
            <table className="build-rec-table">
              <thead>
                <tr>
                  <th scope="col">Part</th>
                  <th scope="col">Selection</th>
                  <th scope="col" className="col-status">Status</th>
                  <th scope="col">Price (PKR)</th>
                </tr>
              </thead>
              <tbody>
                {parts.map((row) => {
                  const st = compat.statusByType[row.type];
                  const bad = st?.ok === false;
                  return (
                    <tr key={row.type} className={bad ? 'is-conflict' : ''}>
                      <td>{row.type}</td>
                      <td>{row.name}</td>
                      <td className="col-status">
                        <span
                          className={`build-rec-status ${bad ? 'is-bad' : 'is-good'}`}
                          title={bad ? st?.note : 'Compatible'}
                        >
                          {bad ? '✗' : '✓'}
                        </span>
                      </td>
                      <td>{row.price === '0' ? '—' : formatPkr(row.price)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {reasoning.length > 0 ? (
        <section className="build-rec-section build-rec-section--reasoning">
          <button
            type="button"
            className="build-rec-collapse"
            onClick={() => setShowWhy((s) => !s)}
            aria-expanded={showWhy}
          >
            <span className="build-rec-collapse-label">Why we recommend this build</span>
            <span className="build-rec-collapse-caret">{showWhy ? 'Hide' : 'Show'}</span>
          </button>
          {showWhy ? (
            <ul className="build-rec-reasoning-list">
              {reasoning.map((item, i) => (
                <li key={i}>{item.replace(/\*\*/g, '')}</li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      {canAdd && !editable ? (
        <section className="build-rec-cta">
          <button
            type="button"
            className="build-rec-cta-btn"
            onClick={() => onAddToCart(buildComponents)}
            disabled={adding}
          >
            {adding ? (
              <span className="build-rec-cta-spinner" aria-hidden />
            ) : (
              <span className="build-rec-cta-icon" aria-hidden>🛒</span>
            )}
            {adding ? 'Adding to cart…' : `Add full build to cart (${addableCount} parts)`}
          </button>
          <span className="build-rec-cta-hint">
            Real inventory · vendor auto-assigned at checkout
          </span>
        </section>
      ) : null}
    </article>
  );
}
