"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, json, message, type RenderPage, type RenderView, type VisualizationView } from "@/lib/api";

const FAILURES: Record<string, string> = {
  PROVIDER_UNAUTHORIZED: "The image provider rejected the configured key.",
  PROVIDER_QUOTA_EXCEEDED: "The image provider account has no remaining quota.",
  PROVIDER_RATE_LIMITED: "The image provider is limiting requests. Try again later.",
  PROVIDER_CONTENT_REFUSED: "The image provider refused this prompt.",
  PROVIDER_UNAVAILABLE: "The image provider could not be reached. Nothing was sent.",
  RENDER_STORAGE_FAILED: "The provider returned an image, but it could not be saved. The request may have been charged.",
  RENDER_NOT_CONFIGURED: "Image rendering was not configured when this render ran. Nothing was sent.",
};

function outcome(job: RenderView) {
  switch (job.status) {
    case "queued": return "Queued";
    case "running": return job.cancel_requested ? "Rendering · cancellation requested; the result will be kept" : "Rendering…";
    case "succeeded": return job.cancel_requested ? "Finished after cancellation was requested" : "Finished";
    case "cancelled": return "Cancelled before it was sent";
    case "acceptance_unknown": return "Outcome unknown: the provider may have received and charged this request. It is not retried automatically.";
    default: return FAILURES[job.error_code ?? ""] ?? "The image provider returned no usable image.";
  }
}

export function RenderHistory({ view, current, onOpenRevision }: {
  view: VisualizationView; current: boolean; onOpenRevision: (revision: number) => void;
}) {
  const [page, setPage] = useState<RenderPage | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef<{ key: string; revision: number } | null>(null);
  const base = `/works/${view.work_id}`;
  const load = useCallback(() => api<RenderPage>(`${base}/visualizations/${view.id}/renders`), [base, view.id]);
  const active = page?.items.some(job => job.status === "queued" || job.status === "running") ?? false;

  // Reload when another revision is shown: the current revision may have moved since the last load.
  useEffect(() => {
    let live = true;
    load().then(value => { if (live) { setPage(value); setError(""); } }).catch(error => { if (live) setError(message(error)); });
    return () => { live = false; };
  }, [load, view.revision]);
  useEffect(() => {
    if (!active) return;
    let live = true;
    const timer = setInterval(() => load().then(value => { if (live) setPage(value); }).catch(() => undefined), 2000);
    return () => { live = false; clearInterval(timer); };
  }, [active, load]);

  async function start() {
    // A retried click after a lost response reuses its key, so it cannot reserve a second paid call.
    if (pending.current?.revision !== view.revision) pending.current = { key: crypto.randomUUID(), revision: view.revision };
    setBusy(true); setError("");
    try {
      await api<RenderView>(`${base}/visualizations/${view.id}/renders`, json({ specification_revision: view.revision }, pending.current.key));
      pending.current = null;
      setPage(await load());
    } catch (error) {
      setError(message(error));
      if (error instanceof ApiError && error.status !== 0) pending.current = null;
    } finally { setBusy(false); }
  }
  async function cancel(job: RenderView) {
    setBusy(true); setError("");
    try {
      const request = json({}, crypto.randomUUID());
      await api<RenderView>(`${base}/renders/${job.id}/cancel`, { ...request, headers: { ...request.headers, "If-Match": `"${job.revision}"` } });
      setPage(await load());
    } catch (error) { setError(message(error)); setPage(await load().catch(() => page)); }
    finally { setBusy(false); }
  }

  return <section className="panel render-history" aria-label="Rendered images">
    <div className="library-toolbar"><h3>Rendered images</h3>
      {current && <button disabled={busy} onClick={() => void start()}>{busy ? "Requesting…" : `Render revision ${view.revision}`}</button>}</div>
    <p className="muted-copy">An image is an interpretation of this specification, not evidence. Each render is a separate, billed request.</p>
    {!page && !error && <p role="status">Loading rendered images…</p>}
    {page && !page.items.length && <p>No rendered images for this specification yet.</p>}
    {page && <ul>{page.items.map(job => <li key={job.id}><article className="render" aria-label={`Render of revision ${job.specification_revision}`}>
      {job.status === "succeeded" && job.output_sha256 && <figure>
        {/* eslint-disable-next-line @next/next/no-img-element -- private, authenticated bytes must bypass the image optimizer */}
        <img src={`/api/v1${base}/renders/${job.id}/image`} alt={`Generated image of revision ${job.specification_revision}`} />
        <figcaption>Generated image · not evidence</figcaption>
      </figure>}
      <div className="render-meta">
        <p><strong>Revision {job.specification_revision}</strong>{job.specification_revision !== page.current_revision && <span className="render-stale"> · Older specification; the current revision is {page.current_revision}</span>}</p>
        <p role={job.status === "queued" || job.status === "running" ? "status" : undefined}>{outcome(job)}</p>
        <p className="book-format">{job.provider} · {job.model} · {new Date(job.created_at).toLocaleString()}</p>
        <div className="actions">
          {job.specification_revision !== view.revision && <button className="secondary" disabled={busy} onClick={() => onOpenRevision(job.specification_revision)}>Show revision {job.specification_revision}</button>}
          {job.status === "succeeded" && job.output_sha256 && <a href={`/api/v1${base}/renders/${job.id}/image?download=true`}>Download image</a>}
          {(job.status === "queued" || (job.status === "running" && !job.cancel_requested)) && <button className="secondary" disabled={busy} onClick={() => void cancel(job)}>Cancel render</button>}
        </div>
      </div>
    </article></li>)}</ul>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
