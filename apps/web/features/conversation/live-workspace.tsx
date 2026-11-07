"use client";

import { BookOpen, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useRef, useState } from "react";
import { api, type ConversationPage, type ConversationSummary } from "@/lib/api";
import { ConversationComposer } from "./composer";
import { useConversation } from "./use-conversation";
import { useComposer } from "./use-composer";
import { useBookPreparation } from "./book-attachment";

const stages: Record<string, string> = { queued: "Your request is saved.", waiting_for_book: "Your question is saved while the book is prepared.",
  resolving: "Finding the subject…", retrieving: "Finding supporting passages…", composing: "Preparing your prompt…", verifying: "Checking the source details…" };

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
  useEffect(() => { void api<ConversationPage>("/conversations").then(page => setRecent(page.items)).catch(() => {}); }, [thread.id]);
  useEffect(() => { if (following.current) scroll.current?.scrollTo({ top: scroll.current.scrollHeight }); }, [thread.messages.length, card?.revision]);
  async function copy() {
    if (!card) return;
    try { await navigator.clipboard.writeText(card.prompt); setNotice(`Prompt version ${card.revision} copied.`); }
    catch { setNotice("Copy was unavailable. Select the prompt text to copy it."); }
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
          <div className="conversation-intro"><p className="eyebrow">Your book, brought into view</p><h1>What would you like to see?</h1>
            {!thread.view && <p>Attach a book and ask in your own words.</p>}
          </div>
          <ol className="conversation-messages" aria-label="Conversation messages">{thread.messages.map(item => <li key={item.id} className={`conversation-message ${item.role}`}>
            <span className="conversation-speaker">{item.role === "user" ? "You" : "Vision"}</span><p>{item.content}</p>
          </li>)}</ol>
          <div className="conversation-status" role="status" aria-live="polite">
            {composer.busy && <p>{thread.id ? "Saving your request…" : "Attaching your book…"}</p>}
            {book.text && <p>{book.text}</p>}{turn && stages[turn.status] && <p>{stages[turn.status]}</p>}
            {turn?.status === "insufficient_evidence" && <p>The book does not establish enough detail for this portrayal. Try another moment or subject.</p>}
            {turn?.status === "needs_context" && <p>More context is needed to choose a supported portrayal.</p>}
          </div>
          {book.failed && <div className="conversation-actions">
            {book.retryable && !composer.preparationBlocked && turn?.error_code === "BOOK_PREPARATION_FAILED" && <button type="button" className="secondary" disabled={composer.busy} onClick={() => void composer.retryPreparation()}>Retry preparation</button>}
            <a className="conversation-link" href="/conversations/new">Replace book</a>
          </div>}
          {card && <section className="conversation-card" aria-labelledby="prompt-heading"><div className="conversation-card-heading"><h2 id="prompt-heading">Your image prompt</h2><span>Version {card.revision}</span></div>
            <p className="conversation-prompt" data-testid="active-prompt">{card.prompt}</p><button type="button" onClick={() => void copy()}>Copy prompt</button>
          </section>}
          {(thread.error || composer.error) && <div role="alert" className="conversation-status conversation-error"><p>{composer.error || thread.error}</p>
            {composer.uncertain && <button className="secondary" type="button" onClick={() => void composer.send()}>Retry request</button>}
            {(composer.stale || thread.error) && <button className="secondary" type="button" onClick={() => void composer.reload()}>Refresh conversation</button>}
          </div>}
        </div>
        <ConversationComposer draft={composer.draft} onDraft={composer.setDraft} file={composer.file} onFile={composer.setFile}
          title={thread.view?.work_title} canAttach={!thread.id} sending={composer.busy} blocked={composer.stale || composer.uncertain || (!!thread.id && !thread.view)} onSend={() => void composer.send()} />
        {notice && <p className="conversation-notice" role="status">{notice}</p>}
      </main>
    </div>
  </div>;
}
