"use client";

import { BookOpen, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, message, type GenerationPage, type IngestionView } from "@/lib/api";

const fatal = new Set(["TEXT_LAYER_UNAVAILABLE", "PDF_ENCRYPTED", "PARSER_LIMIT", "UNSUPPORTED_FORMAT", "SOURCE_INTEGRITY", "INVALID_SOURCE", "NO_PASSAGES"]);
export function useBookPreparation(workId: string | undefined) {
  const [status, setStatus] = useState<{ ready: boolean; failed: boolean; retryable: boolean; text: string }>({ ready: false, failed: false, retryable: false, text: "" });
  useEffect(() => {
    if (!workId) { setStatus({ ready: false, failed: false, retryable: false, text: "" }); return; }
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const page = await api<GenerationPage>(`/works/${workId}/generations`);
        const generation = page.items.find(item => item.current) ?? page.items.at(-1);
        if (!active || !generation) return;
        const failed = ["failed", "cancelled"].includes(generation.status) || generation.narrative_status === "failed";
        if (failed) {
          const job = await api<IngestionView>(`/works/${workId}/ingestions/${generation.job_id}`);
          if (!active) return;
          const code = job.error_code ?? generation.narrative_error;
          setStatus({ ready: false, failed: true, retryable: !fatal.has(code ?? ""), text: code === "TEXT_LAYER_UNAVAILABLE" ?
            "This PDF has no extractable text. Attach a text PDF, EPUB or text file." : code === "PDF_ENCRYPTED" ?
              "This PDF is encrypted. Attach an unlocked copy." : "That book could not be prepared." });
          timer = setTimeout(load, 2000); return;
        }
        const ready = generation.narrative_ready && generation.search_ready;
        setStatus({ ready, failed: false, retryable: false, text: ready ? "Book ready" : !generation.parsed ? "Reading your book…" : "Preparing your book…" });
        if (!ready) timer = setTimeout(load, 2000);
      } catch (error) {
        if (active) { setStatus(previous => ({ ...previous, text: message(error) })); timer = setTimeout(load, 2000); }
      }
    }
    void load();
    return () => { active = false; clearTimeout(timer); };
  }, [workId]);
  return status;
}

export function BookAttachment({ title, file, onRemove, disabled }: { title?: string; file: File | null; onRemove: () => void; disabled: boolean }) {
  if (!title && !file) return null;
  return <div className="conversation-attachment"><BookOpen size={18} strokeWidth={1.5} aria-hidden="true" />
    <span>{title ?? file!.name}</span>{file && <button type="button" className="conversation-link" aria-label="Remove attachment" disabled={disabled} onClick={onRemove}><X size={16} aria-hidden="true" /></button>}
  </div>;
}
