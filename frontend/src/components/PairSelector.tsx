import { PAIRS, type Pair } from '../lib/constants';

export function PairSelector({
  active,
  onSelect,
}: {
  active: Pair;
  onSelect: (pair: Pair) => void;
}) {
  return (
    <div className="selector-row">
      <span className="selector-label">Currency Pair</span>
      <div className="pill-group" role="tablist">
        {PAIRS.map((k) => {
          const [a, b] = k.split('/');
          return (
            <button
              key={k}
              className={`pill ${k === active ? 'active' : ''}`.trim()}
              type="button"
              role="tab"
              aria-selected={k === active}
              onClick={() => onSelect(k)}
            >
              <span className="flagpair">{a}</span>
              <span style={{ opacity: 0.6 }}>/</span>
              <span style={{ marginLeft: 4 }}>{b}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
