
import './Colombus-Dashboard/featurehedge/exposuretoggle.css';

export type Exposure = 'importer' | 'exporter';

interface Props {
  value: Exposure;
  onChange: (v: Exposure) => void;
}

const HINTS: Record<Exposure, string> = {
  importer: 'You buy foreign currency, a rising rate costs you more.',
  exporter: 'You receive foreign currency, a falling rate earns you less.',
};

export function ExposureToggle({ value, onChange }: Props) {
  return (
    <div className="exposure-row" role="group" aria-label="Business exposure direction">
      <span className="exposure-label">I am an</span>

      <div className="exposure-toggle">
        {(['importer', 'exporter'] as Exposure[]).map((opt) => (
          <button
            key={opt}
            className={`exposure-btn${value === opt ? ' exposure-btn--active' : ''}`}
            onClick={() => onChange(opt)}
            aria-pressed={value === opt}
          >
            {opt === 'importer' ? ' Importer' : ' Exporter'}
          </button>
        ))}
      </div>

      <span className="exposure-hint">{HINTS[value]}</span>
    </div>
  );
}