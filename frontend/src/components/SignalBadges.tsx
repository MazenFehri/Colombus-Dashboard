import { usePairAnalysis } from '../hooks/usePairAnalysis';
import { type Pair } from '../lib/constants';

const TREND = {
  bullish: { glyph: '▲', label: 'Bullish', cls: 'sig-up' },
  bearish: { glyph: '▼', label: 'Bearish', cls: 'sig-down' },
  neutral: { glyph: '→', label: 'Neutral', cls: 'sig-flat' },
} as const;

const REGIME = {
  elevated: { label: 'Elevated vol', cls: 'sig-elevated' },
  normal: { label: 'Normal vol', cls: 'sig-normal' },
  compressed: { label: 'Compressed vol', cls: 'sig-compressed' },
} as const;

export function SignalBadges({ pair, asOf }: { pair: Pair; asOf?: string | null }) {
  const { data } = usePairAnalysis(pair, asOf);
  const trend = data?.trend && data.trend in TREND ? TREND[data.trend as keyof typeof TREND] : null;
  const regime = data?.volRegime && data.volRegime in REGIME ? REGIME[data.volRegime as keyof typeof REGIME] : null;

  if (!trend && !regime) return null;

  return (
    <div className="signal-badges">
      {trend && (
        <span className={`signal-pill ${trend.cls}`}>
          <span className="signal-glyph">{trend.glyph}</span> {trend.label}
        </span>
      )}
      {regime && <span className={`signal-pill ${regime.cls}`}>{regime.label}</span>}
    </div>
  );
}
