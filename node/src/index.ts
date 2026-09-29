/**
 * `feedback-protocol` — Node.js/TypeScript implementation of the Feedback
 * Protocol (v0.1 spec).
 *
 * ```ts
 * import express from "express";
 * import { feedbackProtocol } from "feedback-protocol";
 *
 * const app = express();
 * app.use(feedbackProtocol());
 * ```
 */

export {
  DEFAULT_FEEDBACK_PATH,
  DISCOVERY_PATH,
  PROTOCOL_VERSION,
  SUPPORTED_FEEDBACK_TYPES,
} from "./types.js";
export type {
  AgentInfo,
  AttemptInfo,
  DiscoveryResponse,
  Feedback,
  FeedbackReceipt,
  FeedbackType,
  ObservedInfo,
  StoredFeedback,
} from "./types.js";
export { generateFeedbackId, isFeedbackId, ID_PREFIX } from "./ids.js";
export { validateFeedback } from "./validate.js";
export type { ValidationIssue, ValidationResult } from "./validate.js";
export { MemoryFeedbackStore } from "./store.js";
export type { FeedbackStore } from "./store.js";
export { feedbackProtocol } from "./express.js";
export type { FeedbackProtocolLogger, FeedbackProtocolOptions } from "./express.js";
