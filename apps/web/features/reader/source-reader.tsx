"use client";

import { useEffect, useState } from "react";
import { api, json, message, type EvidenceView, type SourceSpan } from "@/lib/api";
import { highlightSegments, type EvidenceTarget } from "./highlight";

export function SourceReader({ workId, parserRevision, cutoff, span, targets = [], selected = [], onSelect }: {
  workId: string; parserRevision: string; cutoff: string | null; span: SourceSpan;
  targets?: EvidenceTarget[]; selected?: string[]; onSelect?: (ids: string[]) => void;
}) {
  const key = JSON.stringify([workId, parserRevision, cutoff, span]);
  const [loaded, setLoaded] = useState<{ key: string; view?: EvidenceView; error?: string } | null>(null);
  useEffect(() => {
    let active = true;
    api<EvidenceView>(`/works/${workId}/evidence`, json({ span, parser_revision: parserRevision,
      reading_boundary: cutoff ? { mode: "through_chapter", chapter_id: cutoff } : { mode: "whole_book" },
      context_before: 150, context_after: 150,
    })).then(view => {
      const quote = Array.from(view.excerpt).slice(view.highlight_start, view.highlight_end).join("");
      if (quote !== span.quote || view.span.passage_id !== span.passage_id ||
          view.span.document_revision_id !== span.document_revision_id || view.parser_revision !== parserRevision ||
          view.excerpt_start + view.highlight_start !== span.start || view.excerpt_start + view.highlight_end !== span.end) {
        throw new Error("Source anchor is unavailable or no longer matches the retained text.");
      }
      if (active) setLoaded({ key, view });
    }).catch(error => { if (active) setLoaded({ key, error: message(error) }); });
    return () => { active = false; };
  }, [key, workId, parserRevision, cutoff, span]);
  const current = loaded?.key === key ? loaded : null;
  const view = current?.view;
  const matching = targets.filter(target => target.span.document_revision_id === span.document_revision_id && target.span.passage_id === span.passage_id);
  const highlights = matching.length ? matching : [{ id: "source", label: "Selected source span", span }];
  const segments = view ? highlightSegments(view.excerpt, view.excerpt_start, highlights) : [];
  return <section className="source-reader panel" aria-label="Source reader">
    <h4>Source passage</h4>
    {!current && <p role="status">Loading authorized excerpt…</p>}
    {current?.error && <p role="alert">{current.error} Return to your library or choose another source reference.</p>}
    {view && <>
      <p className="source-location">{view.pages ? `Pages ${view.pages.join(", ")} · ` : ""}{view.section ? `Section ${view.section} · ` : ""}
        Source characters {view.original_start}–{view.original_end}</p>
      <p className="source-excerpt">{segments.map(segment => segment.ids.length ? <mark key={segment.start} data-selected={!selected.length || segment.ids.some(id => selected.includes(id))}>
        <button className="source-highlight" type="button" aria-label={`Evidence for ${segment.ids.map(id => highlights.find(target => target.id === id)?.label).join(", ")}`}
          aria-pressed={!selected.length || segment.ids.some(id => selected.includes(id))} onClick={() => onSelect?.(segment.ids)}>{segment.text}</button>
      </mark> : <span key={segment.start}>{segment.text}</span>)}</p>
    </>}
  </section>;
}
