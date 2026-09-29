/**
 * Feedback ID generation.
 *
 * IDs are opaque server-assigned strings of the form `fb_<24 hex chars>`
 * (e.g. `fb_9f3c2a1b4d5e6f708192a3b4`), using `crypto` randomness.
 * The format is server-defined per SPEC 3.4 — clients MUST treat IDs as
 * opaque. It is byte-compatible with the Python implementation's IDs:
 * either side accepts the other's receipts.
 */

import { randomBytes } from "node:crypto";

export const ID_PREFIX = "fb_";

const ID_RE = /^fb_[0-9a-f]{24}$/;

/** Generate a new unique feedback ID. */
export function generateFeedbackId(): string {
  return `${ID_PREFIX}${randomBytes(12).toString("hex")}`;
}

/** Return true if `value` looks like a generated feedback ID. */
export function isFeedbackId(value: string): boolean {
  return ID_RE.test(value);
}
