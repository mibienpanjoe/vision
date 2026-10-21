"use client";

import { useEffect, useState } from "react";
import { api, ApiError, message, type GenerationPage, type GenerationView, type IngestionView } from "@/lib/api";

export function JobStatus({ workId, onUnauthorized }: { workId: string; onUnauthorized: () => void }) {
  const [state, setState] = useState<{ generation: GenerationView; job: IngestionView } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function read() {
      try {
        const generations = await api<GenerationPage>(`/works/${workId}/generations`);
        const generation = generations.items.at(-1);
        if (!generation) throw new Error("Processing state is unavailable.");
        const job = await api<IngestionView>(`/works/${workId}/ingestions/${generation.job_id}`);
        if (active) {
          setState(previous => ({ generation, job: previous && previous.job.revision > job.revision ? previous.job : job }));
          setBlocked(false);
        }
      } catch (error) {
        if (active) {
          setBlocked(true);
          setError(message(error));
          if (error instanceof ApiError && error.status === 401) onUnauthorized();
        }
      } finally {
        if (active) timer = setTimeout(read, 2000);
      }
    }
    void read();
    return () => { active = false; clearTimeout(timer); };
  }, [workId, reload, onUnauthorized]);

  async function mutate(action: "retry" | "cancel") {
    if (!state || busy || blocked) return;
    setBusy(true); setError("");
    try {
      const job = await api<IngestionView>(`/works/${workId}/ingestions/${state.job.id}/${action}`, {
        method: "POST", headers: { "Idempotency-Key": crypto.randomUUID(), "If-Match": `"${state.job.revision}"` },
      });
      setState(previous => previous && { ...previous, job });
    } catch (error) {
      setError(error instanceof ApiError && error.status === 412
        ? "Processing changed. The current state is being reloaded; review it before trying again." : message(error));
      setBlocked(true);
      if (error instanceof ApiError && error.status === 401) onUnauthorized();
    } finally { setBusy(false); setReload(value => value + 1); }
  }
  const job = state?.job;
  const generation = state?.generation;
  const parsing = !job ? "Loading…" : job.cancel_requested && job.status === "running" ? "Cancellation requested — waiting for worker"
    : ({ queued: "Waiting for worker", running: "Parsing…", succeeded: "Complete", failed: "Failed", cancelled: "Cancelled" }[job.status]);
  return <div className="job-status">
    <dl className="readiness" aria-live="polite">
      <div><dt>Parsing</dt><dd>{parsing}</dd></div>
      <div><dt>Extraction</dt><dd>{generation?.narrative_ready ? "Complete" : !generation?.parsed ? "Waiting for parsing" : ({ not_started: "Not started", queued: "Waiting for worker", running: "Extracting…", succeeded: "Complete", failed: "Failed" }[generation.narrative_status])}</dd></div>
      <div><dt>Search index</dt><dd>{generation?.search_ready ? "Ready" : "Not ready"}</dd></div>
    </dl>
    {job?.dispatch_pending && <p className="muted-copy">Saved. Waiting for dispatch to the worker.</p>}
    {job?.error_code && <p>Parsing error: <code>{job.error_code}</code></p>}
    {generation?.narrative_error && <p>Extraction error: <code>{generation.narrative_error}</code></p>}
    {generation?.warnings.map(warning => <p key={warning}>Source warning: <code>{warning}</code></p>)}
    <div className="actions">
      {job && ["queued", "running"].includes(job.status) && <button className="secondary" disabled={busy || blocked || job.cancel_requested} onClick={() => void mutate("cancel")}>Cancel parsing</button>}
      {job && ["failed", "cancelled"].includes(job.status) && job.attempts < 3 && <button className="secondary" disabled={busy || blocked} onClick={() => void mutate("retry")}>Retry parsing</button>}
      {job && job.attempts >= 3 && job.status === "failed" && <p>Parsing attempt limit reached.</p>}
    </div>
    {error && <p role="alert">{error}</p>}
  </div>;
}
