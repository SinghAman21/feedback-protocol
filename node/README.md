# feedback-protocol

Node.js/TypeScript implementation of the Feedback Protocol (v0.1 spec):
Express middleware for structured feedback reports.

```ts
import express from "express";
import { feedbackProtocol } from "feedback-protocol";

const app = express();
app.use(feedbackProtocol());
```

This exposes `GET /.well-known/feedback-protocol` (discovery) and
`POST /feedback` (validated submission, `201` + receipt).

- Only `type` and `summary` are required in reports; see
  `schema/feedback.schema.json` in the
  [repository](https://example.org/feedback-protocol) (source of truth).
- Storage is pluggable via `FeedbackStore`; `MemoryFeedbackStore`
  is built in for development and tests.
- No auth system is included — pass your own middleware via
  `feedbackProtocol({ auth })`.
- Only report `id` + `type` are ever logged, never payloads or credentials.

Implements the same v0.1 protocol as the Python `feedback-protocol`
package: identical validation, `fb_…` IDs, and receipt shape.
