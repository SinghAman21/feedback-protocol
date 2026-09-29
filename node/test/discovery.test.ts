/** Tests for GET /.well-known/feedback-protocol. */

import { strict as assert } from "node:assert";
import { after, describe, it } from "node:test";
import { DISCOVERY_PATH } from "../src/index.js";
import { startServer, type TestServer } from "./helpers.js";

describe("discovery", () => {
  let srv: TestServer | undefined;
  after(async () => {
    await srv?.close();
  });

  it("advertises version, endpoint and methods", async () => {
    srv = await startServer();
    const res = await fetch(`${srv.base}${DISCOVERY_PATH}`);
    assert.equal(res.status, 200);
    assert.deepEqual(await res.json(), {
      version: "0.1",
      feedback_endpoint: "/feedback",
      methods: ["POST"],
    });
  });

  it("unknown well-known paths are 404", async () => {
    const res = await fetch(`${srv!.base}/.well-known/does-not-exist`);
    assert.equal(res.status, 404);
  });

  it("advertises a custom feedback path", async () => {
    const custom = await startServer({ feedbackPath: "/api/feedback" });
    try {
      const res = await fetch(`${custom.base}${DISCOVERY_PATH}`);
      assert.equal((await res.json() as { feedback_endpoint: string }).feedback_endpoint, "/api/feedback");
      const sub = await fetch(`${custom.base}/api/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "bug", summary: "x" }),
      });
      assert.equal(sub.status, 201);
    } finally {
      await custom.close();
    }
  });
});
