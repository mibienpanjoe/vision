"use client";

import { useRef, useState } from "react";
import type { EntitySummary, VisualizationCreated, VisualizationView } from "@/lib/api";
import { Composer } from "./composer";
import { Profile } from "./profile";
import { History } from "./history";
import { Refinement } from "./refinement";

export function ReconstructionWorkspace({ workId, entity, cutoff, boundaryLabel, generationId }: {
  workId: string; entity: EntitySummary; cutoff: string | null; boundaryLabel: string; generationId: string;
}) {
  const [result, setResult] = useState<VisualizationCreated | null>(null);
  const [view, setView] = useState<VisualizationView | null>(null);
  const [current, setCurrent] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [composing, setComposing] = useState(false);
  const [selection, setSelection] = useState(0);
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
  return <>
    <Composer workId={workId} entity={entity} cutoff={cutoff} result={result} onResult={composed} onBusy={setComposing} />
    <History workId={workId} generationId={generationId} cutoff={cutoff} refresh={refresh} disabled={composing} onSelect={(view, current) => {
      if (activeSelection.current !== selection) return;
      advance(); setResult(null); setView(view); setCurrent(current);
    }} />
    {view && <>
      {!current && <p role="status">Historical revision. Open the current revision from saved specifications to refine it.</p>}
      <Profile key={`${view.id}/${view.revision}`} view={view} cutoff={cutoff} boundaryLabel={boundaryLabel} />
      {current && <Refinement key={view.id} view={view} generationId={generationId} cutoff={cutoff} onSaved={saved} />}
    </>}
  </>;
}
