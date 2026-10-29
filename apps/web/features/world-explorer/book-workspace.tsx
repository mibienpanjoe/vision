"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, message, type ChapterPage, type EntitySummary, type WorkView } from "@/lib/api";
import { ReconstructionWorkspace } from "@/features/visualization/workspace";
import { Entities } from "./entities";

export function BookWorkspace({ workId }: { workId: string }) {
  const [studioView, setStudioView] = useState("visual");
  const [entityInspector, setEntityInspector] = useState<HTMLDivElement | null>(null);
  const [profileInspector, setProfileInspector] = useState<HTMLDivElement | null>(null);
  const [contextTarget, setContextTarget] = useState<HTMLDivElement | null>(null);
  const [historyTarget, setHistoryTarget] = useState<HTMLDivElement | null>(null);
  const [browseOpen, setBrowseOpen] = useState(false);
  useEffect(() => { setBrowseOpen(window.matchMedia("(min-width: 75rem)").matches); }, []);
  const [work, setWork] = useState<WorkView | null>(null);
  const [chapters, setChapters] = useState<ChapterPage | null>(null);
  const requestArea = useRef<HTMLDivElement>(null);
  const [selectedEntity, setSelectedEntity] = useState<EntitySummary>();
  const selected = useCallback((entity: EntitySummary) => {
    setSelectedEntity(entity);
    setStudioView("visual");
    requestAnimationFrame(() => requestArea.current?.scrollIntoView({ block: "start", behavior: "auto" }));
  }, []);
  const [boundary, setBoundary] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    Promise.all([api<WorkView>(`/works/${workId}`), api<ChapterPage>(`/works/${workId}/chapters`)]).then(([work, chapters]) => {
      if (active) { setWork(work); setChapters(chapters); }
    }).catch(error => { if (active) setError(message(error)); });
    return () => { active = false; };
  }, [workId]);
  async function moreChapters() {
    if (!chapters?.next_after) return;
    setBusy(true);
    try {
      const next = await api<ChapterPage>(`/works/${workId}/chapters?after=${chapters.next_after}`);
      if (next.generation_id !== chapters.generation_id) throw new Error("The source changed. Reload this book before choosing a boundary.");
      setChapters({ ...next, items: [...chapters.items, ...next.items] });
    } catch (error) { setError(message(error)); setBoundary(""); }
    finally { setBusy(false); }
  }
  return <>
    <a className="back-link" href="/">← Your library</a>
    {error && <p role="alert">{error} <a href="/">Return to your library</a> or <button className="secondary" onClick={() => window.location.reload()}>Reload book</button></p>}
    {!work && !error && <p role="status">Opening your book…</p>}
    {work && <><div className="library-heading"><h1 className="book-title">{work.title}</h1></div>
      {chapters && !error && <>
        <section className="panel boundary-panel" aria-label="Reading scope">
          <label htmlFor="reading-boundary">Reading boundary</label>
          <select id="reading-boundary" value={boundary} onChange={event => { setBoundary(event.target.value); setSelectedEntity(undefined); }}>
            <option value="" disabled>Choose how far you have read</option><option value="whole_book">Whole book</option>
            {chapters.items.map(chapter => <option key={chapter.id} value={chapter.id}>Through chapter {chapter.ordinal}</option>)}
          </select>
          {chapters.next_after && <button className="secondary" disabled={busy} onClick={() => void moreChapters()}>Load more chapters</button>}
          <p className="muted-copy">{!chapters.items.length ? "Chapter breaks were not detected. Choose Whole book to allow all of its text." : "Results use only the chapters you allow."}</p>
        </section>
        {boundary ? <><div className="studio-tabs" role="group" aria-label="Workspace view">
          {[ ["browse", "Browse"], ["visual", "Visual"], ["evidence", "Evidence"] ].map(([value, label]) => <button key={value} className="secondary" aria-pressed={studioView === value} onClick={() => { setStudioView(value); if (value === "browse") setBrowseOpen(true); }}>{label}</button>)}
        </div><div className="book-studio" data-view={studioView}>
          <aside className="studio-navigation" aria-label="World navigation">
            <details className="browse-options" open={browseOpen} onToggle={event => setBrowseOpen(event.currentTarget.open)}><summary>Browse people, places and objects</summary><Entities inspectorTarget={entityInspector} onSelect={selected} key={`${chapters.generation_id}/${boundary}`} workId={workId} source={chapters} cutoff={boundary === "whole_book" ? null : boundary} /></details>
            <section className="panel story-context" aria-label="Story context"><h2>Scene and time</h2><div ref={setContextTarget} /></section>
            <div ref={setHistoryTarget} />
          </aside>
          <section className="studio-main" aria-label="Request and visualization" ref={requestArea}><ReconstructionWorkspace contextTarget={contextTarget} inspectorTarget={profileInspector} historyTarget={historyTarget} entity={selectedEntity} key={`${chapters.generation_id}/${boundary}/${selectedEntity?.id ?? "description"}`} workId={workId} cutoff={boundary === "whole_book" ? null : boundary} generationId={chapters.generation_id} boundaryLabel={boundary === "whole_book" ? "Whole book" : `Through chapter ${chapters.items.find(c => c.id === boundary)?.ordinal}`} /></section>
          <aside className="studio-inspector" aria-label="Evidence and attributes" tabIndex={0}><h2>Evidence and attributes</h2><div ref={setProfileInspector} /><div ref={setEntityInspector} />{!selectedEntity && <p className="inspector-empty">Create a visual or select an entity to inspect its supporting passages.</p>}</aside>
        </div></> : <section className="panel"><h2>Create a visual specification</h2><p>First choose how far you have read above. Then describe what you want to see.</p></section>}
      </>}
    </>}
  </>;
}
