import { usePairAnalysis } from '../hooks/usePairAnalysis';
import { RISK_COLORS, type Pair } from '../lib/constants';
import { fmtPct } from '../lib/format';
import { riskVar } from './ui';

function explain(risk: 'LOW' | 'MEDIUM' | 'HIGH', d1: number): string {
  const abs = Math.abs(d1).toFixed(2);
  if (risk === 'HIGH') return `Daily movement of ${abs}% exceeded the 1.00% high-risk threshold.`;
  if (risk === 'MEDIUM') return `Daily movement of ${abs}% is approaching the 1.00% high-risk threshold.`;
  return `Daily movement of ${abs}% is well within the 1.00% low-risk threshold.`;
}

export function RiskBadge({ pair }: { pair: Pair }) {
  const { data } = usePairAnalysis(pair);
  const risk = data?.risk ?? 'LOW';
  const color = RISK_COLORS[risk].color;

  return (
    <section className="card risk-card" style={riskVar(color)}>
      <div className="risk-badge">{risk}</div>
      <div className="risk-body">
        <div className="risk-eyebrow">Risk Assessment</div>
        <h2 className="risk-title">
          Current alert: <span className="accent">{risk}</span>
        </h2>
        <p className="risk-detail">
          {data
            ? `Daily movement: ${fmtPct(data.d1)}. ${explain(risk, data.d1)}`
            : 'Loading risk assessment…'}
        </p>
      </div>
    </section>
  );
}
