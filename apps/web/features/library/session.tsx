"use client";

import { useState, type FormEvent } from "react";
import { api, json, message, type PrincipalView } from "@/lib/api";

export function SignIn({ onSignedIn }: { onSignedIn: (actor: PrincipalView) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true); setError("");
    try {
      onSignedIn(await api<PrincipalView>("/auth/login", json({ username: form.get("username"), password: form.get("password") })));
    } catch (error) { setError(message(error)); }
    finally { setBusy(false); }
  }
  return <section className="panel sign-in" aria-labelledby="sign-in-title">
    <h2 id="sign-in-title">Sign in to your library</h2>
    <p className="muted-copy">Your books and discoveries stay in your private workspace.</p>
    <form onSubmit={submit} className="form-stack">
      <label>Username<input name="username" autoComplete="username" required minLength={3} maxLength={32} /></label>
      <label>Password<input name="password" type="password" autoComplete="current-password" required minLength={12} maxLength={128} /></label>
      <button type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      {error && <p role="alert">{error}</p>}
    </form>
  </section>;
}
