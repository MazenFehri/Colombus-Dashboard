import type { CSSProperties, ReactNode } from 'react';
import { fmtPct } from '../../lib/format';
import './ui.css';

interface CardProps {
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
}

export function Card({ className = '', style, children }: CardProps) {
  return (
    <div className={`card ${className}`.trim()} style={style}>
      {children}
    </div>
  );
}

export function CardHead({
  title,
  hint,
  right,
}: {
  title: string;
  hint?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="card-head">
      <div>
        <h3>{title}</h3>
        {hint != null && <span className="hint">{hint}</span>}
      </div>
      {right}
    </div>
  );
}

/** Coloured ▲/▼ percentage indicator. */
export function Change({ value }: { value: number }) {
  const up = value >= 0;
  return (
    <span className={`change ${up ? 'up' : 'down'} tnum`}>
      <span className="arrow">{up ? '▲' : '▼'}</span>
      {fmtPct(value)}
    </span>
  );
}

/** Helper to set the CSS custom property `--risk-color` without TS complaints. */
export const riskVar = (color: string): CSSProperties =>
  ({ ['--risk-color']: color } as CSSProperties);
