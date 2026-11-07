"use client";

import type { ConversationMessageView, TurnView } from "@/lib/api";

const retryable = new Set(["TURN_FAILED", "TURN_ATTEMPTS_EXHAUSTED", "PROVIDER_UNAVAILABLE", "PROVIDER_TIMEOUT",
  "PROVIDER_RATE_LIMITED", "PROVIDER_INVALID_OUTPUT"]);

/** Context-specific recovery for a settled turn that did not produce a new prompt. */
export function TurnRecovery({ turn, messages, busy, onAsk }: {
  turn: TurnView; messages: ConversationMessageView[]; busy: boolean; onAsk: (text: string, choice?: string) => void;
}) {
  const result = turn.result;
  if (turn.status === "needs_context" && result?.outcome === "needs_context") {
    return <div className="conversation-variants" role="group" aria-label="Which did you mean?">
      {result.choices.map((choice, index) => <button type="button" className="conversation-moment" key={choice.id} disabled={busy}
        onClick={() => onAsk(choice.label, `choice:${index}`)}><strong>{choice.label}</strong>
        {choice.field && <span>{choice.field}</span>}</button>)}
    </div>;
  }
  if (turn.status === "insufficient_evidence" && result?.outcome === "insufficient_evidence") {
    return <p className="conversation-image-state">Not established in the book: {result.missing.join(" ")} Try another moment or subject.</p>;
  }
  const asked = [...messages].reverse().find(item => item.role === "user" && item.turn_id === turn.id);
  if (turn.status === "failed" && turn.error_code && (retryable.has(turn.error_code) || (result?.outcome === "failed" && result.error.retryable)) && asked) {
    return <div className="conversation-actions"><button type="button" className="secondary" disabled={busy} onClick={() => onAsk(asked.content)}>Try again</button></div>;
  }
  return null;
}
