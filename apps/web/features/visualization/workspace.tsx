"use client";

import { useState } from "react";
import type { EntitySummary, VisualizationCreated } from "@/lib/api";
import { Composer } from "./composer";
import { Profile } from "./profile";

export function ReconstructionWorkspace({ workId, entity, cutoff, boundaryLabel }: {
  workId: string; entity: EntitySummary; cutoff: string | null; boundaryLabel: string;
}) {
  const [result, setResult] = useState<VisualizationCreated | null>(null);
  return <>
    <Composer workId={workId} entity={entity} cutoff={cutoff} result={result} onResult={setResult} />
    {result?.visualization && <Profile key={`${result.visualization.id}/${result.visualization.revision}`} view={result.visualization} cutoff={cutoff} boundaryLabel={boundaryLabel} />}
  </>;
}
