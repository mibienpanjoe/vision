"use client";

import { useRef, useState } from "react";
import { api, message, type EntitySummary, type VisualizationCreated, type VisualizationView } from "@/lib/api";
import { Composer } from "./composer";
import { Profile } from "./profile";
import { History, historyScope } from "./history";
import { Refinement } from "./refinement";
import { RenderHistory } from "./render-history";

export function ReconstructionWorkspace({ workId, entity, cutoff, boundaryLabel, generationId }: {
  workId: string; entity: EntitySummary; cutoff: string | null; boundaryLabel: string; generationId: string;
}) {
  const [result, setResult] = useState<VisualizationCreated | null>(null);
  const [view, setView] = useState<VisualizationView | null>(null);
  const [current, setCurrent] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [composing, setComposing] = useState(false);
  const [selection, setSelection] = useState(0);
  const [openError, setOpenError] = useState("");
  const activeSelection = useRef(0);
  function advance() { activeSelection.current += 1; setSelection(activeSelection.current); }
  function composed(result: VisualizationCreated | null) {
    advance();
    setResult(result); setView(result?.visualization ?? null); setCurrent(true);
    if (result?.visualization) setRefresh(value => value + 1);
  }
  function saved(view: VisualizationView) {
    if (activeSelection.current !== selection) return;
    advance(); setResult(null); setView(view); setCurrent(true); setRefresh(value => value + 1);
  }
  async function openRevision(id: string, number: number) {
    const scope = historyScope(generationId, cutoff);
    const started = activeSelection.current;
    setOpenError("");
    try {
      const [revision, head] = await Promise.all([
        api<VisualizationView>(`/works/${workId}/visualizations/${id}/revisions/${number}${scope}`),
        api<VisualizationView>(`/works/${workId}/visualizations/${id}${scope}`)]);
      if (activeSelection.current !== started) return;
      advance(); setResult(null); setView(revision); setCurrent(revision.revision === head.revision);
    } catch (error) { setOpenError(message(error)); }
  }
  return <>
    <Composer workId={workId} entity={entity} cutoff={cutoff} result={result} onResult={composed} onBusy={setComposing} />
    <History workId={workId} generationId={generationId} cutoff={cutoff} refresh={refresh} disabled={composing} onSelect={(view, current) => {
      if (activeSelection.current !== selection) return;
      advance(); setResult(null); setView(view); setCurrent(current);
    }} />
    {view && <>
      {!current && <p role="status">Historical revision. Open the current revision from saved specifications to refine it.</p>}
      <Profile key={`${view.id}/${view.revision}`} view={view} cutoff={cutoff} boundaryLabel={boundaryLabel} />
      {openError && <p role="alert">{openError}</p>}
      <RenderHistory key={`renders-${view.id}`} view={view} current={current} onOpenRevision={number => void openRevision(view.id, number)} />
      {current && <Refinement key={view.id} view={view} generationId={generationId} cutoff={cutoff} onSaved={saved} />}
    </>}
  </>;
}
