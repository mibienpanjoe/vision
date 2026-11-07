"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError, json, message, type ConversationRender, type ConversationRenderPage } from "@/lib/api";

const settled = new Set(["succeeded", "failed", "cancelled", "acceptance_unknown"]);

/** Explicit image generation for the active prompt version; earlier images stay, labelled by their version. */
export function ImageResult({ conversationId, workId, cardRevision }: { conversationId: string; workId: string; cardRevision: number }) {
  const [items, setItems] = useState<ConversationRender[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const key = useRef<string | null>(null);
  const load = useRef<() => Promise<void>>(async () => {});
  load.current = async () => {
    const page = await api<ConversationRenderPage>(`/conversations/${conversationId}/renders`);
    setItems(page.items);
  };
  const pending = items.some(item => !settled.has(item.render.status));
  useEffect(() => { void load.current().catch(() => {}); }, [conversationId, cardRevision]);
  useEffect(() => {
    if (!pending) return;
    const timer = setInterval(() => { void load.current().catch(() => {}); }, 2000);
    return () => clearInterval(timer);
  }, [pending]);
  const current = items.find(item => item.card_revision === cardRevision);
  const latest = items.find(item => item.render.status === "succeeded");
  const shown = current?.render.status === "succeeded" ? current : latest;
  async function generate() {
    setBusy(true); setError("");
    key.current ||= crypto.randomUUID();
    try {
      await api(`/conversations/${conversationId}/renders`, json({ card_revision: cardRevision }, key.current));
      key.current = null;
      await load.current();
    } catch (failure) {
      setError(message(failure));
      if (failure instanceof ApiError && failure.status > 0 && failure.status < 500) key.current = null;
    } finally { setBusy(false); }
  }
  const state = current && !settled.has(current.render.status) ? "Generating image…"
    : current?.render.status === "failed" ? "Image generation failed. Your prompt is unchanged."
    : current?.render.status === "acceptance_unknown" ? "The image service did not confirm this request; it was not retried." : "";
  return <>
    {!current && <button type="button" className="secondary" disabled={busy} onClick={() => void generate()}>Generate image</button>}
    {(state || error) && <p className="conversation-image-state" role="status">{error || state}</p>}
    {shown && <figure className="conversation-image">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={`/api/v1/works/${workId}/renders/${shown.render.id}/image`} alt={`Generated image for prompt version ${shown.card_revision}`} />
      <figcaption>{shown.card_revision === cardRevision ? `Prompt version ${shown.card_revision}` : `From earlier prompt version ${shown.card_revision}`}
        {" · "}<a href={`/api/v1/works/${workId}/renders/${shown.render.id}/image?download=true`}>Download</a></figcaption>
    </figure>}
  </>;
}
