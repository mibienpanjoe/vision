"use client";

import { useRef, useState, type FormEvent } from "react";
import { api, json, message, type EntitySummary, type VisualizationCreated, type VisualizationRequest } from "@/lib/api";

export function Contexts({ workId, entity, cutoff }: { workId: string; entity: EntitySummary; cutoff: string | null }) {
  const [moment, setMoment] = useState("");
  const [context, setContext] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<VisualizationCreated | null>(null);
  const pending = useRef<{ key: string; body: VisualizationRequest } | null>(null);
  function changed() { pending.current = null; setResult(null); setError(""); }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pending.current) pending.current = { key: crypto.randomUUID(), body: { entity_id: entity.id,
      moment: moment.trim() ? { kind: "phrase", text: moment.trim() } : null,
      context: context.trim() || null, through_chapter_id: cutoff, creative_mode: "canon_first" } };
    setBusy(true); setError(""); setResult(null);
    try {
      const response = await api<VisualizationCreated>(`/works/${workId}/visualizations`, json(pending.current.body, pending.current.key));
      setResult(response); pending.current = null;
    } catch (error) { setError(message(error)); }
    finally { setBusy(false); }
  }
  return <section className="panel context-panel" aria-labelledby="context-title">
    <h3 id="context-title">Choose a moment for {entity.label}</h3>
    <p className="muted-copy">Describe when and where in the story. The source must support the chosen moment within your reading boundary.</p>
    <form className="form-stack" onSubmit={submit} onChange={changed}>
      <fieldset disabled={busy}>
        <label>Story moment<input value={moment} onChange={event => setMoment(event.target.value)} maxLength={256} placeholder="After the war, at age ten…" /></label>
        <label>Scene context<input value={context} onChange={event => setContext(event.target.value)} maxLength={256} placeholder="At home, during the family dinner…" /></label>
      </fieldset>
      <button type="submit" disabled={busy}>{busy ? "Checking the source…" : "Create visual specification"}</button>
    </form>
    {error && <p role="alert">{error} Review the inputs or submit again to retry.</p>}
    {result?.visualization && <p role="status">Saved visual specification for {result.visualization.result.data.subject.entity.label} · revision {result.visualization.revision} · {result.visualization.result.data.scope.resolved_moment ?? "moment not specified"}.</p>}
    {result?.result.outcome === "needs_context" && <div><p>Choose more context before creating a specification.</p><ul>{result.result.choices.map(choice => <li key={choice.id}>{choice.label} ({choice.field})</li>)}</ul></div>}
    {result?.result.outcome === "insufficient_evidence" && <div role="status"><p>The source does not establish this request.</p><ul>{result.result.missing.map(item => <li key={item}>{item}</li>)}</ul><p>Try another moment or review the reading boundary.</p></div>}
    {result?.result.outcome === "failed" && <p role="alert">{result.result.error.message} ({result.result.error.code}). {result.result.error.retryable ? "Try again." : "Review the request or return to your library."}</p>}
  </section>;
}
