"use client";

import { useEffect, useRef, useState } from "react";
import type { PromptCardView } from "@/lib/api";
import { SourceReader } from "@/features/reader/source-reader";

/** Exact supporting excerpts on demand, in a modal sheet that returns focus to its opener. */
export function SourceDrawer({ card, workId }: { card: PromptCardView; workId: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLButtonElement>(null);
  const [chosen, setChosen] = useState(0);
  const spec = card.specification.result.data;
  const members = [spec.subject, ...spec.participants, ...spec.world];
  const claims = members.flatMap(member => member.traits.flatMap(trait => trait.evidence.map((span, index) => ({
    id: `${member.entity.entity_ids[0]}:${trait.attribute}:${index}`,
    label: `${member.entity.label} · ${trait.attribute.replaceAll("_", " ")}: ${trait.values.join(", ")}`, span }))));
  // A newer card closes the sheet: a stale excerpt never stands in for the current prompt's sources.
  useEffect(() => { dialog.current?.close(); setChosen(0); }, [card.revision]);
  if (!claims.length) return null;
  const selected = claims[Math.min(chosen, claims.length - 1)];
  return <>
    <button ref={opener} type="button" className="conversation-link" aria-haspopup="dialog" onClick={() => dialog.current?.showModal()}>Sources</button>
    <dialog ref={dialog} className="conversation-drawer" aria-labelledby="sources-heading" onClose={() => opener.current?.focus()}>
      <div className="conversation-drawer-heading"><h2 id="sources-heading">Sources</h2>
        <button type="button" className="conversation-link" onClick={() => dialog.current?.close()}>Close</button></div>
      <ul className="conversation-claims">{claims.map((claim, index) => <li key={claim.id}>
        <button type="button" className="conversation-link" aria-pressed={index === chosen} onClick={() => setChosen(index)}>{claim.label}</button>
      </li>)}</ul>
      <SourceReader workId={workId} parserRevision={spec.scope.parser_revision} cutoff={spec.scope.through_chapter_id ?? null}
        span={selected.span} targets={claims} selected={[selected.id]} />
    </dialog>
  </>;
}
