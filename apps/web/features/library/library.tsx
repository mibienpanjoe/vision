"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, message, type LibraryPage, type PrincipalView, type WorkView } from "@/lib/api";
import { useSession } from "@/components/session-provider";
import { Illustration } from "@/components/illustration";
import { SignIn } from "./session";
import { Upload } from "./upload";
import { JobStatus } from "./job-status";

export function Library() {
  const { actor, checking, error, setActor } = useSession();
  const signedOut = useCallback(() => setActor(null), [setActor]);

  if (checking) return <p role="status">Opening your library…</p>;
  return <>
    {error && <p role="alert">{error} <button className="secondary" onClick={() => window.location.reload()}>Reload library</button></p>}
    {!actor ? <SignIn onSignedIn={setActor} />
      : <PrivateLibrary key={actor.id} actor={actor} signedOut={signedOut} />}
  </>;
}

function PrivateLibrary({ actor, signedOut }: { actor: PrincipalView; signedOut: () => void }) {
  const [works, setWorks] = useState<WorkView[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    let active = true;
    setBusy(true); setError("");
    api<LibraryPage>("/works").then(result => {
      if (active) { setWorks(result.items); setCursor(result.next_cursor); }
    }).catch(error => {
      if (active) { setError(message(error)); if (error instanceof ApiError && error.status === 401) signedOut(); }
    }).finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [actor, signedOut]);

  async function more() {
    if (!cursor) return;
    setBusy(true); setError("");
    try {
      const result = await api<LibraryPage>(`/works?after=${encodeURIComponent(cursor)}`);
      setWorks(previous => [...previous, ...result.items.filter(item => !previous.some(work => work.id === item.id))]);
      setCursor(result.next_cursor);
    } catch (error) { setError(message(error)); if (error instanceof ApiError && error.status === 401) signedOut(); }
    finally { setBusy(false); }
  }

  return <>
    {error && <p role="alert">{error} <button className="secondary" onClick={() => window.location.reload()}>Reload library</button></p>}
      <section aria-labelledby="books-title" className="book-list">
        <h2 id="books-title">Your books</h2>
        {busy && <p role="status">Loading books…</p>}
        {!busy && !works.length && !error && <div className="panel empty-state"><Illustration name="empty" className="empty-art" /><div><p>Upload your first book to begin.</p></div></div>}
        {works.map(work => <article className="panel book" key={work.id} aria-label={work.title}>
          <div className="book-heading"><h3>{work.title}</h3><span className="book-format">{work.format.toUpperCase()} · {new Intl.NumberFormat().format(work.byte_count)} bytes</span></div>
          <JobStatus workId={work.id} onUnauthorized={signedOut} />
          <a href={`/works/${work.id}`}>Open book</a>
        </article>)}
        {cursor && <button className="secondary" onClick={() => void more()} disabled={busy}>Load more books</button>}
      </section>
      <Upload disabled={busy} onUnauthorized={signedOut} onUploaded={({ work }) => setWorks(previous => [work, ...previous.filter(item => item.id !== work.id)])} />
  </>;
}
