import { usePairAnalysis } from '../hooks/usePairAnalysis';
import { RISK_COLORS, VOL_MAX, type Pair } from '../lib/constants';
import { Card, CardHead, riskVar } from './ui';

const ARC = 267; // length of the semicircle arc (π * r, r = 85)

export function VolatilityGauge({ pair }: { pair: Pair }) {
  const { data } = usePairAnalysis(pair);
  const vol = data?.volatility ?? 0;
  const risk = data?.risk ?? 'LOW';
  const color = RISK_COLORS[risk].color;

  const pct = Math.max(0, Math.min(1, vol / VOL_MAX));
  const dashoffset = (ARC * (1 - pct)).toFixed(2);
  const deg = -90 + pct * 180;

  const status =
    risk === 'HIGH'
      ? 'Elevated volatility — review hedging positions'
      : risk === 'MEDIUM'
        ? 'Moderate volatility — monitor closely'
        : 'Stable conditions — within normal range';

  return (
    <Card className="vol-card" style={riskVar(color)}>
      <CardHead title="Volatility Index" hint="Standard deviation, annualized %" />

      <div className="gauge-wrap">
        <svg viewBox="0 0 200 120" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
          <defs>
            <linearGradient id="gaugeGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#22C55E" />
              <stop offset="55%" stopColor="#F59E0B" />
              <stop offset="100%" stopColor="#EF4444" />
            </linearGradient>
          </defs>
          <path
            d="M 15 105 A 85 85 0 0 1 185 105"
            fill="none"
            stroke="var(--bg-soft)"
            strokeWidth="14"
            strokeLinecap="round"
          />
          <path
            d="M 15 105 A 85 85 0 0 1 185 105"
            fill="none"
            stroke="url(#gaugeGrad)"
            strokeWidth="14"
            strokeLinecap="round"
            strokeDasharray={ARC}
            strokeDashoffset={dashoffset}
            style={{ transition: 'stroke-dashoffset 600ms cubic-bezier(.4,0,.2,1)' }}
          />
          <g
            style={{
              transition: 'transform 600ms cubic-bezier(.4,0,.2,1)',
              transformOrigin: '100px 105px',
              transform: `rotate(${deg}deg)`,
            }}
          >
            <line x1="100" y1="80" x2="100" y2="32" stroke="var(--text)" strokeWidth="2" strokeLinecap="round" />
            <circle cx="100" cy="80" r="4" fill="var(--surface)" stroke="var(--text)" strokeWidth="2" />
          </g>
        </svg>
        <div className="gauge-readout">
          <div className="num">
            <span className="tnum">{vol.toFixed(2)}</span>
            <span className="pct">%</span>
          </div>
          <div className="lbl">Daily volatility</div>
        </div>
      </div>

      <div className="gauge-legend">
        <span>STABLE</span>
        <span>MODERATE</span>
        <span>VOLATILE</span>
      </div>
      <div className="vol-status">
        <span className="dot" />
        <span>{status}</span>
      </div>
    </Card>
  );
}
