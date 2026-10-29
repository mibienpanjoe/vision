"use client";

import { useEffect, useRef, useState } from "react";
import { Illustration } from "@/components/illustration";
import { api, message, type ChapterPage, type EntityDetail, type EntityPage, type EntitySummary, type SourceSpan } from "@/lib/api";
import { ReconstructionWorkspace } from "@/features/visualization/workspace";
import { SourceReader } from "@/features/reader/source-reader";

export function Entities({ workId, source, cutoff, onSelect }: { workId: string; source: ChapterPage; cutoff: string | null; onSelect?: (entity: EntitySummary) => void }) {
  const content = useRef<HTMLDivElement>(null);
  const [page, setPage] = useState<EntityPage | null>(null);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<EntityDetail | null>(null);
  useEffect(() => { if (detail && !onSelect) content.current?.scrollIntoView({ block: "start", behavior: "auto" }); }, [detail, onSelect]);
  const [visibleCount, setVisibleCount] = useState(50);
  const [filter, setFilter] = useState("");
  const [kind, setKind] = useState("all");
  const [error, setError] = useState("");
  const [sourceSpan, setSourceSpan] = useState<SourceSpan | null>(null);
  const suffix = cutoff ? `?through_chapter_id=${encodeURIComponent(cutoff)}` : "";
  useEffect(() => {
    let active = true;
    api<EntityPage>(`/works/${workId}/entities${suffix}`).then(page => {
      if (page.scope.generation_id !== source.generation_id) throw new Error("The source changed. Reload this book to use its current generation.");
      if (active) setPage(page);
    }).catch(error => { if (active) setError(message(error)); });
    return () => { active = false; };
  }, [workId, source.generation_id, suffix]);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    api<EntityDetail>(`/works/${workId}/entities/${selected}${suffix}`).then(detail => {
      if (detail.scope.generation_id !== source.generation_id) throw new Error("The source changed. Reload this book.");
      if (active) setDetail(detail);
    }).catch(error => { if (active) setError(message(error)); });
    return () => { active = false; };
  }, [selected, workId, source.generation_id, suffix]);
  function choose(id: string) { if (id !== selected) { const entity = page?.items.find(item => item.id === id); if (entity) onSelect?.(entity); setDetail(null); setSourceSpan(null); setError(""); setSelected(id); } }
  const items = page?.items.filter(entity => (kind === "all" || entity.kind === kind) &&
    [entity.label, ...entity.aliases.map(alias => alias.label)].some(label => label.toLocaleLowerCase().includes(filter.toLocaleLowerCase()))) ?? [];
  items.sort((a, b) => b.mention_count - a.mention_count || a.label.localeCompare(b.label));
  return <section className="explorer" aria-labelledby="explorer-title">
    <h2 id="explorer-title">People, places and objects</h2>
    {error && <p role="alert">{error} <button className="secondary" onClick={() => window.location.reload()}>Reload book</button></p>}
    {!page && !error && <p role="status">Loading eligible entities…</p>}
    {page && <>
      <div className="explorer-filters"><label>Find an entity<input type="search" value={filter} onChange={event => { setFilter(event.target.value); setVisibleCount(50); }} /></label>
        <div><label htmlFor="entity-kind">Kind</label><select id="entity-kind" value={kind} onChange={event => { setKind(event.target.value); setVisibleCount(50); }}>
          <option value="all">All kinds</option><option value="character">Characters</option><option value="place">Places</option><option value="object">Objects</option><option value="organization">Organizations</option>
        </select></div></div>
      <div className="explorer-columns"><div className="explorer-aside"><div className="panel entity-list" role="region" aria-label="Browse entities" tabIndex={0}>
        <p className="entity-count">{items.length} results · most mentioned first</p>
        {!items.length && <div className="empty-state"><Illustration name="empty" className="empty-art" /><p>No matching entities within this reading boundary.</p></div>}
        <ul>{items.slice(0, visibleCount).map(entity => <li key={entity.id}><button className="entity-option" aria-pressed={selected === entity.id} onClick={() => choose(entity.id)}>{entity.label}</button><span>{entity.kind} · {entity.mention_count} {entity.mention_count === 1 ? "mention" : "mentions"}</span></li>)}</ul>
        {items.length > visibleCount && <button className="secondary" onClick={() => setVisibleCount(count => count + 50)}>Show more results</button>}
      </div></div>
        <div className="entity-content" ref={content}>
          {!selected && <div className="panel explorer-start"><h3>What would you like to explore?</h3><p>Choose a person, place or object to see its source passages and create a visual.</p></div>}
          {selected && !detail && !error && <p role="status">Loading entity…</p>}
          {detail && !onSelect && <ReconstructionWorkspace key={detail.entity.id} workId={workId} entity={detail.entity} cutoff={cutoff} generationId={source.generation_id} boundaryLabel={cutoff ? `Through chapter ${source.items.find(chapter => chapter.id === cutoff)?.ordinal}` : "Whole book"} />}
          {detail && <section className="panel" aria-label="Entity details">
            <h3>{detail.entity.label}</h3><p className="muted-copy">{detail.entity.kind} · {detail.entity.mention_count} eligible mentions</p>
            {detail.entity.aliases.length > 0 && <ul className="alias-list">{detail.entity.aliases.map((alias, index) => <li key={index}>{alias.label} · {alias.status === "supported" ? "supported alias" : "candidate alias — identity unresolved"}</li>)}</ul>}
            <details id="entity-evidence"><summary>Source mentions</summary>
              {detail.mentions.map((mention, index) => <div className="mention" key={index}>
                <blockquote>{mention.span.quote}</blockquote>
                <button className="secondary" onClick={() => setSourceSpan(mention.span)}>Read passage {index + 1}</button>
                {mention.entity_id === null && <div><p>Identity unresolved. Choose a person explicitly:</p><div className="actions">
                  {mention.candidate_ids.map(id => <button key={id} className="secondary" onClick={() => choose(id)}>Choose {page.items.find(entity => entity.id === id)?.label ?? "entity"}</button>)}
                </div></div>}
              </div>)}
              {detail.mentions_truncated && <p>Showing the first 200 mentions.</p>}
            </details>
          </section>}
          {detail && sourceSpan && <SourceReader workId={workId} parserRevision={source.parser_revision} cutoff={cutoff} span={sourceSpan} />}
        </div>
      </div>
    </>}
  </section>;
}
