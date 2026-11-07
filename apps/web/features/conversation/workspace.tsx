"use client";

import { ArrowUp, BookOpen, Moon, Paperclip, Sun, X } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useRef, useState } from "react";
import { PromptCard } from "./prompt-card";
import { complete, initial, outcomes, readPreview, revision, sampleTitle, sources, type Moment, type Outcome, type Preview } from "./scenario-fixtures";

const storageKey = "vision-conversation-preview-v1";
const busyPhases = ["reading", "resolving", "verifying"];
const phaseText: Partial<Record<Preview["phase"], string>> = {
  reading: "Reading the sample book…", resolving: "Finding the subject and sources…", verifying: "Checking the sample prompt…",
  ready: "Your prompt has been updated.", ambiguity: "Which captain do you mean?",
  "missing-evidence": "No supported appearance for the messenger. Try Arthur or one of the captains; your earlier prompt is still available.",
  "preparation-error": "The sample book could not be read. Your request is kept.",
  "provider-error": "The response service is unavailable. Your previous prompt is kept.",
  stale: "This prompt changed in another tab. Refresh the current version before changing it.",
  "storage-error": "Preview storage is unavailable. Keep this tab open; your draft is still editable.",
};

export function ConversationPreview() {
  const [state, setState] = useState<Preview>(initial);
  const [recent, setRecent] = useState<Preview | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [outcome, setOutcome] = useState<Outcome>("ready");
  const [notice, setNotice] = useState("");
  const [storageFailed, setStorageFailed] = useState(false);
  const [drawer, setDrawer] = useState<"sources" | "versions">("sources");
  const [historical, setHistorical] = useState<number | null>(null);
  const [away, setAway] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const thread = useRef<HTMLDivElement>(null);
  const followingLatest = useRef(true);
  const fileInput = useRef<HTMLInputElement>(null);
  const draftInput = useRef<HTMLTextAreaElement>(null);
  const { resolvedTheme, setTheme } = useTheme();
  const current = state.revisions.at(-1);
  const busy = busyPhases.includes(state.phase);
  const error = ["preparation-error", "provider-error", "stale", "storage-error"].includes(state.phase);
  const status = state.image?.status === "unknown" ? "Acceptance unknown. This sample image request will not be sent again automatically." :
    state.image?.status === "error" ? "The sample image request was rejected before acceptance. You can try again explicitly." :
    state.image?.status === "pending" ? "Creating a sample image… No provider is being called." : phaseText[state.phase];

  useEffect(() => {
    if (!state.draft) draftInput.current?.scrollTo({ top: 0, left: 0 });
  }, [state.draft]);

  useEffect(() => {
    if (followingLatest.current) thread.current?.scrollTo({ top: thread.current.scrollHeight });
  }, [current?.version, state.image?.status]);

  useEffect(() => {
    try {
      const saved = readPreview(sessionStorage.getItem(storageKey)); if (saved) setState(saved);
      setRecent(readPreview(sessionStorage.getItem(`${storageKey}-recent`)));
    }
    catch { setStorageFailed(true); }
    setLoaded(true);
  }, []);

  useEffect(() => {
    if (!loaded || storageFailed) return;
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(state));
      if (recent) sessionStorage.setItem(`${storageKey}-recent`, JSON.stringify(recent));
    }
    catch { setStorageFailed(true); }
  }, [state, recent, loaded, storageFailed]);

  useEffect(() => {
    if (!busy) return;
    const timer = setTimeout(() => setState(previous => {
      if (previous.phase === "reading") return { ...previous, phase: outcome === "preparation-error" ? outcome : "resolving" };
      if (previous.phase === "resolving") return { ...previous, phase: "verifying" };
      if (["ambiguity", "missing-evidence", "provider-error"].includes(outcome)) return { ...previous, phase: outcome };
      return complete(previous);
    }), 600);
    return () => clearTimeout(timer);
  }, [state.phase, busy, outcome]);

  useEffect(() => {
    if (state.image?.status !== "pending") return;
    const timer = setTimeout(() => setState(previous => ({ ...previous, image: previous.image && {
      ...previous.image, status: outcome === "image-unknown" ? "unknown" : outcome === "image-error" ? "error" : "ready",
    } })), 700);
    return () => clearTimeout(timer);
  }, [state.image?.status, outcome]);

  function send() {
    if (busy || !state.draft.trim() || !state.title) return;
    setNotice("");
    setState(previous => ({ ...previous, pending: previous.draft.trim(), draft: "", phase: "reading",
      messages: [...previous.messages, { role: "user" as const, text: previous.draft.trim() }].slice(-40) }));
  }

  function choose(moment: Moment) {
    if (busy) return;
    setNotice("");
    if (outcome === "stale") { setState(previous => ({ ...previous, phase: "stale" })); return; }
    setState(previous => ({ ...previous, moment, pending: `Show ${moment === "mira" ? "Mira" : moment === "brann" ? "Brann" : "Arthur at this moment"}`, phase: "verifying" }));
    setOutcome("ready");
  }

  function details(kind: "sources" | "versions") {
    setDrawer(kind);
    setHistorical(null);
    dialog.current?.showModal();
  }

  async function copy() {
    if (!current) return;
    try { await navigator.clipboard.writeText(current.prompt); setNotice("Prompt copied."); }
    catch { setNotice("Copy is unavailable. Select the prompt text to copy it."); }
  }

  function attach(file: File | undefined) {
    if (!file) return;
    const extension = file.name.split(".").at(-1)?.toLowerCase();
    if (!["md", "txt", "pdf", "epub"].includes(extension ?? "")) { setNotice("Choose a TXT, Markdown, PDF or EPUB file."); return; }
    // The preview uses only the filename; source bytes never leave the browser.
    setState(previous => ({ ...initial, title: `${file.name.replace(/\.[^.]+$/, "")} · ${extension?.toUpperCase()}`,
      draft: previous.draft, pending: previous.pending, messages: previous.phase === "preparation-error" ? previous.messages : [],
      phase: previous.phase === "preparation-error" ? "reading" : "idle" }));
    if (state.phase === "preparation-error") setOutcome("ready");
    setNotice("Attachment selected for preview. The response uses the sample story.");
  }

  function retry() {
    setOutcome("ready");
    setState(previous => ({ ...previous, phase: previous.phase === "preparation-error" ? "reading" : "resolving" }));
  }

  function saveExport() {
    if (!current) return;
    const data = { kind: "controlled-preview", card: "arthur-sample", revision: current, source: sources[current.moment] };
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `sample-prompt-${current.version}.json`; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <div className="conversation-preview">
    <a className="skip-link" href="#conversation-main">Skip to conversation</a>
    <aside className="conversation-sidebar" aria-label="Conversation history">
      <a className="brand" href="/preview/conversation"><BookOpen size={24} strokeWidth={1.5} aria-hidden="true" />Vision</a>
      <button className="secondary" type="button" onClick={() => { if (state.revisions.length) setRecent(state); setState(initial); setNotice(""); setOutcome("ready"); }}>New conversation</button>
      <p className="conversation-sidebar-label">Recent</p>
      <button type="button" className="conversation-history" aria-current={state.title ? "page" : undefined}
        onClick={() => { setState(previous => recent ?? (previous.revisions.length ? previous : complete({ ...previous, title: sampleTitle, pending: "Show Arthur before the war" }))); setOutcome("ready"); }}>
        <BookOpen size={18} aria-hidden="true" /><span>{sampleTitle}<small>Arthur’s appearance</small></span>
      </button>
      <details className="conversation-controls"><summary>Preview controls</summary>
        <label>Next sample outcome<select value={outcome} onChange={event => {
          const selected = event.target.value as Outcome; setOutcome(selected);
          if (selected === "storage-error") setState(previous => ({ ...previous, phase: selected }));
        }}>{outcomes.map(value => <option key={value} value={value}>{value.replaceAll("-", " ")}</option>)}</select></label>
        <p>Controlled sample responses. No upload, text-model or image-provider requests.</p>
      </details>
    </aside>
    <div className="conversation-body">
      <header className="conversation-header"><span>Interactive preview <span aria-hidden="true">·</span> Sample story</span>
        <button type="button" className="conversation-theme secondary" disabled={!loaded} aria-label={`Switch to ${resolvedTheme === "light" ? "dark" : "light"} mode`}
          onClick={() => setTheme(resolvedTheme === "light" ? "dark" : "light")}>
          {resolvedTheme === "light" ? <Moon size={20} strokeWidth={1.75} aria-hidden="true" /> : <Sun size={20} strokeWidth={1.75} aria-hidden="true" />}
        </button>
      </header>
      <main id="conversation-main" tabIndex={-1} className="conversation-main">
        <div className="conversation-thread" ref={thread} onScroll={event => {
          const element = event.currentTarget;
          const readingEarlier = element.scrollHeight - element.scrollTop - element.clientHeight > 100;
          followingLatest.current = !readingEarlier; setAway(readingEarlier);
        }}>
          <div className="conversation-intro"><p className="eyebrow">Your book, brought into view</p><h1>What would you like to see?</h1>
            {!state.title && <><p className="muted-copy">Attach a book and describe a character or a moment.</p><button type="button" className="secondary" onClick={() => setState(previous => ({ ...previous, title: sampleTitle }))}>Try the sample book</button></>}
          </div>
          <ol className="conversation-messages" aria-label="Messages">{state.messages.map((message, index) => <li key={index} className={`conversation-message ${message.role}`}><span className="conversation-speaker">{message.role === "user" ? "You" : "Vision"}</span><p>{message.text}</p></li>)}</ol>
          {status && <div className={`conversation-status ${error || ["error", "unknown"].includes(state.image?.status ?? "") ? "conversation-error" : ""}`}
            role={error || ["error", "unknown"].includes(state.image?.status ?? "") ? "alert" : "status"}>
            <p>{status}</p>
            {state.phase === "preparation-error" && <div className="conversation-actions"><button type="button" className="secondary" onClick={retry}>Retry preparation</button><button type="button" className="conversation-link" onClick={() => fileInput.current?.click()}>Replace book</button></div>}
            {state.phase === "provider-error" && <button type="button" className="secondary" onClick={retry}>Retry response</button>}
            {state.phase === "stale" && <button type="button" className="secondary" onClick={() => { setOutcome("ready"); setState(previous => ({ ...previous, phase: "ready" })); }}>Refresh current version</button>}
            {state.phase === "storage-error" && <button type="button" className="secondary" onClick={() => { setOutcome("ready"); setState(previous => ({ ...previous, phase: "idle" })); }}>Retry storage</button>}
            {state.phase === "ambiguity" && <div className="conversation-actions"><button type="button" className="secondary" onClick={() => choose("mira")}>Mira · brass compass</button><button type="button" className="secondary" onClick={() => choose("brann")}>Brann · silver sword</button></div>}
          </div>}
          {current && <PromptCard current={current} image={state.image} busy={busy || state.phase === "stale"} onMoment={choose} onCopy={copy}
            onDetails={details} onImage={() => setState(previous => ({ ...previous, image: { version: current.version, status: "pending" } }))} />}
        </div>
        {away && <button type="button" className="conversation-latest secondary" onClick={() => thread.current?.scrollTo({ top: thread.current.scrollHeight, behavior: "instant" })}>Return to latest</button>}
        <form className="conversation-composer" onSubmit={event => { event.preventDefault(); send(); }}
          onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); attach(event.dataTransfer.files[0]); }}>
          {state.title && <p className="conversation-attachment"><BookOpen size={16} aria-hidden="true" />{state.title}</p>}
          <label className="sr-only" htmlFor="conversation-draft">Your message</label>
          <textarea ref={draftInput} id="conversation-draft" placeholder="Describe who or what you’d like to see…" maxLength={4000} rows={2} value={state.draft}
            onChange={event => setState(previous => ({ ...previous, draft: event.target.value }))} />
          <div className="conversation-composer-actions"><label className="conversation-attach" title="Attach book"><Paperclip size={20} strokeWidth={1.5} aria-hidden="true" /><span>Attach book</span>
            <input ref={fileInput} aria-label="Attach book" type="file" accept=".txt,.md,.pdf,.epub" onChange={event => attach(event.target.files?.[0])} />
          </label><span className="muted-copy">Whole book</span><button type="submit" aria-label="Send message" disabled={!loaded || busy || !state.title || !state.draft.trim()}><ArrowUp size={20} aria-hidden="true" /></button></div>
        </form>
        <p className="conversation-disclosure">Preview only. Attachments stay in your browser; responses use the sample story. Generate image shows a sample, with no charge.</p>
        {notice && <p className="conversation-notice" role="status">{notice}</p>}
        {storageFailed && <p className="conversation-notice" role="alert">Preview storage is unavailable. Keep this tab open to retain your work.</p>}
      </main>
    </div>
    <dialog className="conversation-drawer" ref={dialog} aria-labelledby="drawer-title">
      <div className="conversation-card-heading"><h2 id="drawer-title">{drawer === "sources" ? "Sources" : "Prompt versions"}</h2><button type="button" className="secondary" aria-label="Close details" onClick={() => dialog.current?.close()}><X size={18} aria-hidden="true" /></button></div>
      {drawer === "sources" && current && <><p className="muted-copy">{sources[current.moment].chapter}</p><p className="conversation-source">{sources[current.moment].text.split(sources[current.moment].highlight)[0]}<mark>{sources[current.moment].highlight}</mark>{sources[current.moment].text.split(sources[current.moment].highlight)[1]}</p><p className="muted-copy">Exact excerpt from the synthetic story. Unspecified traits stay out of the prompt.</p></>}
      {drawer === "versions" && <><p className="muted-copy">Earlier prompts remain available. Images keep their original version.</p><div className="conversation-actions">{state.revisions.map(item => <button key={item.version} type="button" className="secondary" aria-pressed={(historical ?? current?.version) === item.version} onClick={() => setHistorical(item.version)}>Version {item.version}</button>)}</div>
        <p>{historical && historical !== current?.version ? "Historical version · active prompt unchanged" : "Current version"}</p>
        <p className="conversation-prompt">{state.revisions.find(item => item.version === historical)?.prompt ?? current?.prompt}</p>
        <button type="button" className="secondary" onClick={saveExport}>Export current sample JSON</button></>}
    </dialog>
  </div>;
}
