export const fmtRate = (v: number, dec = 4): string =>
  v.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });

export const fmtPct = (v: number): string => (v >= 0 ? '+' : '') + v.toFixed(2) + '%';

export const fmtDate = (d: Date): string =>
  d.toLocaleDateString('en-US', { month: 'short', day: '2-digit' });

export const fmtTime = (d: Date): string =>
  d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

export const fmtDateTime = (d: Date): string =>
  d.toLocaleDateString('en-GB', { year: 'numeric', month: 'short', day: '2-digit' }) + ' ' + fmtTime(d);
