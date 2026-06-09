import { usePairAnalysis } from '../hooks/usePairAnalysis';
import { fmtDate } from '../lib/format';
import { parseDay } from '../lib/dates';
import { type Pair } from '../lib/constants';

/**
 * "As of {resolved_date}" indicator shown when the dashboard is time-travelled.
 * If the server resolved to a different (earlier) trading day than the picked
 * date — e.g. a holiday — it appends a subtle "nearest trading day" note.
 */
export function AsOfBadge({ pair, asOf }: { pair: Pair; asOf: string }) {
  const { data } = usePairAnalysis(pair, asOf);
  const resolved = data?.resolvedDate ?? asOf;
  const fellBack = resolved !== asOf;

  return (
    <div className="asof-badge" role="status">
      <span className="asof-dot" aria-hidden="true" />
      As of {fmtDate(parseDay(resolved))}
      {fellBack && <span className="asof-note"> · nearest trading day</span>}
    </div>
  );
}
