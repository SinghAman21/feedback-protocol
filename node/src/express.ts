/**
 * Express integration for the Feedback Protocol.
 *
 * Minimal usage:
 *
 * ```ts
 * import express from "express";
 * import { feedbackProtocol } from "feedback-protocol";
 *
 * const app = express();
 * app.use(feedbackProtocol());
 * ```
 *
 * This exposes:
 *
 * - `GET /.well-known/feedback-protocol` (canonical discovery, SPEC v0.1)
 * - `POST /feedback` (validated submission, `201` + receipt)
 *
 * Authentication: this package deliberately provides NO authentication
 * mechanism. Protect the middleware with your own Express middleware:
 *
 * ```ts
 * app.use(feedbackProtocol({ auth: requireApiKey }));
 * ```
 *
 * Privacy: received payloads are never logged in full — only the
 * generated ID and the feedback `type`. See "Production considerations"
 * in the README.
 */

import { Router } from "express";
import type { NextFunction, Request, RequestHandler, Response } from "express";
import { DISCOVERY_PATH, DEFAULT_FEEDBACK_PATH, PROTOCOL_VERSION } from "./types.js";
import type { FeedbackReceipt } from "./types.js";
import { validateFeedback } from "./validate.js";
import { MemoryFeedbackStore, type FeedbackStore } from "./store.js";

export interface FeedbackProtocolLogger {
  info(message: string, ...args: unknown[]): void;
}

export interface FeedbackProtocolOptions {
  /**
   * Persistence backend. Defaults to a new {@link MemoryFeedbackStore}.
   * Pass a custom {@link FeedbackStore} (PostgreSQL, Redis, external
   * service) without changing the HTTP protocol.
   */
  store?: FeedbackStore;
  /** Path for submissions (default `/feedback`). Advertised by discovery. */
  feedbackPath?: string;
  /** Protocol version string for discovery (default `"0.1"`). */
  protocolVersion?: string;
  /**
   * Auth extension point: Express middleware run before both endpoints
   * (e.g. API-key or OAuth2 verification). Rejections SHOULD use `401`
   * (missing/invalid credentials) or `403` (valid credentials, forbidden).
   */
  auth?: RequestHandler | RequestHandler[];
  /** Logger for receipt lines (`id` + `type` only). Set `false` to silence. */
  logger?: FeedbackProtocolLogger | false;
}

const defaultLogger: FeedbackProtocolLogger = {
  info: (message: string, ...args: unknown[]): void => {
    console.info(message, ...args);
  },
};

/**
 * Create Express middleware exposing the Feedback Protocol endpoints.
 * Returns a {@link Router}, which is itself valid `app.use(...)` middleware.
 */
export function feedbackProtocol(options: FeedbackProtocolOptions = {}): Router {
  const store = options.store ?? new MemoryFeedbackStore();
  const feedbackPath = options.feedbackPath ?? DEFAULT_FEEDBACK_PATH;
  const protocolVersion = options.protocolVersion ?? PROTOCOL_VERSION;
  const logger = options.logger === undefined ? defaultLogger : options.logger;
  const authHandlers: RequestHandler[] = options.auth
    ? Array.isArray(options.auth)
      ? options.auth
      : [options.auth]
    : [];

  const router = Router();

  router.get(DISCOVERY_PATH, ...authHandlers, (_req: Request, res: Response) => {
    res.json({ version: protocolVersion, feedback_endpoint: feedbackPath, methods: ["POST"] });
  });

  router.post(
    feedbackPath,
    ...authHandlers,
    (req: Request, res: Response, next: NextFunction) => {
      // Parse JSON here (instead of requiring app-level body parsing) so
      // malformed bodies map to the spec's `400`, and mounting the
      // middleware is all the setup a developer needs.
      if (req.body !== undefined) {
        submit(req.body, req, res, next, store, logger).catch(next);
        return;
      }
      let raw = "";
      req.setEncoding("utf8");
      req.on("data", (chunk: string) => {
        raw += chunk;
      });
      req.on("end", () => {
        if (raw.length === 0) {
          res.status(400).json({ detail: "Request body must be a JSON object." });
          return;
        }
        let parsed: unknown;
        try {
          parsed = JSON.parse(raw);
        } catch {
          res.status(400).json({ detail: "Request body must be valid JSON." });
          return;
        }
        submit(parsed, req, res, next, store, logger).catch(next);
      });
      req.on("error", next);
    },
  );

  // Malformed-JSON bodies rejected by downstream parsers (if any) still
  // surface as JSON `400`s rather than HTML error pages.
  router.use((err: unknown, _req: Request, res: Response, next: NextFunction) => {
    if (res.headersSent) {
      next(err);
      return;
    }
    const status =
      typeof err === "object" && err !== null && "status" in err && (err as { status: unknown }).status === 400
        ? 400
        : 500;
    if (status === 400) {
      res.status(400).json({ detail: "Request body must be valid JSON." });
      return;
    }
    next(err);
  });

  return router;
}

async function submit(
  parsed: unknown,
  _req: Request,
  res: Response,
  _next: NextFunction,
  store: FeedbackStore,
  logger: FeedbackProtocolLogger | false,
): Promise<void> {
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    res.status(400).json({ detail: "Request body must be a JSON object." });
    return;
  }
  const result = validateFeedback(parsed);
  if (!result.ok) {
    res.status(400).json({ detail: "Invalid feedback payload.", errors: result.errors });
    return;
  }
  const record = await store.save(result.value);
  // Privacy: log routing metadata only — never the payload, headers,
  // cookies, tokens, or any credential material.
  if (logger !== false) {
    logger.info("feedback received id=%s type=%s", record.id, record.feedback.type);
  }
  const receipt: FeedbackReceipt = { id: record.id, status: "received" };
  res.status(201).json(receipt);
}
