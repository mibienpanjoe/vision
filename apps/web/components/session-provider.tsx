"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError, message, type PrincipalView } from "@/lib/api";

type Session = { actor: PrincipalView; retry: () => void };
const Context = createContext<Session | null>(null);
let opening: Promise<PrincipalView> | null = null;
let requestKey = "";
let recoveryKey = "";

function nonce() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return btoa(String.fromCharCode(...bytes)).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function openWorkspace() {
  if (opening) return opening;
  requestKey ||= nonce();
  if (location.hash.startsWith("#recover=")) {
    recoveryKey = location.hash.slice(9);
    history.replaceState(null, "", location.pathname + location.search);
  }
  const send = async () => {
    let remembered = false;
    try { remembered = localStorage.getItem("vision-workspace-initialized") === "1"; } catch { /* Cookies still carry access. */ }
    if (remembered && !recoveryKey) await api<PrincipalView>("/auth/me");
    const actor = await api<PrincipalView>(recoveryKey ? "/auth/workspace/recover" : "/auth/workspace", {
      method: "POST", headers: { "Idempotency-Key": requestKey, ...(recoveryKey ? { "Recovery-Key": recoveryKey } : {}) },
    });
    try { localStorage.setItem("vision-workspace-initialized", "1"); } catch { /* Never store a capability outside its cookie. */ }
    return actor;
  };
  opening = (navigator.locks ? navigator.locks.request("vision-workspace-bootstrap", send) : send()).then(actor => {
    recoveryKey = "";
    return actor;
  });
  return opening;
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [actor, setActor] = useState<PrincipalView | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => { opening = null; setAttempt(value => value + 1); }, []);
  useEffect(() => {
    let active = true;
    setError("");
    openWorkspace().then(value => { if (active) setActor(previous => previous?.id === value.id ? previous : value); }).catch(error => { if (active) { setError(message(error)); if (error instanceof ApiError && error.status === 401) setActor(null); } });
    return () => { active = false; };
  }, [attempt]);
  useEffect(() => {
    window.addEventListener("focus", retry);
    return () => window.removeEventListener("focus", retry);
  }, [retry]);
  return <>
    {error && <div role="alert" className="panel"><p>{error}</p><button className="secondary" onClick={retry}>Retry workspace access</button></div>}
    {!actor && !error && <p role="status">Opening your private workspace…</p>}
    {actor && <Context.Provider value={{ actor, retry }}>{children}</Context.Provider>}
  </>;
}

export function useSession() {
  const session = useContext(Context);
  if (!session) throw new Error("Workspace session provider is required.");
  return session;
}
