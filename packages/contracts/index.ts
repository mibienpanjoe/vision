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
export type ConsolidationId = string;
export type CreatedAt = string;
export type GenerationId1 = string;
export type Number = number;
export type ParserRevision3 = string;
export type Items2 = RevisionSummary[];
export type CreativeMode = "canon_first" | "interpretation";
export type DocumentRevisionId2 = string;
export type GenerationId2 = string;
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
/**
 * Which request field the choice fills; a moment choice is resubmitted as its label
 */
export type Field = ("subject" | "moment" | "context") | null;
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
export type CreatedAt1 = string;
export type Id8 = string;
/**
 * Scene context such as "at home"
 */
export type Context = string | null;
export type CreativeMode1 = "canon_first" | "interpretation";
export type EntityId1 = string | null;
export type Moment = (AgeMoment | PhraseMoment) | null;
export type Kind4 = "age";
export type Years = number;
export type Kind5 = "phrase";
export type Text = string;
export type Query = string | null;
export type Style = string | null;
/**
 * Reading cutoff; null means the whole book
 */
export type ThroughChapterId1 = string | null;
export type Attribute1 = string;
export type Reason = string;
export type Support1 = "creative";
export type Value3 = string;
export type Creative = CreativeAddition[];
export type Label4 = string;
export type Reason1 = string;
export type Excluded = ExclusionView[];
export type NegativePrompt = string;
export type Prompt = string;
export type Style1 = string | null;
export type ConsolidationId1 = string;
/**
 * @minItems 1
 */
export type EntityIds = [string, ...string[]];
export type Kind6 = "character" | "place" | "object" | "organization";
export type Label5 = string;
export type Role = "subject" | "participant" | "place" | "object";
export type Adjudication = "unchecked" | "entailed";
export type Attribute2 = string;
export type Evidence2 = SourceSpan[];
/**
 * Why an inferred trait is not canonical
 */
export type Reason2 = string | null;
export type Status4 = "canonical" | "disputed" | "inferred";
/**
 * @minItems 1
 */
export type Values = [string, ...string[]];
export type Traits = TraitView[];
/**
 * Core traits the eligible text does not establish here
 */
export type Unknown = string[];
export type Participants = MemberView[];
export type Context1 = string | null;
export type CreativeMode2 = "canon_first" | "interpretation";
export type GenerationId3 = string;
export type Moment1 = (AgeMoment | PhraseMoment) | null;
export type ParserRevision4 = string;
/**
 * The event the text anchors the moment to
 */
export type ResolvedMoment = string | null;
/**
 * Reading cutoff; null means the whole book
 */
export type ThroughChapterId2 = string | null;
export type SpecVersion = "vision-spec-1.0";
export type Unknown1 = string[];
export type Adjudication1 = "not_requested" | "applied" | "unavailable";
/**
 * Facts removed by verification
 */
export type Removed = number;
export type Selection = "complete" | "compressed" | "truncated" | "protected_overflow";
export type World = MemberView[];
export type Outcome4 = "resolved";
export type SchemaVersion4 = "1.0";
/**
 * Current revision; also the strong ETag
 */
export type Revision2 = number;
export type WorkId1 = string;
export type VisualizationResult = ResolvedSpecification | NeedsContext | InsufficientEvidence | Failed;
export type CreatedAt2 = string;
export type Id9 = string;
export type Revision3 = number;
export type Subject = string;
export type Items3 = VisualizationSummary[];

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
  revision_page: RevisionPage;
  scope: RequestScope;
  source_span: SourceSpan;
  span_outcome: SpanResolution;
  upload_accepted: UploadAccepted;
  upload_metadata: UploadMetadata;
  visualization: VisualizationView;
  visualization_created: VisualizationCreated;
  visualization_page: VisualizationPage;
  visualization_request: VisualizationRequest;
  visualization_result: VisualizationResult;
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
export interface RevisionPage {
  items: Items2;
}
export interface RevisionSummary {
  consolidation_id: ConsolidationId;
  created_at: CreatedAt;
  generation_id: GenerationId1;
  number: Number;
  parser_revision: ParserRevision3;
}
export interface RequestScope {
  creative_mode: CreativeMode;
  document_revision_id: DocumentRevisionId2;
  generation_id: GenerationId2;
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
  field?: Field;
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
export interface VisualizationView {
  created_at: CreatedAt1;
  id: Id8;
  request: VisualizationRequest;
  result: ResolvedSpecification;
  revision: Revision2;
  work_id: WorkId1;
}
export interface VisualizationRequest {
  context?: Context;
  creative_mode?: CreativeMode1;
  entity_id?: EntityId1;
  moment?: Moment;
  query?: Query;
  style?: Style;
  through_chapter_id?: ThroughChapterId1;
}
/**
 * A story-time age of the subject; never a source position.
 */
export interface AgeMoment {
  kind: Kind4;
  years: Years;
}
/**
 * A story-time phrase such as "after the war", anchored by consolidation against cited text.
 */
export interface PhraseMoment {
  kind: Kind5;
  text: Text;
}
export interface ResolvedSpecification {
  data: VisualSpecification;
  outcome: Outcome4;
  schema_version: SchemaVersion4;
}
export interface VisualSpecification {
  creative: Creative;
  excluded: Excluded;
  generation: GenerationIntent;
  lineage: Lineage;
  participants: Participants;
  scope: ScopeView;
  spec_version: SpecVersion;
  subject: MemberView;
  unknown: Unknown1;
  verification: VerificationView;
  world: World;
}
export interface CreativeAddition {
  attribute: Attribute1;
  reason: Reason;
  support?: Support1;
  value: Value3;
}
export interface ExclusionView {
  label: Label4;
  reason: Reason1;
}
export interface GenerationIntent {
  negative_prompt: NegativePrompt;
  prompt: Prompt;
  style: Style1;
}
export interface Lineage {
  consolidation_id: ConsolidationId1;
  processing: Processing;
}
export interface Processing {
  [k: string]: string;
}
export interface MemberView {
  entity: EntityRef;
  role: Role;
  traits: Traits;
  unknown: Unknown;
}
export interface EntityRef {
  entity_ids: EntityIds;
  kind: Kind6;
  label: Label5;
}
export interface TraitView {
  adjudication?: Adjudication;
  attribute: Attribute2;
  evidence: Evidence2;
  reason?: Reason2;
  status: Status4;
  values: Values;
}
export interface ScopeView {
  context: Context1;
  creative_mode: CreativeMode2;
  generation_id: GenerationId3;
  moment: Moment1;
  parser_revision: ParserRevision4;
  resolved_moment: ResolvedMoment;
  through_chapter_id: ThroughChapterId2;
}
export interface VerificationView {
  adjudication: Adjudication1;
  removed: Removed;
  selection: Selection;
}
/**
 * 201 with `visualization` when a resolved result was stored; 200 with it null for any other outcome.
 */
export interface VisualizationCreated {
  result: VisualizationResult;
  visualization: VisualizationView | null;
}
export interface VisualizationPage {
  items: Items3;
}
export interface VisualizationSummary {
  created_at: CreatedAt2;
  id: Id9;
  revision: Revision3;
  subject: Subject;
}
