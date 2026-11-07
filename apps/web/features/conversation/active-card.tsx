"use client";

import type { PromptCardHistory, PromptCardView } from "@/lib/api";

/** The active image prompt: the exact stored prompt is primary; variants, export and history stay secondary. */
export function ActiveCard({ card, history, busy, onCopy, onVariant }: {
  card: PromptCardView; history: PromptCardHistory["items"]; busy: boolean; onCopy: () => void; onVariant: (id: string) => void;
}) {
  function exportJson() {
    const blob = new Blob([JSON.stringify(card.specification, null, 2)], { type: "application/json" });
    const link = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `vision-prompt-v${card.revision}.json` });
    link.click();
    URL.revokeObjectURL(link.href);
  }
  return <section className="conversation-card" aria-labelledby="prompt-heading" aria-busy={busy}>
    <h2 id="prompt-heading" className="sr-only">Image prompt</h2>
    <p className="conversation-prompt" data-testid="active-prompt">{card.prompt}</p>
    <div className="conversation-actions">
      <button type="button" className="secondary" onClick={onCopy}>Copy prompt</button>
      <button type="button" className="conversation-link" onClick={exportJson}>Export JSON</button>
    </div>
    {!!card.variants?.length && <div className="conversation-variants" role="group" aria-label="Other moments">
      {card.variants.map(variant => <button type="button" className="conversation-link" key={variant.id} disabled={busy}
        onClick={() => onVariant(variant.id)}>
        {variant.label}<span> · {variant.changes.map(change => change.after.join(", ")).join("; ")}</span>
      </button>)}
    </div>}
    {history.length > 0 && <details className="conversation-history-versions"><summary>Earlier versions</summary>
      <ol>{history.map(item => <li key={item.revision} aria-label={`Earlier version ${item.revision}`}>
        <small>Version {item.revision}{item.resolved_moment ? ` · ${item.resolved_moment}` : ""}{item.style ? ` · ${item.style}` : ""}</small>
        <p>{item.prompt}</p></li>)}</ol>
    </details>}
  </section>;
}
