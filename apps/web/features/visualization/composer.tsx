"use client";

import { useRef, useState, type FormEvent } from "react";
import { api, json, message, type EntitySummary, type VisualizationCreated, type VisualizationRequest } from "@/lib/api";

export function Composer({ workId, entity, cutoff, result, onResult, onBusy }: {
  workId: string; entity?: EntitySummary; cutoff: string | null; result: VisualizationCreated | null; onResult: (result: VisualizationCreated | null) => void;
  onBusy: (busy: boolean) => void;
}) {
  const [subject, setSubject] = useState<{ id: string | null; label: string }>({ id: entity?.id ?? null, label: entity?.label ?? "" });
  const [query, setQuery] = useState("");
  const [moment, setMoment] = useState("");
  const [context, setContext] = useState("");
  const [mode, setMode] = useState<"canon_first" | "interpretation">("canon_first");
  const [style, setStyle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef<{ key: string; body: VisualizationRequest } | null>(null);
  function changed() { pending.current = null; onResult(null); setError(""); }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!subject.id && !query.trim()) { setError("Describe what you want to visualize."); return; }
    if (!pending.current) pending.current = { key: crypto.randomUUID(), body: { entity_id: subject.id, query: query.trim() || null,
      moment: moment.trim() ? { kind: "phrase", text: moment.trim() } : null,
      context: context.trim() || null, through_chapter_id: cutoff, creative_mode: mode, style: style.trim() || null } };
    setBusy(true); onBusy(true); setError(""); onResult(null);
    try {
      const response = await api<VisualizationCreated>(`/works/${workId}/visualizations`, json(pending.current.body, pending.current.key));
      onResult(response); pending.current = null;
    } catch (error) { setError(message(error)); }
    finally { setBusy(false); onBusy(false); }
  }
  return <section className="panel context-panel" aria-labelledby="context-title">
    <h2 id="context-title">Create a visual specification</h2>
    {subject.label && <p>Subject: <strong>{subject.label}</strong></p>}
    <p className="muted-copy">Describe when and where in the story. The source must support the chosen moment within your reading boundary.</p>
    <form className="form-stack" onSubmit={submit} onChange={changed}>
      <fieldset disabled={busy}>
        <div className="form-field"><label htmlFor="visual-query">Describe the view</label><textarea id="visual-query" value={query} onChange={event => setQuery(event.target.value)} maxLength={1000} rows={3} required={!subject.id} placeholder={subject.label ? `Describe ${subject.label}, a scene, or a moment in the story…` : "Describe a person, place or scene from this book…"} /></div>
        <details className="composer-options"><summary>More options</summary>
        <label>Story moment<input value={moment} onChange={event => setMoment(event.target.value)} maxLength={256} placeholder="After the war, at age ten…" /></label>
        <label>Scene context<input value={context} onChange={event => setContext(event.target.value)} maxLength={256} placeholder="At home, during the family dinner…" /></label>
        <div><label htmlFor="creative-mode">Creative mode</label><select id="creative-mode" value={mode} onChange={event => setMode(event.target.value as "canon_first" | "interpretation")}>
          <option value="canon_first">Canon first</option><option value="interpretation">Interpretation</option>
        </select></div>
        <label>Visual style<input value={style} onChange={event => setStyle(event.target.value)} maxLength={256} placeholder="Ink wash, charcoal…" /></label>
        </details>
      </fieldset>
      <button type="submit" disabled={busy}>{busy ? "Checking the source…" : "Create visual specification"}</button>
    </form>
    {error && <p role="alert">{error} Review the inputs or submit again to retry.</p>}
    {result?.visualization && <p role="status">Saved visual specification for {result.visualization.result.data.subject.entity.label} · revision {result.visualization.revision} · {result.visualization.result.data.scope.resolved_moment ?? "moment not specified"}.</p>}
    {result?.result.outcome === "needs_context" && <div><p>Choose more context before creating a specification.</p><ul className="context-choices">{result.result.choices.map(choice => <li key={choice.id}>
      <button className="secondary" disabled={!choice.field} onClick={() => {
        if (choice.field === "subject") {
          setSubject({ id: choice.id, label: choice.label });
          const name = choice.label.replace(/ \([^)]*\)$/, "");
          const alternatives = result.result.outcome === "needs_context" ? result.result.choices
            .filter(other => other.field === "subject").map(other => other.label.replace(/ \([^)]*\)$/, ""))
            .filter(other => other !== name) : [];
          setQuery(current => alternatives.reduce((text, other) => text.split(other).join(" "), current).replace(/\s+/g, " ").trim());
        }
        if (choice.field === "moment") setMoment(choice.label);
        if (choice.field === "context") setContext(choice.label);
        if (choice.field === "context" || choice.field === "moment") {
          const alternatives = result.result.outcome === "needs_context" ? result.result.choices
            .filter(other => other.field === choice.field && other.label !== choice.label) : [];
          setQuery(current => alternatives.reduce((text, other) => text.split(other.label).join(" "), current).replace(/\s+/g, " ").trim());
        }
        changed();
      }}>Use {choice.field ?? "choice"}: {choice.label}</button>
    </li>)}</ul></div>}
    {result?.result.outcome === "insufficient_evidence" && <div role="status"><p>The source does not establish this request.</p><ul>{result.result.missing.map(item => <li key={item}>{item}</li>)}</ul><p>Try another moment or review the reading boundary.</p></div>}
    {result?.result.outcome === "failed" && <p role="alert">{result.result.error.message} ({result.result.error.code}). {result.result.error.retryable ? "Try again." : "Review the request or return to your library."}</p>}
  </section>;
}
