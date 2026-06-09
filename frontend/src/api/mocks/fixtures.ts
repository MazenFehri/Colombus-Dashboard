import type { PairAnalysis, RatePoint } from '../client';
import { isoDay } from '../../lib/dates';

// Hardcoded fallback data so the UI can run without a backend
// (enable with VITE_USE_MOCKS=true). Numbers mirror the design spec.
const DATA: Record<string, Omit<PairAnalysis, 'resolvedDate'> & { ai: string }> = {
  'EUR/USD': {
    rate: 1.0842, d1: 0.31, d7: -0.82, d30: 1.24, high: 1.0951, low: 1.0701, volatility: 0.42, risk: 'LOW',
    ai: 'The Euro shows modest daily appreciation against the US Dollar, supported by stable ECB policy signals. Volatility remains within normal bounds at 0.42%, indicating low short-term FX risk for European-exposed corporate clients. Companies with USD payment obligations may consider this a favorable window for hedging.',
  },
  'GBP/USD': {
    rate: 1.2734, d1: -1.23, d7: -0.55, d30: 2.10, high: 1.2910, low: 1.2580, volatility: 1.31, risk: 'HIGH',
    ai: 'Sterling has recorded a sharp 1.23% decline against the Dollar today, driven by weaker UK manufacturing data and renewed dollar strength. With daily movement breaching the 1% high-risk threshold and volatility at 1.31%, corporate clients with GBP exposure should exercise caution and review open positions. A continued bearish trend is possible in the short term.',
  },
  'USD/TND': {
    rate: 3.1764, d1: 0.08, d7: 0.22, d30: 0.61, high: 3.1900, low: 3.1540, volatility: 0.15, risk: 'LOW',
    ai: "The Tunisian Dinar remains broadly stable against the US Dollar, with daily movement of just 0.08% — well within the low-risk threshold. The Central Bank of Tunisia's managed exchange rate policy continues to limit volatility. This pair presents minimal FX risk for import/export operations denominated in USD.",
  },
  'EUR/TND': {
    rate: 3.4428, d1: 0.74, d7: -0.31, d30: 1.87, high: 3.4750, low: 3.3900, volatility: 0.68, risk: 'MEDIUM',
    ai: 'EUR/TND is showing moderate movement of 0.74% today, placing it in the medium-risk category. While not alarming, the trend suggests mild Euro strength that could slightly increase the cost of Euro-denominated imports for Tunisian businesses. Clients should monitor this pair over the next 48 hours.',
  },
};

function seedRand(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function genHistory(pair: string, days: number): RatePoint[] {
  const p = DATA[pair];
  const seed = [...pair].reduce((a, c) => a * 31 + c.charCodeAt(0), 7) + days;
  const rand = seedRand(seed);
  const start = p.rate / (1 + (p.d30 ?? 0) / 100);
  const end = p.rate;
  const step = (end - start) / (days - 1);
  const sigma = ((p.volatility ?? 0) / 100) * p.rate * 0.55;
  const out: RatePoint[] = [];
  let val = start;
  const today = new Date();
  for (let i = 0; i < days; i++) {
    const target = start + step * i;
    val += (target - val) * 0.35 + (rand() - 0.5) * 2 * sigma;
    const d = new Date(today);
    d.setDate(today.getDate() - (days - 1 - i));
    out.push({ date: isoDay(d), rate: i === days - 1 ? end : val });
  }
  return out;
}

export const fixtures = {
  analysis(pair: string): PairAnalysis {
    const { ai: _ai, ...rest } = DATA[pair];
    return { ...rest, resolvedDate: isoDay(new Date()) };
  },
  commentary(pair: string): string {
    return DATA[pair].ai;
  },
  history(pair: string, days: number): RatePoint[] {
    return genHistory(pair, days);
  },
  news(pair: string, day: string) {
    return {
      base: pair.split('/')[0],
      quote: pair.split('/')[1],
      date: day,
      top: [
        { title: `${pair} steadies as central banks hold`, url: 'https://example.com/1',
          source: 'example.com', published_at: `${day}T10:00:00`, language: 'english', is_top: true,
          explanation: `The latest moves around ${pair} were driven by central-bank signals, nudging the pair this session.` },
      ],
      more: [
        { title: `Markets weigh ${pair} outlook`, url: 'https://example.com/2',
          source: 'example.com', published_at: `${day}T08:00:00`, language: 'english', is_top: false,
          explanation: null },
      ],
    };
  },
};
