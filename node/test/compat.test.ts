/**
 * Protocol compatibility: our validator must agree with the normative
 * `schema/feedback.schema.json` (the source of truth) on every payload.
 *
 * NOTE on the relative path: tests run compiled from `dist-test/test/`,
 * so `../../../schema/...` resolves to the repository-root schema file.
 */

import { strict as assert } from "node:assert";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";
import { validateFeedback } from "../src/index.js";
import { CANONICAL_EXAMPLE } from "./helpers.js";

// ajv ships as CommonJS; load it via require for reliable ESM interop.
// The 2020 build understands the draft 2020-12 `$schema` our file declares.
const require = createRequire(import.meta.url);
// eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
const Ajv2020 = require("ajv/dist/2020");
// eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
const addFormats = require("ajv-formats");

const schemaPath = fileURLToPath(new URL("../../../schema/feedback.schema.json", import.meta.url));
const schema = JSON.parse(readFileSync(schemaPath, "utf8")) as Record<string, unknown>;

const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
const validateWithSchema = ajv.compile(schema);

describe("protocol compatibility", () => {
  it("schema requires only type + summary", () => {
    assert.deepEqual(schema["required"], ["type", "summary"]);
    assert.deepEqual(
      ((schema["properties"] as Record<string, unknown>)["type"] as { enum: string[] }).enum,
      ["bug", "missing_feature", "unexpected_behavior", "documentation", "performance"],
    );
  });

  it("canonical SPEC example is valid per the real schema", () => {
    assert.equal(validateWithSchema(CANONICAL_EXAMPLE), true);
  });

  it("shared schema/examples fixtures are valid under both", () => {
    const dir = join(dirname(schemaPath), "examples");
    const files = readdirSync(dir).filter((f) => f.endsWith(".json")).sort();
    assert.ok(files.length >= 4, `expected fixtures, got: ${files}`);
    for (const file of files) {
      const payload = JSON.parse(readFileSync(join(dir, file), "utf8")) as unknown;
      assert.equal(validateWithSchema(payload), true, `schema: ${file}`);
      assert.equal(validateFeedback(payload).ok, true, `node validator: ${file}`);
    }
  });

  it("our validator agrees with the schema on every payload", () => {
    const cases: Array<[string, unknown, boolean]> = [
      ["canonical", CANONICAL_EXAMPLE, true],
      ["minimal bug", { type: "bug", summary: "x" }, true],
      ["minimal documentation", { type: "documentation", summary: "x" }, true],
      ["full fields", { ...CANONICAL_EXAMPLE, description: "d", expected: "e", request_id: "r", timestamp: "2026-01-15T12:34:56Z", metadata: { k: "v" } }, true],
      ["unknown top-level field", { type: "bug", summary: "x", future: 1 }, true],
      ["expected as object", { type: "bug", summary: "x", expected: { capability: "pagination" } }, true],
      ["expected empty string", { type: "bug", summary: "x", expected: "" }, false],
      ["expected number", { type: "bug", summary: "x", expected: 42 }, false],
      ["service as name", { type: "bug", summary: "x", service: "payments-api" }, true],
      ["service empty name", { type: "bug", summary: "x", service: "" }, false],
      ["service as object", { type: "bug", summary: "x", service: { name: "p", version: "4.2.1", environment: "prod" } }, true],
      ["service object empty", { type: "bug", summary: "x", service: {} }, true],
      ["service as number", { type: "bug", summary: "x", service: 42 }, false],
      ["service bad version", { type: "bug", summary: "x", service: { name: "p", version: "" } }, false],
      ["session and trace", { type: "bug", summary: "x", session_id: "s", trace_id: "t" }, true],
      ["empty session", { type: "bug", summary: "x", session_id: "" }, false],
      ["empty object", {}, false],
      ["missing type", { summary: "x" }, false],
      ["missing summary", { type: "bug" }, false],
      ["bad type", { type: "nope", summary: "x" }, false],
      ["empty summary", { type: "bug", summary: "" }, false],
      ["long summary", { type: "bug", summary: "x".repeat(281) }, false],
      ["bad status", { type: "bug", summary: "x", observed: { status: 99 } }, false],
      ["non-integer status", { type: "bug", summary: "x", observed: { status: 200.5 } }, false],
      ["agent without name", { type: "bug", summary: "x", agent: {} }, false],
      ["bad timestamp", { type: "bug", summary: "x", timestamp: "not-a-date" }, false],
      ["metadata array", { type: "bug", summary: "x", metadata: [] }, false],
    ];
    for (const [name, payload, expected] of cases) {
      assert.equal(validateWithSchema(payload), expected, `schema: ${name}`);
      assert.equal(validateFeedback(payload).ok, expected, `node validator: ${name}`);
    }
  });
});
