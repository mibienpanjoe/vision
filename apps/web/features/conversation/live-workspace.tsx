"use client";

import { BookOpen, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useRef, useState } from "react";
import { api, type ConversationPage, type ConversationSummary, type PromptCardHistory } from "@/lib/api";
import { ActiveCard } from "./active-card";
import { ConversationComposer } from "./composer";
import { useConversation } from "./use-conversation";
import { useComposer } from "./use-composer";
import { useBookPreparation } from "./book-attachment";

const stages: Record<string, string> = { queued: "Saved", waiting_for_book: "Saved — waiting for the book",
  resolving: "Reading…", retrieving: "Reading…", composing: "Writing the prompt…", verifying: "Checking the source…" };

export function LiveConversation({ initialId }: { initialId: string | null }) {
  const thread = useConversation(initialId);
  const composer = useComposer(thread);
  const book = useBookPreparation(thread.view?.work_id);
  const [recent, setRecent] = useState<ConversationSummary[]>([]);
  const [notice, setNotice] = useState("");
  const { resolvedTheme, setTheme } = useTheme();
  const scroll = useRef<HTMLDivElement>(null);
  const following = useRef(true);
  const card = thread.view?.card;
  const turn = thread.view?.active_turn;
  const [history, setHistory] = useState<PromptCardHistory["items"]>([]);
  useEffect(() => {
    if (!thread.id || !card || card.revision < 2) { setHistory([]); return; }
    void api<PromptCardHistory>(`/conversations/${thread.id}/cards`).then(page => setHistory(page.items.filter(item => !item.current))).catch(() => {});
  }, [thread.id, card?.revision]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void api<ConversationPage>("/conversations").then(page => setRecent(page.items)).catch(() => {}); }, [thread.id]);
  useEffect(() => { if (following.current) scroll.current?.scrollTo({ top: scroll.current.scrollHeight }); }, [thread.messages.length, card?.revision]);
  const [pendingMoment, setPendingMoment] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const shownBefore = useRef<number | null>(null);
  async function chooseMoment(id: string, revision: number) {
    setPendingMoment(id); setAnnouncement(""); shownBefore.current = revision;
    await composer.selectVariant(id, revision);
  }
  useEffect(() => {
    if (!pendingMoment || !turn) return;
    if (turn.status === "succeeded" && card && card.revision !== shownBefore.current) {
      setAnnouncement(`Now showing ${card.specification.result.data.scope.resolved_moment ?? "the selected moment"}.`); setPendingMoment(null);
    } else if (["failed", "insufficient_evidence", "needs_context", "cancelled", "superseded"].includes(turn.status) || composer.error) {
      setAnnouncement("That moment could not be shown. Your previous prompt is unchanged."); setPendingMoment(null);
    }
  }, [turn?.status, card?.revision, composer.error]); // eslint-disable-line react-hooks/exhaustive-deps
  async function copy() {
    if (!card) return;
    try { await navigator.clipboard.writeText(card.prompt); setNotice("Copied"); }
    catch { setNotice("Copy unavailable — select the text instead."); }
  }
  return <div className="conversation-workspace">
    <a className="skip-link" href="#conversation-main">Skip to conversation</a>
    <aside className="conversation-sidebar" aria-label="Conversation history">
      <a className="brand" href="/conversations/new"><BookOpen size={24} strokeWidth={1.5} aria-hidden="true" />Vision</a>
      <a className="secondary conversation-new" href="/conversations/new">New conversation</a>
      {recent.map(item => <a className="conversation-history" key={item.id} href={`/conversations/${item.id}`} aria-current={thread.id === item.id ? "page" : undefined}>
        <span>{item.title}<small>{item.work_title}</small></span>
      </a>)}
    </aside>
    <div className="conversation-body">
      <header className="conversation-header"><span>{thread.view?.work_title ?? "Your private workspace"}</span>
        <button type="button" className="secondary conversation-theme" aria-label="Switch color theme" onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}>
          {resolvedTheme === "dark" ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
        </button>
      </header>
      <main id="conversation-main" tabIndex={-1} className="conversation-main">
        <div className="conversation-thread" ref={scroll} onScroll={() => { const node = scroll.current; if (node) following.current = node.scrollHeight - node.scrollTop - node.clientHeight < 100; }}>
          {!thread.messages.length && <div className="conversation-intro"><h1>What would you like to see?</h1></div>}
          <ol className="conversation-messages" aria-label="Conversation messages">{thread.messages.map(item => <li key={item.id} className={`conversation-message ${item.role}`}>
            <span className="sr-only">{item.role === "user" ? "You" : "Vision"}</span><p>{item.content}</p>
          </li>)}</ol>
          <div className="conversation-status" role="status" aria-live="polite">
            {(() => { const line = composer.busy ? (thread.id ? "Saving…" : "Attaching your book…")
              : turn && stages[turn.status] ? stages[turn.status] : book.text && !(book.ready && card) ? book.text : "";
              return line && <p>{line}</p>; })()}
          </div>
          {book.failed && <div className="conversation-actions">
            {book.retryable && !composer.preparationBlocked && turn?.error_code === "BOOK_PREPARATION_FAILED" && <button type="button" className="secondary" disabled={composer.busy} onClick={() => void composer.retryPreparation()}>Retry preparation</button>}
            <a className="conversation-link" href="/conversations/new">Replace book</a>
          </div>}
          {card && thread.view && <ActiveCard card={card} conversationId={thread.view.id} workId={thread.view.work_id} history={history} busy={composer.busy || (!!turn && !!stages[turn.status])}
            pending={pendingMoment} onCopy={() => void copy()} onVariant={id => void chooseMoment(id, card.revision)} />}
          {(thread.error || composer.error) && <div role="alert" className="conversation-status conversation-error"><p>{composer.error || thread.error}</p>
            {composer.uncertain && <button className="secondary" type="button" onClick={() => void composer.send()}>Retry request</button>}
            {(composer.stale || thread.error) && <button className="secondary" type="button" onClick={() => void composer.reload()}>Refresh conversation</button>}
          </div>}
        </div>
        <ConversationComposer draft={composer.draft} onDraft={composer.setDraft} file={composer.file} onFile={composer.setFile}
          title={thread.view?.work_title} canAttach={!thread.id} sending={composer.busy} blocked={composer.stale || composer.uncertain || (!!thread.id && !thread.view)} onSend={() => void composer.send()} />
        {notice && <p className="conversation-notice" role="status">{notice}</p>}
        <p className="sr-only" role="status" aria-live="polite">{announcement}</p>
      </main>
    </div>
  </div>;
}
