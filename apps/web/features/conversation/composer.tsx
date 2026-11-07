"use client";

import { ArrowUp, Paperclip } from "lucide-react";
import type { FormEvent } from "react";
import { BookAttachment } from "./book-attachment";

export function ConversationComposer({ draft, onDraft, file, onFile, title, sending, blocked, canAttach, onSend }: {
  draft: string; onDraft: (value: string) => void; file: File | null; onFile: (value: File | null) => void;
  title?: string; canAttach: boolean; sending: boolean; blocked: boolean; onSend: () => void;
}) {
  function submit(event: FormEvent) { event.preventDefault(); onSend(); }
  return <form className="conversation-composer" aria-label="Conversation composer" onSubmit={submit}
    onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); if (canAttach && !title && !sending && !blocked && event.dataTransfer.files.length === 1) onFile(event.dataTransfer.files[0]); }}>
    <BookAttachment title={title} file={file} disabled={sending || blocked} onRemove={() => onFile(null)} />
    <label className="sr-only" htmlFor="message">Message</label>
    <textarea id="message" value={draft} maxLength={4000} onChange={event => onDraft(event.target.value)}
      onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (!sending && !blocked) onSend(); } }} placeholder="Describe who or what you want to see…" />
    <div className="conversation-composer-actions">
      {canAttach && !title && <label className="conversation-attach"><Paperclip size={20} strokeWidth={1.5} aria-hidden="true" /><span>Attach book</span>
        <input type="file" aria-label="Book file" accept=".txt,.md,.pdf,.epub" disabled={sending || blocked} onChange={event => { onFile(event.target.files?.[0] ?? null); event.target.value = ""; }} />
      </label>}
      <button type="submit" aria-label="Send" disabled={sending || blocked || (!draft.trim() && !file)}><ArrowUp size={20} strokeWidth={1.5} aria-hidden="true" /></button>
    </div>
  </form>;
}
