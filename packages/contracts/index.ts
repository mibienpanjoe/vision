/* Generated from Python Pydantic models. Run pnpm --dir packages/contracts generate. */

export type Code = string;
export type CorrelationId = string;
export type Message = string;
export type Retryable = boolean;
export type CorrelationId1 = string;
export type DispatchPending = boolean;
export type DocumentId = string;
export type Id = string;
export type Stage = "awaiting_parser";
export type Status = "queued";
export type Attempts = number;
export type CorrelationId2 = string;
export type DispatchPending1 = boolean;
export type Id1 = string;
export type Result = number | null;
export type Stage1 = "queued" | "complete";
export type Status1 = "queued" | "succeeded";
export type ByteCount = number;
export type DocumentId1 = string;
export type Format = "txt" | "md";
export type Id2 = string;
export type Revision = number;
export type Sha256 = string;
export type Title = string;
export type Items = WorkView[];
export type NextCursor = string | null;
export type Password = string;
export type Username = string;
export type Id3 = string;
export type Username1 = string;
export type Kind = "probe";
export type Value = number;
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
export type Id4 = string;
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
export type Format1 = "txt" | "md";
export type Title1 = string;

/**
 * Build-time export root only; this is not an HTTP request/response.
 */
export interface SchemaCatalog {
  error: ErrorEnvelope;
  ingestion: IngestionView;
  job: JobView;
  library_page: LibraryPage;
  login_request: LoginRequest;
  principal: PrincipalView;
  probe_request: ProbeRequest;
  scope: RequestScope;
  source_span: SourceSpan;
  span_outcome: SpanResolution;
  upload_accepted: UploadAccepted;
  upload_metadata: UploadMetadata;
  work: WorkView;
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
export interface IngestionView {
  correlation_id: CorrelationId1;
  dispatch_pending: DispatchPending;
  document_id: DocumentId;
  id: Id;
  stage: Stage;
  status: Status;
}
export interface JobView {
  attempts: Attempts;
  correlation_id: CorrelationId2;
  dispatch_pending: DispatchPending1;
  id: Id1;
  result: Result;
  stage: Stage1;
  status: Status1;
}
export interface LibraryPage {
  items: Items;
  next_cursor: NextCursor;
}
export interface WorkView {
  byte_count: ByteCount;
  document_id: DocumentId1;
  format: Format;
  id: Id2;
  revision: Revision;
  sha256: Sha256;
  title: Title;
}
export interface LoginRequest {
  password: Password;
  username: Username;
}
export interface PrincipalView {
  id: Id3;
  username: Username1;
}
export interface ProbeRequest {
  kind?: Kind;
  value?: Value;
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
  id: Id4;
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
export interface UploadAccepted {
  job: IngestionView;
  work: WorkView;
}
export interface UploadMetadata {
  format: Format1;
  title: Title1;
}
