"use client";

import type { PromptCardView } from "@/lib/api";

/** Optional moment cards: the current moment is marked, each other moment is one action with its visible difference. */
export function MomentOptions({ card, pending, busy, onSelect }: {
  card: PromptCardView; pending: string | null; busy: boolean; onSelect: (id: string) => void;
}) {
  const variants = card.variants ?? [];
  if (!variants.length) return null;
  const current = card.specification.result.data.scope.resolved_moment;
  return <div className="conversation-variants" role="group" aria-label="Other moments">
    {current && <span className="conversation-moment" aria-current="true"><strong>{current}</strong><span>shown</span></span>}
    {variants.map(variant => <button type="button" className="conversation-moment" key={variant.id}
      aria-pressed={pending === variant.id} aria-busy={pending === variant.id} disabled={busy}
      onClick={() => onSelect(variant.id)}>
      <strong>{variant.label}</strong>
      <span>{pending === variant.id ? "Updating…" : variant.changes.map(change => change.after.join(", ")).join("; ")}</span>
    </button>)}
  </div>;
}
