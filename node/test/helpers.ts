/** Shared helpers for the Express integration tests (real HTTP). */

import express from "express";
import type { Server } from "node:http";
import type { AddressInfo } from "node:net";
import { feedbackProtocol } from "../src/index.js";
import type { FeedbackProtocolOptions } from "../src/index.js";
import { MemoryFeedbackStore } from "../src/index.js";

export const CANONICAL_EXAMPLE = {
  type: "missing_feature",
  summary: "Users endpoint does not support pagination",
  goal: "Retrieve all users",
  attempt: { method: "GET", path: "/api/v1/users" },
  observed: { status: 200, item_count: 100000 },
  missing_capability: "pagination",
  suggestion: "Support cursor-based pagination",
  agent: { name: "example-agent", version: "1.0.0" },
} as const;

export interface TestServer {
  base: string;
  store: MemoryFeedbackStore;
  close: () => Promise<void>;
}

export async function startServer(options: FeedbackProtocolOptions = {}): Promise<TestServer> {
  const store = (options.store as MemoryFeedbackStore | undefined) ?? new MemoryFeedbackStore();
  const app = express();
  app.use(feedbackProtocol({ ...options, store }));
  const server: Server = await new Promise((resolve) => {
    const s = app.listen(0, "127.0.0.1", () => resolve(s));
  });
  const { port } = server.address() as AddressInfo;
  return {
    base: `http://127.0.0.1:${port}`,
    store,
    close: () => new Promise((resolve, reject) => server.close((e) => (e ? reject(e) : resolve()))),
  };
}

export async function postJson(base: string, path: string, body: unknown): Promise<Response> {
  return fetch(`${base}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}
