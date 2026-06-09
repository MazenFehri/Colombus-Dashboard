export const PAIRS = ['EUR/USD', 'GBP/USD', 'USD/TND', 'EUR/TND'] as const;
export type Pair = (typeof PAIRS)[number];

export type Risk = 'LOW' | 'MEDIUM' | 'HIGH';

export const RISK_COLORS: Record<Risk, { color: string; label: string; desc: string }> = {
  LOW:    { color: '#22C55E', label: 'Low risk',    desc: 'Daily movement within normal range' },
  MEDIUM: { color: '#F59E0B', label: 'Medium risk', desc: 'Daily movement approaching threshold' },
  HIGH:   { color: '#EF4444', label: 'High risk',   desc: 'Daily movement exceeded 1% threshold' },
};

/** Rates are shown to 4 decimals; percentages to 2. */
export const RATE_DECIMALS = 4;

/** Earliest date with rate data (Frankfurter coverage start). */
export const DATA_START = '2020-04-09';

/** Ceiling (in daily %) for the volatility gauge. */
export const VOL_MAX = 1.5;

export function splitPair(pair: string): { base: string; quote: string } {
  const [base, quote] = pair.split('/');
  return { base, quote };
}
