import { endpoints } from './endpoints';
import { splitPair, type Risk } from '../lib/constants';
import { rangeFrom, isoDay, parseDay } from '../lib/dates';
import { fixtures } from './mocks/fixtures';
import { authHeaders, tokenStore } from '../auth/api';

// Toggle: when VITE_USE_MOCKS is "true", serve hardcoded fixtures instead of
// hitting the backend. Lets the UI run fully standalone.
const USE_MOCKS = String(import.meta.env.VITE_USE_MOCKS ?? '').toLowerCase() === 'true';

// ----- Raw backend response shapes (mirror app/schemas.py) -----
export interface RatePoint { date: string; rate: number; }
interface Commentary { commentary: string; date: string; cached: boolean; headlines: Headline[]; }
export interface Headline { headline: string; source: string; url: string; }
export interface CommentaryResult { commentary: string; headlines: Headline[]; }
export interface NewsArticle {
  headline: string;
  source: string;
  url: string;
  published_at: string | null;
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
  trend: string | null;
  vol_regime: string | null;
  momentum: number | null;
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
  trend: string | null;
  volRegime: string | null;
  momentum: number | null;
  risk: Risk;
  resolvedDate: string;
}

async function jget<T>(url: string): Promise<T> {
  const r = await fetch(url, { headers: authHeaders() });
  if (r.status === 401) { tokenStore.clear(); location.reload(); throw new Error('Unauthorized'); }
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
    trend: s.trend,
    volRegime: s.vol_regime,
    momentum: s.momentum,
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

/** Latest news articles for the pair (live/today, not time-travelled). */
export async function fetchNews(pair: string): Promise<NewsResponse> {
  const { base, quote } = splitPair(pair);
  const day = isoDay(new Date());
  if (USE_MOCKS) return fixtures.news(pair, day) as NewsResponse;
  return jget<NewsResponse>(endpoints.news(base, quote, day));
}

// ----- Hedge recommendation types -----
export interface ForwardRateData { tenor: string; rate: number; pct_diff: number; }
export interface HedgeResult {
  signal: string;
  short_reason: string;
  narrative: string;
  exposure: string;
  as_of: string;
  spot_rate: number;
  change_30d: number;
  volatility: number;
  risk_level: string;
  forward_rates: ForwardRateData[];
}

/** AI market commentary for the pair, plus the headlines that informed it. */
export async function fetchCommentary(pair: string): Promise<CommentaryResult> {
  if (USE_MOCKS) return { commentary: fixtures.commentary(pair), headlines: [] };
  const { base, quote } = splitPair(pair);
  const r = await fetch(endpoints.commentary(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ base, quote, date: isoDay(new Date()) }),
  });
  if (!r.ok) throw new Error(`POST commentary -> ${r.status}`);
  const data = (await r.json()) as Commentary;
  return { commentary: data.commentary, headlines: data.headlines ?? [] };
}

/** Spot-vs-forward recommendation: heuristic signal + CIP forward rates + AI narrative. */
export async function fetchHedge(pair: string, exposure: string, asOf?: string): Promise<HedgeResult> {
  const { base, quote } = splitPair(pair);
  return jget<HedgeResult>(endpoints.hedge(base, quote, exposure, asOf));
}

/** Email the current user the 4-pair news digest for today. */
export async function emailNews(): Promise<{ sent: boolean; to: string }> {
  const r = await fetch(endpoints.emailNews(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({}),
  });
  if (!r.ok) throw new Error(`POST email -> ${r.status}`);
  return (await r.json()) as { sent: boolean; to: string };
}
