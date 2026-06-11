import { useState } from 'react';
import { useAuth } from '../../auth/AuthContext';

export function SignupPage({ onSwitch }: { onSwitch: () => void }) {
  const { register } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (password.length < 8) { setErr('Password must be at least 8 characters'); return; }
    setBusy(true);
    try { await register(email, password); }
    catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <div className="auth-shell">
      <form className="auth-card" onSubmit={submit}>
        <h1>Colombus FX</h1>
        <p className="auth-sub">Create your account</p>
        <input type="email" placeholder="Email" value={email}
               onChange={(e) => setEmail(e.target.value)} required />
        <input type="password" placeholder="Password (min 8 chars)" value={password}
               onChange={(e) => setPassword(e.target.value)} required />
        {err && <p className="auth-err">{err}</p>}
        <button type="submit" disabled={busy}>{busy ? '…' : 'Create account'}</button>
        <p className="auth-switch">Have an account?{' '}
          <button type="button" onClick={onSwitch}>Sign in</button></p>
      </form>
    </div>
  );
}
