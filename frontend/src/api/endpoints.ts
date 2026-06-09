// All endpoint URLs for the FastAPI backend, built from VITE_API_BASE.
// In dev, Vite proxies this base to http://127.0.0.1:8000 (see vite.config.ts).
const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api/v1';

export const endpoints = {
  currencies: () => `${BASE}/currencies`,
  rates: (b: string, q: string, from: string, to: string) =>
    `${BASE}/rates/${b}/${q}?from_date=${from}&to_date=${to}`,
  dailyChange: (b: string, q: string) => `${BASE}/rates/${b}/${q}/daily-change`,
  performance: (b: string, q: string, period: 'weekly' | 'monthly') =>
    `${BASE}/rates/${b}/${q}/performance?period=${period}`,
  highLow: (b: string, q: string) => `${BASE}/rates/${b}/${q}/high-low`,
  volatility: (b: string, q: string) => `${BASE}/rates/${b}/${q}/volatility`,
  snapshot: (b: string, q: string, asOf?: string) =>
    `${BASE}/analysis/${b}/${q}/snapshot${asOf ? `?as_of=${asOf}` : ''}`,
  alert: (b: string, q: string) => `${BASE}/alerts/${b}/${q}`,
  commentary: () => `${BASE}/ai/commentary`,
  news: (b: string, q: string, date: string) =>
    `${BASE}/news/${b}/${q}?date=${date}`,
};
