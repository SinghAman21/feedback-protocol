/** Tests for ID generation and the storage abstraction. */

import { strict as assert } from "node:assert";
import { describe, it } from "node:test";
import express from "express";
import { generateFeedbackId, isFeedbackId } from "../src/index.js";
import { feedbackProtocol } from "../src/index.js";
import { MemoryFeedbackStore, type FeedbackStore, type StoredFeedback } from "../src/index.js";
import type { Feedback } from "../src/index.js";

describe("ids", () => {
  it("generates fb_ + 24 hex ids", () => {
    const id = generateFeedbackId();
    assert.ok(id.startsWith("fb_"));
    assert.ok(isFeedbackId(id));
    assert.equal(isFeedbackId("fb_123"), false);
    assert.equal(isFeedbackId("123"), false);
  });

  it("generates unique ids", () => {
    assert.equal(new Set(Array.from({ length: 1000 }, generateFeedbackId)).size, 1000);
  });
});

describe("MemoryFeedbackStore", () => {
  it("saves, gets and counts", async () => {
    const store = new MemoryFeedbackStore();
    assert.equal(await store.count(), 0);
    assert.equal(await store.get("fb_doesnotexist0000000000"), null);
    const record = await store.save({ type: "bug", summary: "hello" });
    assert.equal(await store.count(), 1);
    assert.deepEqual(await store.get(record.id), record);
    assert.ok(record.received_at.endsWith("Z"));
  });

  it("lists in insertion order with pagination", async () => {
    const store = new MemoryFeedbackStore();
    for (let i = 0; i < 5; i++) {
      await store.save({ type: "bug", summary: `report ${i}` });
    }
    assert.deepEqual(
      (await store.list(2, 0)).map((r) => r.feedback.summary),
      ["report 0", "report 1"],
    );
    assert.deepEqual(
      (await store.list(2, 2)).map((r) => r.feedback.summary),
      ["report 2", "report 3"],
    );
    assert.deepEqual(
      (await store.list(2, 4)).map((r) => r.feedback.summary),
      ["report 4"],
    );
  });

  it("backs the middleware via a custom implementation", async () => {
    class CountingStore extends MemoryFeedbackStore {
      saves = 0;
      override async save(feedback: Feedback): Promise<StoredFeedback> {
        this.saves += 1;
        return super.save(feedback);
      }
    }
    const store = new CountingStore();
    const app = express();
    app.use(feedbackProtocol({ store }));
    const server = await new Promise<import("node:http").Server>((resolve) => {
      const s = app.listen(0, "127.0.0.1", () => resolve(s));
    });
    try {
      const { port } = server.address() as import("node:net").AddressInfo;
      const res = await fetch(`http://127.0.0.1:${port}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "bug", summary: "x" }),
      });
      assert.equal(res.status, 201);
      assert.equal(store.saves, 1);
    } finally {
      await new Promise<void>((resolve, reject) =>
        server.close((e) => (e ? reject(e) : resolve())),
      );
    }
  });

  it("satisfies the FeedbackStore interface", () => {
    const store: FeedbackStore = new MemoryFeedbackStore();
    assert.ok(typeof store.save === "function");
    assert.ok(typeof store.get === "function");
    assert.ok(typeof store.list === "function");
    assert.ok(typeof store.count === "function");
  });
});
