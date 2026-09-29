/**
 * Storage abstraction for received feedback.
 *
 * No database is required. The default {@link MemoryFeedbackStore} keeps
 * records in process memory and is suitable for development and tests.
 *
 * The {@link FeedbackStore} interface is intentionally narrow (`save`,
 * `get`, `list`, `count`) and async, so future implementations backed by
 * PostgreSQL, Redis, or an external service can be dropped in without
 * changing the HTTP protocol.
 */

import { generateFeedbackId } from "./ids.js";
import type { Feedback, StoredFeedback } from "./types.js";

/** Abstract persistence boundary for feedback records. */
export interface FeedbackStore {
  /** Assign an ID + receipt time, persist, and return the stored record. */
  save(feedback: Feedback): Promise<StoredFeedback>;
  /** Return the record for `feedbackId`, or `null` if unknown. */
  get(feedbackId: string): Promise<StoredFeedback | null>;
  /** Return stored records in insertion order (paginated). */
  list(limit?: number, offset?: number): Promise<StoredFeedback[]>;
  /** Return the total number of stored records. */
  count(): Promise<number>;
}

/**
 * Non-persistent, in-process store for development and tests.
 *
 * Not suitable for multi-process production use: records live only in
 * memory and are lost on restart. Use a database-backed
 * {@link FeedbackStore} for production.
 */
export class MemoryFeedbackStore implements FeedbackStore {
  private readonly records = new Map<string, StoredFeedback>();
  private readonly order: string[] = [];

  async save(feedback: Feedback): Promise<StoredFeedback> {
    const receivedAt = new Date().toISOString();
    // Preserve a client-supplied timestamp; stamp receipt time separately.
    const stored: Feedback =
      feedback.timestamp === undefined ? { ...feedback, timestamp: receivedAt } : feedback;
    let id = generateFeedbackId();
    // Regenerate on the (astronomically unlikely) collision.
    while (this.records.has(id)) {
      id = generateFeedbackId();
    }
    const record: StoredFeedback = { id, received_at: receivedAt, feedback: stored };
    this.records.set(id, record);
    this.order.push(id);
    return record;
  }

  async get(feedbackId: string): Promise<StoredFeedback | null> {
    return this.records.get(feedbackId) ?? null;
  }

  async list(limit = 100, offset = 0): Promise<StoredFeedback[]> {
    return this.order
      .slice(offset, offset + limit)
      .map((id) => this.records.get(id))
      .filter((r): r is StoredFeedback => r !== undefined);
  }

  async count(): Promise<number> {
    return this.records.size;
  }
}
