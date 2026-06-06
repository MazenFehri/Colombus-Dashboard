import { fmtTime } from '../../lib/format';

export function Header({
  now,
  theme,
  onToggleTheme,
}: {
  now: Date;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
}) {
  return (
    <header className="app-header">
      <div className="header-inner">
        <div className="title-block">
          <h1>
            FX Risk Alert <span className="accent-coral">Dashboard</span>
          </h1>
          <span className="sub">Real-time corporate FX exposure monitor</span>
        </div>
        <div className="header-spacer" />
        <div className="header-meta">
          <span className="live-dot" aria-hidden="true" />
          <span>
            Live · Last update <span className="mono">{fmtTime(now)}</span>
          </span>
          <button
            className="theme-toggle"
            type="button"
            aria-label="Toggle theme"
            onClick={onToggleTheme}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
            <span>{theme === 'light' ? 'Light' : 'Dark'}</span>
          </button>
        </div>
      </div>
    </header>
  );
}
