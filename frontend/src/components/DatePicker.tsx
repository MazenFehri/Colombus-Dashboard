import { useState } from 'react';
import { isoDay, parseDay } from '../lib/dates';

const DATA_START = '2020-04-09';

/** Weekend = Saturday (6) or Sunday (0) in local terms. */
function isWeekend(iso: string): boolean {
  const day = parseDay(iso).getDay();
  return day === 0 || day === 6;
}

/**
 * Date "time-travel" control. Native date input bounded to the available data
 * range; weekend selections are rejected (the backend has no weekend rows) with
 * an inline hint, since a native date input cannot grey out specific weekdays.
 * A "Live / Today" button clears back to live.
 */
export function DatePicker({
  asOf,
  onChange,
}: {
  asOf: string | null;
  onChange: (asOf: string | null) => void;
}) {
  const today = isoDay(new Date());
  const [hint, setHint] = useState(false);

  const handleChange = (value: string) => {
    if (!value) {
      setHint(false);
      onChange(null);
      return;
    }
    // Weekends have no data — ignore the selection rather than re-anchor to a hole,
    // and surface why so the input doesn't appear to silently snap back.
    if (isWeekend(value)) {
      setHint(true);
      return;
    }
    setHint(false);
    onChange(value);
  };

  return (
    <div className="date-travel">
      <label className="date-travel-label" htmlFor="asof-input">
        As of date
      </label>
      <input
        id="asof-input"
        type="date"
        className="date-travel-input"
        min={DATA_START}
        max={today}
        value={asOf ?? today}
        onChange={(e) => handleChange(e.target.value)}
      />
      <button
        type="button"
        className="date-travel-live"
        onClick={() => {
          setHint(false);
          onChange(null);
        }}
        disabled={asOf === null}
      >
        Live / Today
      </button>
      {hint && (
        <span className="date-travel-hint" role="status">
          Markets are closed on weekends — pick a weekday.
        </span>
      )}
    </div>
  );
}
