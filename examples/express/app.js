import express from "express";
import { feedbackProtocol, MemoryFeedbackStore } from "feedback-protocol";

// --- Optional auth extension point -------------------------------------------
// The protocol defines no auth mechanism. Uncomment and adapt for production:
//
// const requireApiKey = (req, res, next) => {
//   if (req.get("x-api-key") !== "super-secret") {
//     res.status(401).json({ detail: "Invalid API key." });
//     return;
//   }
//   next();
// };
// app.use(feedbackProtocol({ store, auth: requireApiKey }));

const store = new MemoryFeedbackStore();
const app = express();

app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

app.use(feedbackProtocol({ store }));

// Operator-only debug endpoint (NOT part of the protocol): confirms what was
// stored while developing locally. Remove or protect in production.
app.get("/debug/feedback-count", async (_req, res) => {
  res.json({ count: await store.count() });
});

const port = Number(process.env.PORT ?? 3000);
app.listen(port, () => {
  console.log(`Feedback Protocol example listening on http://localhost:${port}`);
});
