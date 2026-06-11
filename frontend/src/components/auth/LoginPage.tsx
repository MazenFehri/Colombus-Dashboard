import { useState } from 'react';
import { useAuth } from '../../auth/AuthContext';

export function LoginPage({ onSwitch }: { onSwitch: () => void }) {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null); setBusy(true);
    try { await login(email, password); }
    catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <div className="auth-shell">
      <form className="auth-card" onSubmit={submit}>
        <h1>Colombus FX</h1>
        <p className="auth-sub">Sign in to your dashboard</p>
        <input type="email" placeholder="Email" value={email}
               onChange={(e) => setEmail(e.target.value)} required />
        <input type="password" placeholder="Password" value={password}
               onChange={(e) => setPassword(e.target.value)} required />
        {err && <p className="auth-err">{err}</p>}
        <button type="submit" disabled={busy}>{busy ? '…' : 'Sign in'}</button>
        <p className="auth-switch">No account?{' '}
          <button type="button" onClick={onSwitch}>Create one</button></p>
      </form>
    </div>
  );
}
