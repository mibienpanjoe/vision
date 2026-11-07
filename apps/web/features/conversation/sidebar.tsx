"use client";

import { useEffect, useState } from "react";
import { api, json, message, type ConversationPage, type ConversationSummary, type WorkView } from "@/lib/api";

/** Recent conversations grouped by book, paged on demand; per book: ask again or delete it. */
export function ConversationSidebar({ activeId }: { activeId: string | null }) {
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  async function load(after: string | null) {
    const page = await api<ConversationPage>(`/conversations?limit=20${after ? `&after=${after}` : ""}`);
    setItems(previous => after ? [...previous, ...page.items.filter(item => !previous.some(seen => seen.id === item.id))] : page.items);
    setCursor(page.next_cursor ?? null);
  }
  useEffect(() => { void load(null).catch(() => {}); }, [activeId]);
  const books = [...new Map(items.map(item => [item.work_id, item.work_title])).entries()];
  async function remove(workId: string) {
    try {
      const work = await api<WorkView>(`/works/${workId}`);
      await api(`/works/${workId}`, { method: "DELETE", headers: { ...json({}, crypto.randomUUID()).headers, "If-Match": `"${work.revision}"` } });
      setItems(previous => previous.filter(item => item.work_id !== workId)); setNotice("Book deleted.");
      if (items.some(item => item.work_id === workId && item.id === activeId)) location.assign("/conversations/new");
    } catch (error) { setNotice(message(error)); }
    setConfirming(null);
  }
  return <nav className="conversation-books" aria-label="Your books">
    {books.map(([workId, title]) => <section key={workId} aria-label={title}>
      <h2>{title}</h2>
      <ul>{items.filter(item => item.work_id === workId).map(item => <li key={item.id}>
        <a className="conversation-history" href={`/conversations/${item.id}`} aria-current={activeId === item.id ? "page" : undefined}>{item.title}</a>
      </li>)}</ul>
      <div className="conversation-book-actions">
        <a className="conversation-link" href={`/conversations/new?work=${workId}`}>New question</a>
        {confirming === workId
          ? <><button type="button" className="conversation-link" onClick={() => void remove(workId)}>Confirm delete</button>
              <button type="button" className="conversation-link" onClick={() => setConfirming(null)}>Keep</button></>
          : <button type="button" className="conversation-link" aria-label={`Delete ${title}`} onClick={() => setConfirming(workId)}>Delete</button>}
      </div>
    </section>)}
    {cursor && <button type="button" className="conversation-link" onClick={() => void load(cursor).catch(() => {})}>Show more</button>}
    {notice && <p role="status" className="conversation-image-state">{notice}</p>}
  </nav>;
}
