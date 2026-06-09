import { endpoints } from './endpoints';
import { splitPair, type Risk } from '../lib/constants';
import { rangeFrom, isoDay } from '../lib/dates';
import { fixtures } from './mocks/fixtures';

// Toggle: when VITE_USE_MOCKS is "true", serve hardcoded fixtures instead of
// hitting the backend. Lets the UI run fully standalone.
const USE_MOCKS = String(import.meta.env.VITE_USE_MOCKS ?? '').toLowerCase() === 'true';

// ----- Raw backend response shapes (mirror app/schemas.py) -----
export interface RatePoint { date: string; rate: number; }
interface DailyChange { date: string; rate: number; prev_rate: number; change_pct: number; }
interface Performance { period: string; start_date: string; end_date: string; start_rate: number; end_rate: number; change_pct: number; }
interface HighLow { high: number; high_date: string; low: number; low_date: string; }
interface Volatility { rolling_21d_std: number; annualized_vol: number; latest_date: string; }
interface Alert { date: string; risk_level: string; change_pct: number; message: string; }
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

// ----- Aggregated, UI-friendly per-pair snapshot -----
export interface PairAnalysis {
  rate: number;
  d1: number;
  d7: number;
  d30: number;
  high: number;
  low: number;
  volatility: number; // daily %, derived from rolling_21d_std * 100
  risk: Risk;
}

async function jget<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
  return (await r.json()) as T;
}

/**
 * Pull every metric the dashboard needs for one pair and fold the separate
 * backend endpoints into a single snapshot the components consume.
 */
export async function fetchPairAnalysis(pair: string): Promise<PairAnalysis> {
  if (USE_MOCKS) return fixtures.analysis(pair);
  const { base, quote } = splitPair(pair);
  const [dc, wk, mo, hl, vol, alert] = await Promise.all([
    jget<DailyChange>(endpoints.dailyChange(base, quote)),
    jget<Performance>(endpoints.performance(base, quote, 'weekly')),
    jget<Performance>(endpoints.performance(base, quote, 'monthly')),
    jget<HighLow>(endpoints.highLow(base, quote)),
    jget<Volatility>(endpoints.volatility(base, quote)).catch(() => null), // needs >= 21 days
    jget<Alert>(endpoints.alert(base, quote)),
  ]);
  return {
    rate: dc.rate,
    d1: dc.change_pct,
    d7: wk.change_pct,
    d30: mo.change_pct,
    high: hl.high,
    low: hl.low,
    volatility: vol ? Number((vol.rolling_21d_std * 100).toFixed(2)) : 0,
    risk: (alert.risk_level || 'low').toUpperCase() as Risk,
  };
}

/** Historical rate series for the chart over the last `days` days. */
export async function fetchHistory(pair: string, days: number): Promise<RatePoint[]> {
  if (USE_MOCKS) return fixtures.history(pair, days);
  const { base, quote } = splitPair(pair);
  const { from, to } = rangeFrom(days);
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
