import React, { useState } from 'react';
import { useHedge } from '../hooks/useHedge';
import { ExposureToggle, type Exposure } from './ExposureToggle';
import { type Pair } from '../lib/constants';
import './hedgeadvisor.css';

const SIGNAL_CONFIG = {
  CONSIDER_FORWARD: { icon: '⇒', label: 'Consider Forward',  color: '#F59E0B' },
  SPOT_REASONABLE:  { icon: '✓', label: 'Spot Reasonable',    color: '#22C55E' },
  NEUTRAL:          { icon: '—', label: 'No Strong Signal',   color: '#94A3B8' },
} as const;

type Signal = keyof typeof SIGNAL_CONFIG;

function fmtChg(v: number): string {
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

export function HedgeAdvisor({ pair, asOf }: { pair: Pair; asOf: string | null }) {
  const [exposure, setExposure] = useState<Exposure>('importer');
  const { data, isLoading, isError } = useHedge(pair, exposure, asOf);

  const cfg = data
    ? (SIGNAL_CONFIG[data.signal as Signal] ?? SIGNAL_CONFIG.NEUTRAL)
    : null;

  return (
    <section className="hedge-section" aria-label="Spot vs Forward Advisor">
      <div className="hedge-card">
        {/* Header */}
        <div className="hedge-header">
          <div className="hedge-spark" aria-hidden="true">⇄</div>
          <div className="hedge-title-group">
            <h3 className="hedge-title">Spot vs Forward Advisor</h3>
            <div className="hedge-subtitle">HEDGING GUIDANCE · CIP FORWARD RATES</div>
          </div>
          <span className="hedge-tag">Beta</span>
        </div>

        {/* Exposure toggle */}
        <ExposureToggle value={exposure} onChange={setExposure} />

        {/* States */}
        {isLoading && (
          <div className="hedge-loading">
            <span className="hedge-spinner" />
            Analysing market conditions…
          </div>
        )}

        {isError && (
          <div className="hedge-error">
            ⚠ Hedge advisor unavailable — check backend connection.
          </div>
        )}

        {data && cfg && (
          <>
            {/* Signal badge */}
            <div
              className="hedge-signal"
              style={{ '--signal-color': cfg.color } as React.CSSProperties}
            >
              <span className="hedge-signal__icon">{cfg.icon}</span>
              <div>
                <p className="hedge-signal__label">{cfg.label}</p>
                <p className="hedge-signal__reason">{data.short_reason}</p>
              </div>
            </div>

            {/* CIP Forward rate table — only shown when IRs are available */}
            {data.forward_rates.length > 0 && (
              <div className="hedge-fwd-table">
                <div className="hedge-fwd-header">CIP Forward Rates</div>
                <div className="hedge-fwd-grid">
                  <div className="hedge-fwd-row hedge-fwd-row--spot">
                    <span>Spot</span>
                    <span>{data.spot_rate.toFixed(4)}</span>
                    <span className="fwd-zero">—</span>
                  </div>
                  {data.forward_rates.map((fr) => (
                    <div key={fr.tenor} className="hedge-fwd-row">
                      <span>{fr.tenor}</span>
                      <span>{fr.rate.toFixed(4)}</span>
                      <span className={fr.pct_diff > 0.001 ? 'fwd-premium' : fr.pct_diff < -0.001 ? 'fwd-discount' : 'fwd-zero'}>
                        {fr.pct_diff >= 0 ? '+' : ''}{fr.pct_diff.toFixed(2)}%
                      </span>
                    </div>
                  ))}
                </div>
                <p className="hedge-fwd-note">
                  Computed via covered interest parity — TND 7.00%, USD 3.70%, EUR 2.10%.
                  Indicative only; actual bank forwards include spread and credit adjustments.
                </p>
              </div>
            )}

            {/* Stats row */}
            <div className="hedge-stats">
              <div className="hedge-stat">
                <span className="hedge-stat__label">Spot Rate</span>
                <span className="hedge-stat__value">{data.spot_rate.toFixed(4)}</span>
              </div>
              <div className="hedge-stat">
                <span className="hedge-stat__label">30d Change</span>
                <span className="hedge-stat__value">{fmtChg(data.change_30d)}</span>
              </div>
              <div className="hedge-stat">
                <span className="hedge-stat__label">Ann. Vol</span>
                <span className="hedge-stat__value">{(data.volatility * 100).toFixed(1)}%</span>
              </div>
              <div className="hedge-stat">
                <span className="hedge-stat__label">Risk</span>
                <span className="hedge-stat__value">{data.risk_level.toUpperCase()}</span>
              </div>
            </div>

            {/* AI narrative */}
            <div className="hedge-narrative">
              <div className="hedge-narrative__eyebrow">AI Advisory</div>
              <p className="hedge-narrative__text">{data.narrative}</p>
            </div>

            {/* Disclaimer */}
            <div className="hedge-disclaimer">
              Educational guidance only — not financial advice. Forward rates are indicative
              CIP estimates and do not account for bank spreads, credit risk, or regulatory constraints.
            </div>
          </>
        )}
      </div>
    </section>
  );
}
