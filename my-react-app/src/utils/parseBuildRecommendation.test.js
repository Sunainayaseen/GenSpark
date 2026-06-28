import { describe, it, expect } from 'vitest';
import {
  parseBuildRecommendationMarkdown,
  formatPkr,
  clarifyIntegratedGraphicsMarkdown,
} from './parseBuildRecommendation';

const SAMPLE_BUILD_MARKDOWN = `Compatibility Status:** Validated — No bottleneck found
PSU Wattage Buffer: 120 W
Performance Score: 82/100
Estimated parts total: 165,000 PKR
Tier: A

## Recommended Components
| Type | Name | Price |
|------|------|-------|
| CPU | Ryzen 5 5600 | 45,000 |
| GPU | RTX 4060 | 120,000 |

## Summary
This build offers great gaming performance for the budget.

## Reasoning
- Balanced budget allocation
- No bottlenecks detected
`;

describe('parseBuildRecommendationMarkdown', () => {
  it('returns isBuildRecommendation: false for plain chat text', () => {
    const result = parseBuildRecommendationMarkdown('Sure, what is your budget?');
    expect(result.isBuildRecommendation).toBe(false);
    expect(result.remainderMarkdown).toBe('Sure, what is your budget?');
  });

  it('returns isBuildRecommendation: false for empty input', () => {
    expect(parseBuildRecommendationMarkdown('')).toEqual({
      isBuildRecommendation: false,
      remainderMarkdown: '',
    });
  });

  it('parses a full build recommendation into stats, parts, summary, and reasoning', () => {
    const result = parseBuildRecommendationMarkdown(SAMPLE_BUILD_MARKDOWN);

    expect(result.isBuildRecommendation).toBe(true);

    expect(result.stats).toMatchObject({
      compatibility: 'Validated',
      bottleneck: 'No bottleneck found',
      psuWatts: 120,
      performanceScore: 82,
      totalPkr: '165000',
      tier: 'A',
    });

    expect(result.parts).toEqual([
      { type: 'CPU', name: 'Ryzen 5 5600', price: '45,000' },
      { type: 'GPU', name: 'RTX 4060', price: '120,000' },
    ]);

    expect(result.summary).toBe('This build offers great gaming performance for the budget.');
    expect(result.reasoning).toEqual(['Balanced budget allocation', 'No bottlenecks detected']);
  });
});

describe('formatPkr', () => {
  it('formats a plain number with international (not lakh) grouping', () => {
    expect(formatPkr(189000)).toBe('189,000');
  });

  it('round-trips an already-comma-formatted string', () => {
    expect(formatPkr('45,000')).toBe('45,000');
  });

  it('falls back to the raw input for non-numeric values', () => {
    expect(formatPkr('TBD')).toBe('TBD');
  });
});

describe('clarifyIntegratedGraphicsMarkdown', () => {
  it('relabels a zero-priced GPU row as "Included" with a descriptive name', () => {
    const input = '| GPU | - | 0 |';
    const output = clarifyIntegratedGraphicsMarkdown(input);
    expect(output).toBe('| GPU | Integrated graphics (CPU) | Included |');
  });

  it('leaves a normally-priced GPU row untouched', () => {
    const input = '| GPU | RTX 4060 | 120,000 |';
    expect(clarifyIntegratedGraphicsMarkdown(input)).toBe(input);
  });

  it('leaves non-table lines untouched', () => {
    const input = 'Just a plain sentence about graphics.';
    expect(clarifyIntegratedGraphicsMarkdown(input)).toBe(input);
  });

  it('leaves the header row untouched', () => {
    const input = '| Type | Name | Price |';
    expect(clarifyIntegratedGraphicsMarkdown(input)).toBe(input);
  });
});
