"use client";

import { useMemo, useState } from "react";
import type { SourceSpan, VisualSpecification } from "@/lib/api";
import { SourceReader } from "@/features/reader/source-reader";

export function EvidenceInspector({ workId, specification, cutoff }: { workId: string; specification: VisualSpecification; cutoff: string | null }) {
  const attributes = useMemo(() => [specification.subject, ...specification.participants, ...specification.world]
    .flatMap((member, memberIndex) => member.traits.map((trait, traitIndex) => ({
      id: `${memberIndex}/${traitIndex}`, label: `${member.entity.label} · ${trait.attribute}`, trait,
    }))), [specification]);
  const targets = useMemo(() => attributes.flatMap(attribute => attribute.trait.evidence.map(span => ({
    id: attribute.id, label: attribute.label, span,
  }))), [attributes]);
  const [selected, setSelected] = useState<string[]>([]);
  const [span, setSpan] = useState<SourceSpan | null>(null);
  if (cutoff !== specification.scope.through_chapter_id) return <p role="alert">This specification uses another reading boundary. Choose a result within the current scope.</p>;
  return <section className="evidence-inspector" aria-label="Attribute evidence">
    <h4>Inspect supporting evidence</h4>
    <ul className="evidence-attributes">{attributes.map(attribute => <li key={attribute.id}>
      <button className="secondary" disabled={!attribute.trait.evidence.length} aria-pressed={selected.includes(attribute.id)}
        onClick={() => { setSelected([attribute.id]); setSpan(attribute.trait.evidence[0]); }}>{attribute.label}: {attribute.trait.values.join(" / ")}</button>
      <p className="trait-support">{({ canonical: "Canonical", inferred: "Inferred", disputed: "Disputed" })[attribute.trait.status]}{attribute.trait.reason ? ` · ${attribute.trait.reason}` : ""}</p>
      {selected.includes(attribute.id) && attribute.trait.evidence.length > 1 && <div className="actions">{attribute.trait.evidence.map((source, index) =>
        <button className="secondary" key={index} onClick={() => setSpan(source)}>Evidence {index + 1} for {attribute.label}</button>)}</div>}
    </li>)}</ul>
    {span && <SourceReader workId={workId} parserRevision={specification.scope.parser_revision} cutoff={cutoff} span={span} targets={targets} selected={selected} onSelect={setSelected} />}
  </section>;
}
