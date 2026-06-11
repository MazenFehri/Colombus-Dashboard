import { endpoints } from '../api/endpoints';

const TOKEN_KEY = 'colombus_token';

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export interface Me { id: number; email: string; digest_enabled: boolean; }

export async function apiRegister(email: string, password: string): Promise<void> {
  const r = await fetch(endpoints.register(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? 'Registration failed');
}

export async function apiLogin(email: string, password: string): Promise<string> {
  const r = await fetch(endpoints.login(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? 'Login failed');
  return (await r.json()).access_token as string;
}

export async function apiMe(): Promise<Me> {
  const r = await fetch(endpoints.me(), { headers: authHeaders() });
  if (!r.ok) throw new Error('Not authenticated');
  return (await r.json()) as Me;
}

export async function apiSetDigest(enabled: boolean): Promise<Me> {
  const r = await fetch(endpoints.me(), {
    method: 'PATCH',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ digest_enabled: enabled }),
  });
  if (!r.ok) throw new Error('Failed to update preference');
  return (await r.json()) as Me;
}

export function authHeaders(): Record<string, string> {
  const t = tokenStore.get();
  return t ? { Authorization: `Bearer ${t}` } : {};
}
