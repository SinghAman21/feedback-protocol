/**
 * TypeScript types for the Feedback Protocol v0.1.
 *
 * These types mirror `schema/feedback.schema.json` exactly. Only `type`
 * and `summary` are required; every other field is optional so reporters
 * are never forced to speculate about internals they cannot know.
 *
 * Unknown fields are accepted and preserved (index signatures), per the
 * spec's extensibility rule: implementations MUST ignore what they do
 * not understand instead of rejecting it.
 */

/** Protocol version advertised by the discovery endpoint (SPEC v0.1). */
export const PROTOCOL_VERSION = "0.1";

/** Default submission path advertised by discovery. */
export const DEFAULT_FEEDBACK_PATH = "/feedback";

/** Canonical discovery path (normative, SPEC v0.1 section 2). */
export const DISCOVERY_PATH = "/.well-known/feedback-protocol";

/** Category of feedback (v0.1 supports exactly these five). */
export type FeedbackType =
  | "bug"
  | "missing_feature"
  | "unexpected_behavior"
  | "documentation"
  | "performance";

export const SUPPORTED_FEEDBACK_TYPES: readonly FeedbackType[] = [
  "bug",
  "missing_feature",
  "unexpected_behavior",
  "documentation",
  "performance",
];

/** Identity of the reporter (`agent` field). `name` is required when present. */
export interface AgentInfo {
  name: string;
  version?: string;
  [key: string]: unknown;
}

/** The API operation that surfaced the problem (`attempt` field). */
export interface AttemptInfo {
  method?: string;
  path?: string;
  [key: string]: unknown;
}

/**
 * What was actually observed (`observed` field). Facts, not diagnosis.
 * `status` is an HTTP status code when applicable.
 */
export interface ObservedInfo {
  status?: number;
  [key: string]: unknown;
}

/** A feedback submission body. Mirrors the v0.1 JSON schema 1:1. */
export interface Feedback {
  type: FeedbackType;
  summary: string;
  description?: string;
  goal?: string;
  attempt?: AttemptInfo;
  observed?: ObservedInfo;
  expected?: string;
  missing_capability?: string;
  suggestion?: string;
  agent?: AgentInfo;
  request_id?: string;
  /** When the problem was observed (RFC 3339 date-time, UTC preferred). */
  timestamp?: string;
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

/** Body of `GET /.well-known/feedback-protocol`. */
export interface DiscoveryResponse {
  version: string;
  feedback_endpoint: string;
  methods: string[];
  [key: string]: unknown;
}

/** Minimal successful response to `POST /feedback` (SPEC 3.4). */
export interface FeedbackReceipt {
  id: string;
  status: "received";
  [key: string]: unknown;
}

/**
 * A feedback report as persisted by a {@link FeedbackStore}.
 *
 * This is a server-side record, NOT part of the wire schema: it wraps the
 * client-supplied {@link Feedback} with the generated `id` and the
 * server-side `received_at` timestamp. The nested `feedback` payload keeps
 * the exact v0.1 shape so future stores can persist it without changing
 * the HTTP protocol.
 */
export interface StoredFeedback {
  id: string;
  /** Server-side receipt time, RFC 3339 date-time in UTC. */
  received_at: string;
  feedback: Feedback;
  [key: string]: unknown;
}
