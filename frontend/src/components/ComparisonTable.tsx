import type { CSSProperties } from 'react';
import { useAllPairs } from '../hooks/usePairAnalysis';
import { PAIRS, RISK_COLORS, RATE_DECIMALS, VOL_MAX, type Pair } from '../lib/constants';
import { fmtRate, fmtDateTime } from '../lib/format';
import { Card, CardHead, Change } from './ui';

export function ComparisonTable({
  active,
  now,
  onSelect,
  asOf,
}: {
  active: Pair;
  now: Date;
  onSelect: (pair: Pair) => void;
  asOf?: string | null;
}) {
  const results = useAllPairs(asOf);

  return (
    <Card className="table-card">
      <CardHead
        title="Currency Pair Overview"
        hint="Click any row to switch the dashboard"
        right={<span className="hint mono">Snapshot · {fmtDateTime(now)}</span>}
      />
      <table className="pairs-table">
        <thead>
          <tr>
            <th>Pair</th>
            <th>Current Rate</th>
            <th>1D Change</th>
            <th>Volatility</th>
            <th>Risk Level</th>
          </tr>
        </thead>
        <tbody>
          {PAIRS.map((k, i) => {
            const p = results[i]?.data;
            const chip = RISK_COLORS[p?.risk ?? 'LOW'];
            const vol = p?.volatility ?? null;
            const volPct = vol !== null ? Math.min(100, (vol / VOL_MAX) * 100) : 0;
            return (
              <tr
                key={k}
                className={k === active ? 'active' : ''}
                onClick={() => onSelect(k)}
              >
                <td>
                  <span className="pair-cell">
                    <span className="ic">{k.split('/')[0]}</span>
                    <span className="mono">{k}</span>
                  </span>
                </td>
                <td className="tnum mono">{p ? fmtRate(p.rate, RATE_DECIMALS) : '—'}</td>
                <td>{p && p.d1 !== null ? <Change value={p.d1} /> : '—'}</td>
                <td>
                  <span className="vol-bar">
                    <span style={{ width: `${volPct.toFixed(0)}%` }} />
                  </span>
                  <span
                    className="mono tnum"
                    style={{ marginLeft: 8, color: 'var(--text-mute)', fontSize: 12 }}
                  >
                    {vol !== null ? `${vol.toFixed(2)}%` : '—'}
                  </span>
                </td>
                <td>
                  <span className="risk-chip" style={{ ['--chip']: chip.color } as CSSProperties}>
                    <span className="d" />
                    {p?.risk ?? '—'}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}
