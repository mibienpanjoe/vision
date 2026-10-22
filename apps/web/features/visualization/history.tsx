"use client";

import { useEffect, useState } from "react";
import { api, message, type RevisionPage, type VisualizationPage, type VisualizationView } from "@/lib/api";

export function historyScope(generationId: string, cutoff: string | null) {
  return `?generation_id=${encodeURIComponent(generationId)}${cutoff ? `&through_chapter_id=${encodeURIComponent(cutoff)}` : ""}`;
}

export function History({ workId, generationId, cutoff, refresh, onSelect, disabled }: {
  workId: string; generationId: string; cutoff: string | null; refresh: number;
  onSelect: (view: VisualizationView, current: boolean) => void;
  disabled: boolean;
}) {
  const [items, setItems] = useState<VisualizationPage | null>(null);
  const [revisions, setRevisions] = useState<{ id: string; head: number; page: RevisionPage } | null>(null);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState(false);
  const scope = historyScope(generationId, cutoff);
  useEffect(() => {
    let active = true;
    api<VisualizationPage>(`/works/${workId}/visualizations${scope}`).then(page => {
      if (active) { setItems(page); setRevisions(null); setError(""); }
    }).catch(error => { if (active) setError(message(error)); });
    return () => { active = false; };
  }, [workId, scope, refresh, reload]);
  async function open(id: string, head: number, number?: number) {
    setBusy(true); setError("");
    try {
      const view = await api<VisualizationView>(`/works/${workId}/visualizations/${id}${number ? `/revisions/${number}` : ""}${scope}`);
      const page = await api<RevisionPage>(`/works/${workId}/visualizations/${id}/revisions${scope}`);
      const currentHead = page.items[0]?.number ?? head;
      setRevisions({ id, head: currentHead, page });
      onSelect(view, view.revision === currentHead);
    } catch (error) { setError(message(error)); }
    finally { setBusy(false); }
  }
  return <section className="panel history" aria-label="Saved specifications">
    <div className="library-toolbar"><h3>Saved specifications</h3><button className="secondary" disabled={busy || disabled} onClick={() => setReload(value => value + 1)}>Reload saved views</button></div>
    {!items && !error && <p role="status">Loading saved views…</p>}
    {items && !items.items.length && <p>No saved specifications in this reading scope.</p>}
    {items && <ul>{items.items.map(item => <li key={item.id}><button className="secondary" disabled={busy || disabled} onClick={() => void open(item.id, item.revision)}>Open {item.subject} revision {item.revision}</button></li>)}</ul>}
    {revisions && <div><h4>Revision history</h4><ul>{revisions.page.items.map(revision => <li key={revision.number}>
      <button className="secondary" disabled={busy || disabled} onClick={() => void open(revisions.id, revisions.head, revision.number)}>View revision {revision.number}</button>
    </li>)}</ul></div>}
    {error && <p role="alert">{error} Reload saved views or return to your library.</p>}
  </section>;
}
