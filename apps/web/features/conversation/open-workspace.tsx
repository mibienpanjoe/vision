"use client";

import { useEffect } from "react";
import { api, type ConversationPage } from "@/lib/api";

/** Opens straight into the remembered workspace: the latest conversation, or a new one. */
export function OpenWorkspace() {
  useEffect(() => {
    void api<ConversationPage>("/conversations?limit=1")
      .then(page => location.replace(page.items[0] ? `/conversations/${page.items[0].id}` : "/conversations/new"))
      .catch(() => location.replace("/conversations/new"));
  }, []);
  return <main className="conversation-intro" aria-busy="true"><p role="status">Opening your workspace…</p></main>;
}
