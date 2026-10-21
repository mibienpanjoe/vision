"use client";

import { useEffect, useState } from "react";
import { api, message, type ChapterPage, type EntityDetail, type EntityPage } from "@/lib/api";
import { Contexts } from "./contexts";

export function Entities({ workId, source, cutoff }: { workId: string; source: ChapterPage; cutoff: string | null }) {
  const [page, setPage] = useState<EntityPage | null>(null);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<EntityDetail | null>(null);
  const [filter, setFilter] = useState("");
  const [kind, setKind] = useState("all");
  const [error, setError] = useState("");
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
  function choose(id: string) { if (id !== selected) { setDetail(null); setError(""); setSelected(id); } }
  const items = page?.items.filter(entity => (kind === "all" || entity.kind === kind) &&
    [entity.label, ...entity.aliases.map(alias => alias.label)].some(label => label.toLocaleLowerCase().includes(filter.toLocaleLowerCase()))) ?? [];
  return <section className="explorer" aria-labelledby="explorer-title">
    <h2 id="explorer-title">People, places and objects</h2>
    {error && <p role="alert">{error} <button className="secondary" onClick={() => window.location.reload()}>Reload book</button></p>}
    {!page && !error && <p role="status">Loading eligible entities…</p>}
    {page && <>
      <div className="explorer-filters"><label>Find an entity<input type="search" value={filter} onChange={event => setFilter(event.target.value)} /></label>
        <div><label htmlFor="entity-kind">Kind</label><select id="entity-kind" value={kind} onChange={event => setKind(event.target.value)}>
          <option value="all">All kinds</option><option value="character">Characters</option><option value="place">Places</option><option value="object">Objects</option><option value="organization">Organizations</option>
        </select></div></div>
      <div className="explorer-columns"><div className="panel entity-list">
        {!items.length && <p>No matching entities within this reading boundary.</p>}
        <ul>{items.map(entity => <li key={entity.id}><button className="entity-option" aria-pressed={selected === entity.id} onClick={() => choose(entity.id)}>{entity.label}</button><span>{entity.kind} · {entity.mention_count} mentions</span></li>)}</ul>
      </div>
        <div className="entity-content">
          {selected && !detail && !error && <p role="status">Loading entity…</p>}
          {detail && <section className="panel" aria-label="Entity details">
            <h3>{detail.entity.label}</h3><p className="muted-copy">{detail.entity.kind} · {detail.entity.mention_count} eligible mentions</p>
            {detail.entity.aliases.length > 0 && <ul className="alias-list">{detail.entity.aliases.map((alias, index) => <li key={index}>{alias.label} · {alias.status === "supported" ? "supported alias" : "candidate alias — identity unresolved"}</li>)}</ul>}
            <div id="entity-evidence"><h4>Source mentions</h4>
              {detail.mentions.map((mention, index) => <div className="mention" key={index}>
                <blockquote>{mention.span.quote}</blockquote>
                {mention.entity_id === null && <div><p>Identity unresolved. Choose a person explicitly:</p><div className="actions">
                  {mention.candidate_ids.map(id => <button key={id} className="secondary" onClick={() => choose(id)}>Choose {page.items.find(entity => entity.id === id)?.label ?? "entity"}</button>)}
                </div></div>}
              </div>)}
              {detail.mentions_truncated && <p>Showing the first 200 mentions.</p>}
            </div>
          </section>}
          {detail && <Contexts key={detail.entity.id} workId={workId} entity={detail.entity} cutoff={cutoff} />}
        </div>
      </div>
    </>}
  </section>;
}
