import { endpoints } from './endpoints';
import { splitPair, type Risk } from '../lib/constants';
import { rangeFrom, isoDay, parseDay } from '../lib/dates';
import { fixtures } from './mocks/fixtures';

// Toggle: when VITE_USE_MOCKS is "true", serve hardcoded fixtures instead of
// hitting the backend. Lets the UI run fully standalone.
const USE_MOCKS = String(import.meta.env.VITE_USE_MOCKS ?? '').toLowerCase() === 'true';

// ----- Raw backend response shapes (mirror app/schemas.py) -----
export interface RatePoint { date: string; rate: number; }
interface Commentary { commentary: string; date: string; cached: boolean; }
export interface NewsArticle {
  title: string;
  url: string;
  source: string;
  published_at: string | null;
  language: string;
  is_top: boolean;
  explanation: string | null;
}
export interface NewsResponse {
  base: string;
  quote: string;
  date: string;
  top: NewsArticle[];
  more: NewsArticle[];
}

// Raw snapshot response (mirrors app/schemas.py SnapshotOut).
interface Snapshot {
  resolved_date: string;
  rate: number;
  d1: number | null;
  d7: number | null;
  d30: number | null;
  high: number;
  low: number;
  volatility: number | null; // rolling_21d_std (daily)
  risk: string;
}

// ----- Aggregated, UI-friendly per-pair snapshot -----
export interface PairAnalysis {
  rate: number;
  d1: number | null;
  d7: number | null;
  d30: number | null;
  high: number;
  low: number;
  volatility: number | null; // daily %, derived from rolling_21d_std * 100
  risk: Risk;
  resolvedDate: string;
}

async function jget<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
  return (await r.json()) as T;
}

/**
 * Pull the dashboard's per-pair metrics in a single consolidated snapshot
 * request. `asOf` (YYYY-MM-DD) time-travels to a historical date; omit it for
 * the live (today) snapshot.
 */
export async function fetchPairAnalysis(pair: string, asOf?: string): Promise<PairAnalysis> {
  if (USE_MOCKS) return fixtures.analysis(pair);
  const { base, quote } = splitPair(pair);
  const s = await jget<Snapshot>(endpoints.snapshot(base, quote, asOf));
  return {
    rate: s.rate,
    d1: s.d1,
    d7: s.d7,
    d30: s.d30,
    high: s.high,
    low: s.low,
    volatility: s.volatility === null ? null : Number((s.volatility * 100).toFixed(2)),
    risk: (s.risk || 'low').toUpperCase() as Risk,
    resolvedDate: s.resolved_date,
  };
}

/**
 * Historical rate series for the chart over the last `days` days. When `asOf`
 * (YYYY-MM-DD) is supplied the trailing window ends at that date instead of today.
 */
export async function fetchHistory(pair: string, days: number, asOf?: string): Promise<RatePoint[]> {
  if (USE_MOCKS) return fixtures.history(pair, days);
  const { base, quote } = splitPair(pair);
  const { from, to } = rangeFrom(days, asOf ? parseDay(asOf) : undefined);
  return jget<RatePoint[]>(endpoints.rates(base, quote, from, to));
}

/** News for a pair on a given day (top + more). */
export async function fetchNews(pair: string, day: string): Promise<NewsResponse> {
  if (USE_MOCKS) return fixtures.news(pair, day);
  const { base, quote } = splitPair(pair);
  return jget<NewsResponse>(endpoints.news(base, quote, day));
}

/** AI market commentary for the pair (generated server-side, cached per day). */
export async function fetchCommentary(pair: string): Promise<string> {
  if (USE_MOCKS) return fixtures.commentary(pair);
  const { base, quote } = splitPair(pair);
  const r = await fetch(endpoints.commentary(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ base, quote, date: isoDay(new Date()) }),
  });
  if (!r.ok) throw new Error(`POST commentary -> ${r.status}`);
  return ((await r.json()) as Commentary).commentary;
}
