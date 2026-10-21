"use client";

import { useRef, useState, type FormEvent } from "react";
import { api, ApiError, message, type UploadAccepted } from "@/lib/api";

export function Upload({ onUploaded, onUnauthorized, disabled }: { onUploaded: (result: UploadAccepted) => void; onUnauthorized: () => void; disabled: boolean }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // Keep the same key and payload after an uncertain network outcome.
  const pending = useRef<{ key: string; body: FormData } | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!pending.current) pending.current = { key: crypto.randomUUID(), body: new FormData(form) };
    setBusy(true); setError("");
    try {
      const result = await api<UploadAccepted>("/works", { method: "POST", headers: { "Idempotency-Key": pending.current.key }, body: pending.current.body });
      pending.current = null; form.reset(); onUploaded(result);
    } catch (error) { setError(message(error)); if (error instanceof ApiError && error.status === 401) onUnauthorized(); }
    finally { setBusy(false); }
  }
  return <section className="panel upload-panel" aria-labelledby="upload-title">
    <div><p className="eyebrow">Add a world</p><h2 id="upload-title">Upload a book</h2>
      <p className="muted-copy">TXT, Markdown, PDF or EPUB · up to 8 MiB.<br />PDFs need a text layer; scanned pages are unsupported.</p></div>
    <form onSubmit={submit} onChange={() => { pending.current = null; setError(""); }} className="form-stack">
      <fieldset disabled={busy || disabled}>
        <label>Book title<input name="title" required maxLength={256} /></label>
        <div className="form-row"><label>Format<select name="format" defaultValue="txt"><option value="txt">Plain text</option><option value="md">Markdown</option><option value="pdf">PDF</option><option value="epub">EPUB</option></select></label>
          <label>Source file<input name="file" type="file" accept=".txt,.md,.pdf,.epub" required /></label></div>
      </fieldset>
      <div><button disabled={busy || disabled} type="submit">{busy ? "Uploading…" : "Upload book"}</button></div>
      {busy && <p role="status">Transferring your book. Processing begins after it is stored.</p>}
      {error && <p role="alert">{error} Submit again to retry this upload.</p>}
    </form>
  </section>;
}
