/**
 * Validation for feedback submission bodies.
 *
 * This validator is behavior-compatible with `schema/feedback.schema.json`
 * (which remains the source of truth): the same payloads are accepted and
 * rejected. Unknown fields are accepted and preserved, per the spec's
 * extensibility rule. See `test/compat.test.ts`, which cross-checks this
 * validator against the real schema file.
 */

import { SUPPORTED_FEEDBACK_TYPES, type Feedback } from "./types.js";

export interface ValidationIssue {
  path: string;
  message: string;
}

export interface ValidationSuccess {
  ok: true;
  value: Feedback;
}

export interface ValidationFailure {
  ok: false;
  errors: ValidationIssue[];
}

export type ValidationResult = ValidationSuccess | ValidationFailure;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function checkOptionalString(
  obj: Record<string, unknown>,
  field: string,
  path: string,
  errors: ValidationIssue[],
): void {
  if (obj[field] === undefined) return;
  if (typeof obj[field] !== "string" || (obj[field] as string).length < 1) {
    errors.push({ path, message: `${path} must be a non-empty string` });
  }
}

/**
 * Validate an unknown parsed-JSON value as a v0.1 feedback body.
 * Returns the value typed as {@link Feedback} on success.
 */
export function validateFeedback(payload: unknown): ValidationResult {
  const errors: ValidationIssue[] = [];

  if (!isRecord(payload)) {
    return { ok: false, errors: [{ path: "$", message: "body must be a JSON object" }] };
  }

  if (
    typeof payload["type"] !== "string" ||
    !(SUPPORTED_FEEDBACK_TYPES as readonly string[]).includes(payload["type"])
  ) {
    errors.push({
      path: "$.type",
      message: `$.type must be one of: ${SUPPORTED_FEEDBACK_TYPES.join(", ")}`,
    });
  }

  if (
    typeof payload["summary"] !== "string" ||
    payload["summary"].length < 1 ||
    payload["summary"].length > 280
  ) {
    errors.push({
      path: "$.summary",
      message: "$.summary must be a string of 1-280 characters",
    });
  }

  for (const field of [
    "description",
    "goal",
    "expected",
    "missing_capability",
    "suggestion",
    "request_id",
  ] as const) {
    checkOptionalString(payload, field, `$.${field}`, errors);
  }

  if (payload["attempt"] !== undefined) {
    if (!isRecord(payload["attempt"])) {
      errors.push({ path: "$.attempt", message: "$.attempt must be an object" });
    } else {
      checkOptionalString(payload["attempt"], "method", "$.attempt.method", errors);
      checkOptionalString(payload["attempt"], "path", "$.attempt.path", errors);
    }
  }

  if (payload["observed"] !== undefined) {
    if (!isRecord(payload["observed"])) {
      errors.push({ path: "$.observed", message: "$.observed must be an object" });
    } else {
      const status = payload["observed"]["status"];
      if (
        status !== undefined &&
        (typeof status !== "number" || !Number.isInteger(status) || status < 100 || status > 599)
      ) {
        errors.push({
          path: "$.observed.status",
          message: "$.observed.status must be an integer between 100 and 599",
        });
      }
    }
  }

  if (payload["agent"] !== undefined) {
    if (!isRecord(payload["agent"])) {
      errors.push({ path: "$.agent", message: "$.agent must be an object" });
    } else {
      if (typeof payload["agent"]["name"] !== "string" || payload["agent"]["name"].length < 1) {
        errors.push({ path: "$.agent.name", message: "$.agent.name is required" });
      }
      checkOptionalString(payload["agent"], "version", "$.agent.version", errors);
    }
  }

  if (payload["timestamp"] !== undefined) {
    if (typeof payload["timestamp"] !== "string" || Number.isNaN(Date.parse(payload["timestamp"]))) {
      errors.push({
        path: "$.timestamp",
        message: "$.timestamp must be an RFC 3339 date-time string",
      });
    }
  }

  if (payload["metadata"] !== undefined && !isRecord(payload["metadata"])) {
    errors.push({ path: "$.metadata", message: "$.metadata must be an object" });
  }

  if (errors.length > 0) {
    return { ok: false, errors };
  }
  return { ok: true, value: payload as Feedback };
}
