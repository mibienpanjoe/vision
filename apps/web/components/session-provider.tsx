"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError, message, type PrincipalView } from "@/lib/api";

type Session = {
  actor: PrincipalView | null;
  checking: boolean;
  error: string;
  setActor: (actor: PrincipalView | null) => void;
};
const SessionContext = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [actor, setActor] = useState<PrincipalView | null>(null);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api<PrincipalView>("/auth/me").then(value => { if (active) setActor(value); }).catch(error => {
      if (active && !(error instanceof ApiError && error.status === 401)) setError(message(error));
    }).finally(() => { if (active) setChecking(false); });
    return () => { active = false; };
  }, []);
  return <SessionContext.Provider value={{ actor, checking, error, setActor }}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const session = useContext(SessionContext);
  if (!session) throw new Error("SessionProvider is required");
  return session;
}

export function AccountControl() {
  const { actor, setActor } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function logout() {
    setBusy(true); setError("");
    try {
      await api("/auth/logout", { method: "POST" });
      finish();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) finish();
      else setError(message(error));
    } finally { setBusy(false); }
  }
  function finish() {
    setActor(null);
    if (window.location.pathname !== "/") window.location.assign("/");
  }
  if (!actor) return null;
  return <>
    <span className="account-name">{actor.username}</span>
    <button className="secondary" disabled={busy} onClick={() => void logout()}>Sign out</button>
    {error && <p role="alert">{error}</p>}
  </>;
}
