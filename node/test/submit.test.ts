/** Tests for POST /feedback: valid, invalid, types, timestamps, IDs. */

import { strict as assert } from "node:assert";
import { after, before, describe, it } from "node:test";
import { SUPPORTED_FEEDBACK_TYPES, isFeedbackId } from "../src/index.js";
import { CANONICAL_EXAMPLE, postJson, startServer, type TestServer } from "./helpers.js";

describe("submission", () => {
  let srv: TestServer;
  before(async () => {
    srv = await startServer();
  });
  after(async () => {
    await srv.close();
  });

  it("accepts the canonical example with 201 + receipt", async () => {
    const res = await postJson(srv.base, "/feedback", CANONICAL_EXAMPLE);
    assert.equal(res.status, 201);
    const body = (await res.json()) as { id: string; status: string };
    assert.equal(body.status, "received");
    assert.ok(isFeedbackId(body.id), body.id);
    const record = await srv.store.get(body.id);
    assert.ok(record);
    assert.equal(record.feedback.summary, CANONICAL_EXAMPLE.summary);
  });

  it("accepts a minimal body with only required fields", async () => {
    const res = await postJson(srv.base, "/feedback", { type: "bug", summary: "500 on documented call" });
    assert.equal(res.status, 201);
    assert.equal(((await res.json()) as { status: string }).status, "received");
  });

  for (const t of SUPPORTED_FEEDBACK_TYPES) {
    it(`accepts type "${t}"`, async () => {
      const res = await postJson(srv.base, "/feedback", { type: t, summary: `summary for ${t}` });
      assert.equal(res.status, 201, t);
      assert.ok(isFeedbackId(((await res.json()) as { id: string }).id));
    });
  }

  it("generates unique IDs", async () => {
    const ids = new Set<string>();
    for (let i = 0; i < 25; i++) {
      const res = await postJson(srv.base, "/feedback", { type: "bug", summary: `report ${i}` });
      ids.add(((await res.json()) as { id: string }).id);
    }
    assert.equal(ids.size, 25);
  });

  it("stamps a server timestamp when absent", async () => {
    const before = new Date().toISOString();
    const res = await postJson(srv.base, "/feedback", { type: "bug", summary: "no ts" });
    const record = await srv.store.get(((await res.json()) as { id: string }).id);
    assert.ok(record?.feedback.timestamp);
    assert.ok(record.received_at >= before);
    assert.ok(record.received_at.endsWith("Z"));
  });

  it("preserves a client-supplied timestamp", async () => {
    const res = await postJson(srv.base, "/feedback", {
      type: "performance",
      summary: "slow",
      timestamp: "2026-01-15T12:34:56Z",
    });
    assert.equal(res.status, 201);
    const record = await srv.store.get(((await res.json()) as { id: string }).id);
    assert.ok(record?.feedback.timestamp?.startsWith("2026-01-15T12:34:56"));
  });

  it("rejects an unknown type with 400", async () => {
    const res = await postJson(srv.base, "/feedback", { type: "not_a_type", summary: "x" });
    assert.equal(res.status, 400);
    assert.ok("detail" in ((await res.json()) as object));
  });

  it("rejects missing type/summary with 400", async () => {
    assert.equal((await postJson(srv.base, "/feedback", { type: "bug" })).status, 400);
    assert.equal((await postJson(srv.base, "/feedback", { summary: "x" })).status, 400);
  });

  const invalid: Array<[string, unknown]> = [
    ["empty object", {}],
    ["empty summary", { type: "bug", summary: "" }],
    ["summary too long", { type: "bug", summary: "x".repeat(281) }],
    ["status out of range", { type: "bug", summary: "x", observed: { status: 999 } }],
    ["agent without name", { type: "bug", summary: "x", agent: { version: "1.0" } }],
  ];
  for (const [name, payload] of invalid) {
    it(`rejects ${name} with 400`, async () => {
      assert.equal((await postJson(srv.base, "/feedback", payload)).status, 400);
    });
  }

  it("rejects an empty body with 400", async () => {
    const res = await fetch(`${srv.base}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "",
    });
    assert.equal(res.status, 400);
  });

  it("rejects malformed JSON with 400", async () => {
    const res = await fetch(`${srv.base}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{not json",
    });
    assert.equal(res.status, 400);
  });

  it("rejects a JSON array with 400", async () => {
    assert.equal((await postJson(srv.base, "/feedback", ["not", "an", "object"])).status, 400);
  });

  it("accepts unknown fields for extensibility", async () => {
    const res = await postJson(srv.base, "/feedback", {
      type: "bug",
      summary: "x",
      future_field: "must not break v0.1",
    });
    assert.equal(res.status, 201);
  });

  it("preserves service, correlation ids and structured expected", async () => {
    const res = await postJson(srv.base, "/feedback", {
      type: "missing_feature",
      summary: "no pagination",
      expected: { capability: "pagination" },
      service: { name: "users-api", version: "4.2.1", environment: "production" },
      session_id: "sess_1",
      trace_id: "trace_1",
    });
    assert.equal(res.status, 201);
    const record = await srv.store.get(((await res.json()) as { id: string }).id);
    assert.deepEqual(record?.feedback.expected, { capability: "pagination" });
    assert.deepEqual(record?.feedback.service, {
      name: "users-api",
      version: "4.2.1",
      environment: "production",
    });
    assert.equal(record?.feedback.session_id, "sess_1");
    assert.equal(record?.feedback.trace_id, "trace_1");
  });

  it("rejects malformed service and expected shapes with 400", async () => {
    for (const payload of [
      { type: "bug", summary: "x", service: 42 },
      { type: "bug", summary: "x", service: { version: "" } },
      { type: "bug", summary: "x", expected: 42 },
      { type: "bug", summary: "x", session_id: "" },
    ]) {
      assert.equal((await postJson(srv.base, "/feedback", payload)).status, 400);
    }
  });
});
