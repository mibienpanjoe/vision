/* Generated from Python Pydantic models. Run pnpm --dir packages/contracts generate. */

export type Code = string;
export type CorrelationId = string;
export type Message = string;
export type Retryable = boolean;
export type Password = string;
export type Username = string;
export type Id = string;
export type Username1 = string;
export type CreativeMode = "canon_first" | "interpretation";
export type DocumentRevisionId = string;
export type GenerationId = string;
export type ReadingBoundary = WholeBook | ThroughChapter;
export type Mode = "whole_book";
export type ChapterId = string;
export type Mode1 = "through_chapter";
export type StoryEventId = string | null;
export type WorkId = string;
export type DocumentRevisionId1 = string;
export type End = number;
export type OffsetUnit = "unicode_code_point";
export type PassageId = string;
export type Quote = string;
export type Start = number;
export type SpanResolution = ResolvedSourceSpan | NeedsContext | InsufficientEvidence | Failed;
export type Outcome = "resolved";
export type SchemaVersion = "1.0";
/**
 * @minItems 1
 */
export type Choices = [ContextChoice, ...ContextChoice[]];
export type Id1 = string;
export type Label = string;
export type Outcome1 = "needs_context";
export type SchemaVersion1 = "1.0";
/**
 * @minItems 1
 */
export type Missing = [string, ...string[]];
export type Outcome2 = "insufficient_evidence";
export type SchemaVersion2 = "1.0";
export type Outcome3 = "failed";
export type SchemaVersion3 = "1.0";

/**
 * Build-time export root only; this is not an HTTP request/response.
 */
export interface SchemaCatalog {
  error: ErrorEnvelope;
  login_request: LoginRequest;
  principal: PrincipalView;
  scope: RequestScope;
  source_span: SourceSpan;
  span_outcome: SpanResolution;
}
export interface ErrorEnvelope {
  error: SafeError;
}
export interface SafeError {
  code: Code;
  correlation_id: CorrelationId;
  message: Message;
  retryable: Retryable;
}
export interface LoginRequest {
  password: Password;
  username: Username;
}
export interface PrincipalView {
  id: Id;
  username: Username1;
}
export interface RequestScope {
  creative_mode: CreativeMode;
  document_revision_id: DocumentRevisionId;
  generation_id: GenerationId;
  reading_boundary: ReadingBoundary;
  story_event_id?: StoryEventId;
  work_id: WorkId;
}
export interface WholeBook {
  mode: Mode;
}
export interface ThroughChapter {
  chapter_id: ChapterId;
  mode: Mode1;
}
export interface SourceSpan {
  document_revision_id: DocumentRevisionId1;
  end: End;
  offset_unit?: OffsetUnit;
  passage_id: PassageId;
  quote: Quote;
  start: Start;
}
export interface ResolvedSourceSpan {
  data: SourceSpan;
  outcome: Outcome;
  schema_version: SchemaVersion;
}
export interface NeedsContext {
  choices: Choices;
  outcome: Outcome1;
  schema_version: SchemaVersion1;
}
export interface ContextChoice {
  id: Id1;
  label: Label;
}
export interface InsufficientEvidence {
  missing: Missing;
  outcome: Outcome2;
  schema_version: SchemaVersion2;
}
export interface Failed {
  error: SafeError;
  outcome: Outcome3;
  schema_version: SchemaVersion3;
}
