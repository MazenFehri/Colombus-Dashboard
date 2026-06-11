import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { apiLogin, apiMe, apiRegister, apiSetDigest, tokenStore, type Me } from './api';

interface AuthState {
  user: Me | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  setDigest: (enabled: boolean) => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!tokenStore.get()) { setReady(true); return; }
    apiMe().then(setUser).catch(() => tokenStore.clear()).finally(() => setReady(true));
  }, []);

  const login = async (email: string, password: string) => {
    tokenStore.set(await apiLogin(email, password));
    setUser(await apiMe());
  };
  const register = async (email: string, password: string) => {
    await apiRegister(email, password);
    await login(email, password);
  };
  const logout = () => { tokenStore.clear(); setUser(null); };
  const setDigest = async (enabled: boolean) => setUser(await apiSetDigest(enabled));

  return <Ctx.Provider value={{ user, ready, login, register, logout, setDigest }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAuth must be used within AuthProvider');
  return v;
}
