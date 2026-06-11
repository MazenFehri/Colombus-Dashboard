import { useState } from 'react';
import { fmtTime } from '../../lib/format';
import { useAuth } from '../../auth/AuthContext';

export function Header({
  now,
  theme,
  onToggleTheme,
}: {
  now: Date;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
}) {
  const { user, logout, setDigest } = useAuth();
  const [digestErr, setDigestErr] = useState<string | null>(null);

  const onToggleDigest = async (enabled: boolean) => {
    setDigestErr(null);
    try {
      await setDigest(enabled);
    } catch {
      setDigestErr('Save failed');
    }
  };

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
          {user && (
            <div className="acct">
              <span className="acct-email">{user.email}</span>
              <label className="acct-digest">
                <input type="checkbox" checked={user.digest_enabled}
                       onChange={(e) => onToggleDigest(e.target.checked)} />
                Daily digest
              </label>
              {digestErr && <span className="acct-digest-err">{digestErr}</span>}
              <button className="acct-logout" onClick={logout}>Log out</button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
