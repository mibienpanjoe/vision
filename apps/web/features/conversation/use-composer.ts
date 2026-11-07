"use client";

import { useRef, useState } from "react";
import { api, ApiError, json, message, type ConversationView, type TurnView, type UploadAccepted } from "@/lib/api";

type Pending = { text: string; file: File | null; uploadKey: string; threadKey: string; turnKey: string; thread: ConversationView | null; workId?: string };

export function useComposer({ current, open, refresh }: {
  current: { current: ConversationView | null }; open: (view: ConversationView) => void; refresh: (id?: string | null) => Promise<void>;
}) {
  const [draft, setDraft] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const [stale, setStale] = useState(false);
  const [preparationBlocked, setPreparationBlocked] = useState(false);
  const pending = useRef<Pending | null>(null);
  const retryKey = useRef<{ key: string; revision: number; id: string } | null>(null);

  async function send() {
    if (busy || stale) return;
    if (!pending.current) {
      if (!current.current && !file) { setError("Attach a book to start."); return; }
      if (!draft.trim() && !file) return;
      pending.current = { text: draft, file, uploadKey: crypto.randomUUID(), threadKey: crypto.randomUUID(), turnKey: crypto.randomUUID(), thread: current.current };
    }
    const snapshot = pending.current;
    setBusy(true); setError(""); setUncertain(false);
    try {
      if (!snapshot.thread) {
        if (!snapshot.workId) {
          const form = new FormData(); form.set("file", snapshot.file!);
          const uploaded = await api<UploadAccepted>("/works", { method: "POST", headers: { "Idempotency-Key": snapshot.uploadKey }, body: form });
          snapshot.workId = uploaded.work.id;
        }
        snapshot.thread = await api<ConversationView>("/conversations", json({ work_id: snapshot.workId,
          title: snapshot.text.replace(/[\u0000-\u001f]/g, " ").trim().replace(/\s+/g, " ").slice(0, 160) || "New conversation" }, snapshot.threadKey));
        open(snapshot.thread);
      }
      if (snapshot.text.trim()) {
        const request = json({ text: snapshot.text }, snapshot.turnKey);
        await api<TurnView>(`/conversations/${snapshot.thread.id}/turns`, { ...request,
          headers: { ...request.headers, "If-Match": `"${snapshot.thread.revision}"` } });
      }
      pending.current = null; setFile(null); setDraft(previous => previous === snapshot.text ? "" : previous);
      await refresh(snapshot.thread.id).catch(() => {});
    } catch (error) {
      setError(message(error));
      if (error instanceof ApiError && error.status === 412) { pending.current = null; setStale(true); }
      else if (error instanceof ApiError && error.status > 0 && error.status < 500) pending.current = null;
      else setUncertain(true);
    } finally { setBusy(false); }
  }
  async function reload() {
    try { await refresh(); setStale(false); setError(""); } catch { /* The owned read reports its failure. */ }
  }
  async function retryPreparation() {
    const view = current.current;
    if (!view || busy || stale) return;
    retryKey.current ||= { key: crypto.randomUUID(), revision: view.revision, id: view.id };
    const attempt = retryKey.current;
    setBusy(true); setError("");
    try {
      const request = json({}, attempt.key);
      await api<TurnView>(`/conversations/${attempt.id}/preparation-retries`, { ...request,
        headers: { ...request.headers, "If-Match": `"${attempt.revision}"` } });
      retryKey.current = null;
      await refresh(attempt.id).catch(() => {});
    } catch (error) {
      setError(message(error));
      if (error instanceof ApiError && error.status === 412) { retryKey.current = null; setStale(true); }
      if (error instanceof ApiError && ["ATTEMPTS_EXHAUSTED", "PREPARATION_NOT_RETRYABLE"].includes(error.code)) setPreparationBlocked(true);
    } finally { setBusy(false); }
  }
  return { draft, setDraft, file, setFile, busy, error, uncertain, stale, preparationBlocked, send, reload, retryPreparation };
}
