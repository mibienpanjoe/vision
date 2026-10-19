import type { SourceSpan } from "./index.js";

export function validateSpan(span: SourceSpan): void {
  if (!Number.isInteger(span.start) || !Number.isInteger(span.end) ||
      span.start < 0 || span.end <= span.start ||
      Array.from(span.quote).length !== span.end - span.start) {
    throw new Error("Span length must match its nonempty code-point quote");
  }
}

export function sourceSlice(text: string, span: SourceSpan): string {
  validateSpan(span);
  const points = Array.from(text);
  const quote = points.slice(span.start, span.end).join("");
  if (span.end > points.length || quote !== span.quote) {
    throw new Error("Source span does not match immutable passage text");
  }
  return quote;
}
