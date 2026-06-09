import { usePairAnalysis } from '../hooks/usePairAnalysis';
import { RISK_COLORS, RATE_DECIMALS, type Pair } from '../lib/constants';
import { fmtRate } from '../lib/format';
import { Card, Change, riskVar } from './ui';

export function KpiCards({ pair, asOf }: { pair: Pair; asOf?: string | null }) {
  const { data } = usePairAnalysis(pair, asOf);
  const color = data ? RISK_COLORS[data.risk].color : RISK_COLORS.LOW.color;
  const style = riskVar(color);

  const rate = (v: number | null | undefined) =>
    v === undefined || v === null ? '—' : fmtRate(v, RATE_DECIMALS);

  const change = (v: number | null | undefined) =>
    v === undefined || v === null ? '—' : <Change value={v} />;

  return (
    <section className="kpi-grid">
      <Card className="kpi-card" style={style}>
        <span className="kpi-label">Current Rate</span>
        <span className="kpi-value tnum">{rate(data?.rate)}</span>
        <span className="kpi-foot">
          <span className="mono" style={{ color: 'var(--text-dim)' }}>{pair}</span>
        </span>
      </Card>

      <Card className="kpi-card" style={style}>
        <span className="kpi-label">1-Day Change</span>
        <span className="kpi-value tnum">{data ? change(data.d1) : '—'}</span>
        <span className="kpi-foot"><span style={{ color: 'var(--text-dim)' }}>vs. yesterday</span></span>
      </Card>

      <Card className="kpi-card" style={style}>
        <span className="kpi-label">7-Day Change</span>
        <span className="kpi-value tnum">{data ? change(data.d7) : '—'}</span>
        <span className="kpi-foot"><span style={{ color: 'var(--text-dim)' }}>vs. 7 days ago</span></span>
      </Card>

      <Card className="kpi-card" style={style}>
        <span className="kpi-label">30-Day Change</span>
        <span className="kpi-value tnum">{data ? change(data.d30) : '—'}</span>
        <span className="kpi-foot"><span style={{ color: 'var(--text-dim)' }}>vs. 30 days ago</span></span>
      </Card>

      <Card className="kpi-card" style={style}>
        <span className="kpi-label">Period High</span>
        <span className="kpi-value tnum">{rate(data?.high)}</span>
        <span className="kpi-foot"><span style={{ color: 'var(--text-dim)' }}>30-day max</span></span>
      </Card>

      <Card className="kpi-card" style={style}>
        <span className="kpi-label">Period Low</span>
        <span className="kpi-value tnum">{rate(data?.low)}</span>
        <span className="kpi-foot"><span style={{ color: 'var(--text-dim)' }}>30-day min</span></span>
      </Card>
    </section>
  );
}
