"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, message, type ConversationMessagePage, type ConversationMessageView, type ConversationView } from "@/lib/api";
import { useSession } from "@/components/session-provider";

const terminal = new Set(["succeeded", "failed", "needs_context", "insufficient_evidence", "superseded", "cancelled"]);

export function useConversation(initialId: string | null) {
  const { retry } = useSession();
  const [id, setId] = useState(initialId);
  const [view, setView] = useState<ConversationView | null>(null);
  const [messages, setMessages] = useState<ConversationMessageView[]>([]);
  const [error, setError] = useState("");
  const currentId = useRef(initialId);
  const current = useRef<ConversationView | null>(null);
  const accept = useCallback((value: ConversationView) => {
    if (value.id !== currentId.current || (current.current && value.revision < current.current.revision)) return false;
    current.current = value; setView(value); return true;
  }, []);
  const refresh = useCallback(async (target = currentId.current) => {
    if (!target) return;
    try {
      const head = await api<ConversationView>(`/conversations/${target}`);
      const rows = await api<ConversationMessagePage>(`/conversations/${target}/messages?limit=50`);
      if (currentId.current !== target) return;
      if (accept(head)) setMessages(rows.items.filter(item => item.sequence <= head.last_sequence));
      setError("");
    } catch (error) {
      if (currentId.current !== target) return;
      setError(message(error));
      if (error instanceof ApiError && error.status === 401) retry();
      if (error instanceof ApiError && error.status === 404) { current.current = null; setView(null); setMessages([]); }
      throw error;
    }
  }, [accept, retry]);
  useEffect(() => { if (id) void refresh(id).catch(() => {}); }, [id, refresh]);
  const busy = !!view?.active_turn && !terminal.has(view.active_turn.status);
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => void refresh().catch(() => {}), 1000);
    return () => clearInterval(timer);
  }, [busy, refresh]);
  const open = useCallback((value: ConversationView) => {
    currentId.current = value.id; current.current = value; setView(value); setId(value.id); setMessages([]); setError("");
    history.replaceState(null, "", `/conversations/${value.id}`);
  }, []);
  return { id, view, current, messages, error, busy, refresh, open };
}
