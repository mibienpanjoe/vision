import type { SourceSpan } from "@/lib/api";

export type EvidenceTarget = { id: string; label: string; span: SourceSpan };

export function highlightSegments(text: string, excerptStart: number, targets: EvidenceTarget[]) {
  const points = Array.from(text);
  const anchors = targets.map(target => ({ ...target, start: target.span.start - excerptStart, end: target.span.end - excerptStart }))
    .filter(target => target.start >= 0 && target.end <= points.length && target.end > target.start &&
      points.slice(target.start, target.end).join("") === target.span.quote);
  const boundaries = [...new Set([0, points.length, ...anchors.flatMap(anchor => [anchor.start, anchor.end])])].sort((a, b) => a - b);
  return boundaries.slice(0, -1).map((start, index) => {
    const end = boundaries[index + 1];
    return { start, end, text: points.slice(start, end).join(""),
      ids: anchors.filter(anchor => anchor.start <= start && anchor.end >= end).map(anchor => anchor.id) };
  });
}
