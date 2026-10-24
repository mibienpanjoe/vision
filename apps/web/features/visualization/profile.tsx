"use client";

import type { VisualizationView } from "@/lib/api";
import { EvidenceInspector } from "./evidence-inspector";
import { exportSpecification } from "./export";

export function Profile({ view, cutoff, boundaryLabel }: { view: VisualizationView; cutoff: string | null; boundaryLabel: string }) {
  const spec = view.result.data;
  if (cutoff !== spec.scope.through_chapter_id) return <p role="alert">This result uses another reading boundary. Reconstruct it within the current scope.</p>;
  return <section className="panel profile" aria-label="Visual specification">
    <div className="library-toolbar"><h3>{spec.subject.entity.label} · {spec.scope.resolved_moment ?? "Unspecified moment"}</h3>
      <button className="secondary" onClick={() => exportSpecification(view)}>Export JSON</button></div>
    <p>{boundaryLabel} · revision {view.revision} · {spec.scope.creative_mode === "canon_first" ? "Canon first" : "Interpretation"}</p>
    {spec.scope.context && <p>Context: {spec.scope.context}</p>}
    {spec.verification.selection === "protected_overflow" && <p role="status">Some descriptive evidence did not fit the context budget, so details the book states may be missing here.</p>}
    {spec.verification.selection === "compressed" && <p role="status">Some long passages were reduced to their descriptive sentences to fit the context budget.</p>}
    <EvidenceInspector workId={view.work_id} specification={spec} cutoff={cutoff} />
    <div className="unknowns"><h4>Unknown</h4>
      {[spec.subject, ...spec.participants, ...spec.world].map((member, index) => member.unknown.length > 0 && <p key={index}>{member.entity.label}: {member.unknown.join(", ")}</p>)}
      {spec.unknown.map(value => <p key={value}>{value}</p>)}
      {![spec.subject, ...spec.participants, ...spec.world].some(member => member.unknown.length) && !spec.unknown.length && <p>No additional unknowns reported.</p>}
    </div>
    {spec.creative.length > 0 && <section aria-label="Creative additions"><h4>Creative</h4><p>Artistic choices, separate from source claims.</p><ul>{spec.creative.map((addition, index) => <li key={index}><strong>{addition.attribute}</strong>: {addition.value} · {addition.reason}</li>)}</ul></section>}
    {spec.excluded.length > 0 && <details><summary>Excluded from this view</summary><ul>{spec.excluded.map((item, index) => <li key={index}>{item.label}: {item.reason}</li>)}</ul></details>}
    <details><summary>Prompt and verification</summary><p>{spec.generation.prompt}</p>
      {spec.generation.negative_prompt && <p>Exclude: {spec.generation.negative_prompt}</p>}
      <p>Source checks applied. Additional model verification: {spec.verification.adjudication.replaceAll("_", " ")}.</p>
      {spec.verification.selection !== "complete" && <p>Evidence selection: {spec.verification.selection.replaceAll("_", " ")}. Some details may be missing.</p>}
    </details>
  </section>;
}
