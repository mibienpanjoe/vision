export const sampleTitle = "The House by the Ash Tree";
export const outcomes = ["ready", "preparation-error", "ambiguity", "missing-evidence", "provider-error", "stale", "image-error", "image-unknown", "storage-error"] as const;
export type Outcome = typeof outcomes[number];
export type Moment = "childhood" | "home" | "mira" | "brann";
export type Phase = "idle" | "reading" | "resolving" | "verifying" | Outcome;
export type Revision = { version: number; moment: Moment; charcoal: boolean; prompt: string };
export type SampleImage = { version: number; status: "pending" | "ready" | "error" | "unknown" };
export type Message = { role: "user" | "assistant"; text: string };
export type Preview = {
  title: string; draft: string; messages: Message[]; revisions: Revision[];
  phase: Phase; pending: string; moment: Moment; image: SampleImage | null;
};
export const initial: Preview = { title: "", draft: "", messages: [], revisions: [], phase: "idle", pending: "", moment: "childhood", image: null };

export const moments = [
  { id: "childhood" as const, title: "Before the war", difference: "Blue wool coat · unmarked cheek" },
  { id: "home" as const, title: "At home", difference: "Linen shirt · visible left-cheek scar" },
];

export const sources: Record<Moment, { chapter: string; text: string; highlight: string }> = {
  childhood: { chapter: "Chapter 1 · Before the war", text: "At ten, Arthur had chestnut hair and an unmarked left cheek. He wore a blue wool coat beside the house by the ash tree. The house had an intact slate roof.", highlight: "blue wool coat" },
  home: { chapter: "Chapter 3 · The road and the return", text: "Before dinner, Arthur removed his steel armor and put on a plain linen shirt. At dinner his left-cheek scar was still visible.", highlight: "plain linen shirt" },
  mira: { chapter: "Chapter 1 · Before the war", text: "Captain Mira carried a brass compass. Captain Brann carried a silver sword.", highlight: "Captain Mira carried a brass compass" },
  brann: { chapter: "Chapter 1 · Before the war", text: "Captain Mira carried a brass compass. Captain Brann carried a silver sword.", highlight: "Captain Brann carried a silver sword" },
};

export function revision(version: number, moment: Moment, charcoal = false): Revision {
  const appearance = {
    childhood: "Arthur at ten, with chestnut hair and an unmarked left cheek, wearing a blue wool coat.",
    home: "Arthur at the home dinner, wearing a plain linen shirt, with a visible scar on his left cheek.",
    mira: "Captain Mira carrying a brass compass.",
    brann: "Captain Brann carrying a silver sword.",
  }[moment];
  return { version, moment, charcoal, prompt: `${charcoal ? "Charcoal drawing. " : ""}${appearance}` };
}

// Controlled preview responses only; this is not production intent inference.
export function complete(state: Preview): Preview {
  const prior = state.revisions.at(-1);
  const moment = /earlier|before the war/i.test(state.pending) ? "childhood" : state.moment;
  const next = revision((prior?.version ?? 0) + 1, moment, /charcoal/i.test(state.pending) || (prior?.charcoal ?? false));
  return { ...state, phase: "ready", moment, pending: "", revisions: [...state.revisions, next].slice(-20),
    messages: [...state.messages, { role: "assistant" as const, text: prior ? "Your prompt has been updated." : "Here is a supported portrayal. Eye color is left unspecified." }].slice(-40) };
}

export function readPreview(raw: string | null): Preview | null {
  if (!raw || raw.length > 100_000) return null;
  try {
    const value: Preview = JSON.parse(raw);
    const validRevision = (item: Revision) => item && Number.isSafeInteger(item.version) && item.version > 0 &&
      Object.hasOwn(sources, item.moment) && typeof item.charcoal === "boolean" && item.prompt === revision(item.version, item.moment, item.charcoal).prompt;
    if (!value || typeof value.title !== "string" || typeof value.draft !== "string" || typeof value.pending !== "string" ||
        !Object.hasOwn(sources, value.moment) || !["idle", "reading", "resolving", "verifying", ...outcomes].includes(value.phase) ||
        !Array.isArray(value.revisions) || value.revisions.length > 20 || !value.revisions.every(validRevision) ||
        !Array.isArray(value.messages) || value.messages.length > 40 || !value.messages.every(item => item && ["user", "assistant"].includes(item.role) && typeof item.text === "string") ||
        (value.image !== null && (!value.image || !Number.isSafeInteger(value.image.version) || !["pending", "ready", "error", "unknown"].includes(value.image.status)))) return null;
    // A refresh never repeats a simulated uncertain image send.
    return { ...value, image: value.image?.status === "pending" ? { ...value.image, status: "unknown" } : value.image };
  } catch { return null; }
}

export function sampleImage(version: number) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360"><rect width="640" height="360" fill="#efede8"/><path d="M260 260V110h120v150M260 110l60-30 60 30" fill="none" stroke="#625e57" stroke-width="3"/><text x="320" y="305" text-anchor="middle" fill="#242424" font-family="serif" font-size="20">Sample only · prompt version ${version}</text></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}
