"use client";

import { useRef, useState, type FormEvent } from "react";
import { api, ApiError, json, message, type CanonicalLock, type RefinementRequest, type VisualizationView } from "@/lib/api";
import { historyScope } from "./history";

export function Refinement({ view, generationId, cutoff, onSaved }: {
  view: VisualizationView; generationId: string; cutoff: string | null; onSaved: (view: VisualizationView) => void;
}) {
  const [style, setStyle] = useState(view.request.style ?? "");
  const [mode, setMode] = useState<"canon_first" | "interpretation">(view.result.data.scope.creative_mode);
  const [locks, setLocks] = useState<CanonicalLock[]>(view.result.data.locks ?? []);
  const [busy, setBusy] = useState(false);
  const [stale, setStale] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const pending = useRef<{ key: string; revision: number; body: RefinementRequest } | null>(null);
  const options = [view.result.data.subject, ...view.result.data.participants, ...view.result.data.world].flatMap(member =>
    member.traits.filter(trait => trait.status === "canonical").flatMap(trait => trait.values.map(value => ({
      label: `Lock ${member.entity.label} ${trait.attribute}: ${value}`,
      lock: { entity_id: member.entity.entity_ids[0], attribute: trait.attribute, value },
    }))));
  const lockKey = (lock: CanonicalLock) => JSON.stringify([lock.entity_id, lock.attribute, lock.value]);
  function changed() { pending.current = null; setNotice(""); if (!stale && !blocked) setError(""); }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (stale || blocked) return;
    if (!pending.current) pending.current = { key: crypto.randomUUID(), revision: view.revision,
      body: { style: style.trim() || null, creative_mode: mode, locks } };
    setBusy(true); setError(""); setNotice("");
    try {
      const request = json(pending.current.body, pending.current.key);
      const result = await api<VisualizationView>(`/works/${view.work_id}/visualizations/${view.id}/refinements`, {
        ...request, headers: { ...request.headers, "If-Match": `"${pending.current.revision}"` },
      });
      pending.current = null; setNotice(`Saved revision ${result.revision}.`); onSaved(result);
    } catch (error) {
      setError(message(error));
      if (error instanceof ApiError && error.status === 412) { setStale(true); pending.current = null; }
      if (error instanceof ApiError && ["SCOPE_CHANGED", "DEPENDENCIES_CHANGED"].includes(error.code)) setBlocked(true);
    } finally { setBusy(false); }
  }
  async function reloadCurrent() {
    setBusy(true);
    try {
      const current = await api<VisualizationView>(`/works/${view.work_id}/visualizations/${view.id}${historyScope(generationId, cutoff)}`);
      setLocks(current.result.data.locks ?? []); setMode(current.result.data.scope.creative_mode);
      pending.current = null; setStale(false); setError(""); setNotice(`Loaded revision ${current.revision}. Review the draft style before saving.`); onSaved(current);
    } catch (error) { setError(message(error)); }
    finally { setBusy(false); }
  }
  return <section className="panel refinement" aria-label="Refine presentation">
    <h3>Refine presentation</h3><p>Editing revision {view.revision}. Source claims and evidence stay unchanged.</p>
    <form onSubmit={save} onChange={changed} className="form-stack">
      <fieldset disabled={busy}>
        <label>Refinement style<input value={style} maxLength={256} onChange={event => setStyle(event.target.value)} /></label>
        <div><label htmlFor="refinement-mode">Refinement creative mode</label><select id="refinement-mode" value={mode} onChange={event => setMode(event.target.value as "canon_first" | "interpretation")}>
          <option value="canon_first">Canon first</option><option value="interpretation">Interpretation</option>
        </select></div>
        <div className="canonical-locks"><p>Keep canonical values in the prompt (up to 32):</p>{options.map(option => <label key={lockKey(option.lock)}>
          <input type="checkbox" disabled={locks.length >= 32 && !locks.some(lock => lockKey(lock) === lockKey(option.lock))} checked={locks.some(lock => lockKey(lock) === lockKey(option.lock))} onChange={event => setLocks(previous => event.target.checked ? [...previous, option.lock] : previous.filter(lock => lockKey(lock) !== lockKey(option.lock)))} />{option.label}
        </label>)}</div>
      </fieldset>
      <button type="submit" disabled={busy || stale || blocked}>{busy ? "Saving revision…" : "Save new revision"}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {stale && <button className="secondary" disabled={busy} onClick={() => void reloadCurrent()}>Reload current revision</button>}
    {blocked && <button className="secondary" onClick={() => window.location.reload()}>Reload book</button>}
  </section>;
}
