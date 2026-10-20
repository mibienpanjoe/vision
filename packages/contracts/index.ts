/* Generated from Python Pydantic models. Run pnpm --dir packages/contracts generate. */

/**
 * @minItems 2
 * @maxItems 2
 */
export type FactIds = [string, string];
export type Status = "unresolved";
export type Conflicts = ConflictView[];
export type Label = string;
export type DocumentRevisionId = string;
export type End = number;
export type OffsetUnit = "unicode_code_point";
export type PassageId = string;
export type Quote = string;
export type Start = number;
export type Status1 = "supported" | "candidate";
export type Aliases = AliasView[];
export type Id = string;
export type Kind = "character" | "place" | "object" | "organization";
/**
 * A name used by an eligible mention
 */
export type Label1 = string;
export type MentionCount = number;
export type Relation = "before" | "after" | "during" | "overlaps" | "unknown";
export type SourceId = string;
export type TargetId = string;
export type EventRelations = EventRelationView[];
export type Kind1 = "age" | "date" | "relative";
export type Value = string;
export type Anchors = AnchorView[];
export type Evidence = SourceSpan[];
export type Id1 = string;
export type Label2 = string;
export type Modality = string;
export type ParticipantIds = string[];
export type Events = EventView[];
export type Assumption = string | null;
export type Attribute = string;
export type Canonical = boolean;
export type EventIds = string[];
export type Evidence1 = SourceSpan[];
export type Id2 = string;
export type Kind2 = "identity" | "acquired" | "interval" | "scene";
export type Modality1 = string;
export type Perspective = string | null;
export type Polarity = "affirmed" | "negated";
export type Support = "explicit" | "inferred";
export type Value1 = string;
export type Facts = FactView[];
export type CandidateIds = string[];
/**
 * Set only when the source supports one identity
 */
export type EntityId = string | null;
/**
 * @maxItems 200
 */
export type Mentions = MentionView[];
export type MentionsTruncated = boolean;
export type ObjectId = string;
export type Relation1 = string;
export type SubjectId = string;
export type Relations = RelationView[];
export type GenerationId = string;
export type ParserRevision = string;
/**
 * Reading cutoff; null means the whole book
 */
export type ThroughChapterId = string | null;
export type Items = EntitySummary[];
export type Code = string;
export type CorrelationId = string;
export type Message = string;
export type Retryable = boolean;
export type ChapterId = string | null;
export type Excerpt = string;
export type ExcerptStart = number;
export type HighlightEnd = number;
export type HighlightStart = number;
export type OriginalEnd = number;
export type OriginalStart = number;
/**
 * Source pages of the containing passage, when the format has pages
 */
export type Pages = number[] | null;
export type ParserRevision1 = string;
/**
 * Content document and fragment of the containing passage, for EPUB
 */
export type Section = string | null;
export type ContextAfter = number;
export type ContextBefore = number;
export type ParserRevision2 = string;
export type ReadingBoundary = WholeBook | ThroughChapter;
export type Mode = "whole_book";
export type ChapterId1 = string;
export type Mode1 = "through_chapter";
export type DocumentRevisionId1 = string;
export type End1 = number;
export type OffsetUnit1 = "unicode_code_point";
export type PassageId1 = string;
export type Quote1 = string;
export type Start1 = number;
export type Attempts = number;
export type CancelRequested = boolean;
export type CorrelationId1 = string;
export type DispatchPending = boolean;
export type DocumentId = string;
export type ErrorCode = string | null;
export type Id3 = string;
export type Revision = number;
export type Stage = "awaiting_parser" | "parse" | "parsed" | "failed" | "cancelled";
export type Status2 = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type Warnings = string[];
export type Attempts1 = number;
export type CorrelationId2 = string;
export type DispatchPending1 = boolean;
export type Id4 = string;
export type Result = number | null;
export type Stage1 = "queued" | "complete";
export type Status3 = "queued" | "succeeded";
export type ByteCount = number;
export type CurrentParserRevision = string | null;
export type DocumentId1 = string;
export type Format = "txt" | "md" | "pdf" | "epub";
export type Id5 = string;
export type Revision1 = number;
export type Sha256 = string;
export type Title = string;
export type Items1 = WorkView[];
export type NextCursor = string | null;
export type Password = string;
export type Username = string;
export type Id6 = string;
export type Username1 = string;
export type Kind3 = "probe";
export type Value2 = number;
export type CreativeMode = "canon_first" | "interpretation";
export type DocumentRevisionId2 = string;
export type GenerationId1 = string;
export type ReadingBoundary1 = WholeBook | ThroughChapter;
export type StoryEventId = string | null;
export type WorkId = string;
export type SpanResolution = ResolvedSourceSpan | NeedsContext | InsufficientEvidence | Failed;
export type Outcome = "resolved";
export type SchemaVersion = "1.0";
/**
 * @minItems 1
 */
export type Choices = [ContextChoice, ...ContextChoice[]];
export type Id7 = string;
export type Label3 = string;
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
export type Format1 = "txt" | "md" | "pdf" | "epub";
export type Title1 = string;

/**
 * Build-time export root only; this is not an HTTP request/response.
 */
export interface SchemaCatalog {
  entity_detail: EntityDetail;
  entity_page: EntityPage;
  error: ErrorEnvelope;
  evidence: EvidenceView;
  evidence_request: EvidenceRequest;
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
export interface EntityDetail {
  conflicts: Conflicts;
  entity: EntitySummary;
  event_relations: EventRelations;
  events: Events;
  facts: Facts;
  mentions: Mentions;
  mentions_truncated: MentionsTruncated;
  relations: Relations;
  scope: NarrativeScope;
}
export interface ConflictView {
  fact_ids: FactIds;
  status: Status;
}
export interface EntitySummary {
  aliases: Aliases;
  id: Id;
  kind: Kind;
  label: Label1;
  mention_count: MentionCount;
}
export interface AliasView {
  label: Label;
  span: SourceSpan;
  status: Status1;
}
export interface SourceSpan {
  document_revision_id: DocumentRevisionId;
  end: End;
  offset_unit?: OffsetUnit;
  passage_id: PassageId;
  quote: Quote;
  start: Start;
}
export interface EventRelationView {
  relation: Relation;
  source_id: SourceId;
  span: SourceSpan;
  target_id: TargetId;
}
export interface EventView {
  anchors: Anchors;
  evidence: Evidence;
  id: Id1;
  label: Label2;
  modality: Modality;
  participant_ids: ParticipantIds;
}
export interface AnchorView {
  kind: Kind1;
  span: SourceSpan;
  value: Value;
}
export interface FactView {
  assumption: Assumption;
  attribute: Attribute;
  canonical: Canonical;
  event_ids: EventIds;
  evidence: Evidence1;
  id: Id2;
  kind: Kind2;
  modality: Modality1;
  perspective: Perspective;
  polarity: Polarity;
  support: Support;
  value: Value1;
}
export interface MentionView {
  candidate_ids: CandidateIds;
  entity_id: EntityId;
  span: SourceSpan;
}
export interface RelationView {
  object_id: ObjectId;
  relation: Relation1;
  span: SourceSpan;
  subject_id: SubjectId;
}
export interface NarrativeScope {
  generation_id: GenerationId;
  parser_revision: ParserRevision;
  through_chapter_id: ThroughChapterId;
}
export interface EntityPage {
  items: Items;
  scope: NarrativeScope;
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
export interface EvidenceView {
  chapter_id: ChapterId;
  excerpt: Excerpt;
  excerpt_start: ExcerptStart;
  highlight_end: HighlightEnd;
  highlight_start: HighlightStart;
  original_end: OriginalEnd;
  original_start: OriginalStart;
  pages: Pages;
  parser_revision: ParserRevision1;
  section: Section;
  span: SourceSpan;
}
export interface EvidenceRequest {
  context_after?: ContextAfter;
  context_before?: ContextBefore;
  parser_revision: ParserRevision2;
  reading_boundary: ReadingBoundary;
  span: EvidenceSpan;
}
export interface WholeBook {
  mode: Mode;
}
export interface ThroughChapter {
  chapter_id: ChapterId1;
  mode: Mode1;
}
export interface EvidenceSpan {
  document_revision_id: DocumentRevisionId1;
  end: End1;
  offset_unit?: OffsetUnit1;
  passage_id: PassageId1;
  quote: Quote1;
  start: Start1;
}
export interface IngestionView {
  attempts: Attempts;
  cancel_requested: CancelRequested;
  correlation_id: CorrelationId1;
  dispatch_pending: DispatchPending;
  document_id: DocumentId;
  error_code: ErrorCode;
  id: Id3;
  revision: Revision;
  stage: Stage;
  status: Status2;
  warnings: Warnings;
}
export interface JobView {
  attempts: Attempts1;
  correlation_id: CorrelationId2;
  dispatch_pending: DispatchPending1;
  id: Id4;
  result: Result;
  stage: Stage1;
  status: Status3;
}
export interface LibraryPage {
  items: Items1;
  next_cursor: NextCursor;
}
export interface WorkView {
  byte_count: ByteCount;
  current_parser_revision: CurrentParserRevision;
  document_id: DocumentId1;
  format: Format;
  id: Id5;
  revision: Revision1;
  sha256: Sha256;
  title: Title;
}
export interface LoginRequest {
  password: Password;
  username: Username;
}
export interface PrincipalView {
  id: Id6;
  username: Username1;
}
export interface ProbeRequest {
  kind?: Kind3;
  value?: Value2;
}
export interface RequestScope {
  creative_mode: CreativeMode;
  document_revision_id: DocumentRevisionId2;
  generation_id: GenerationId1;
  reading_boundary: ReadingBoundary1;
  story_event_id?: StoryEventId;
  work_id: WorkId;
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
  id: Id7;
  label: Label3;
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
