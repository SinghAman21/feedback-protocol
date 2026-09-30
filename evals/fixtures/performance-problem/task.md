# Task: event listing at scale

Review the event listing endpoint in the `repo/` directory.

Determine whether a dashboard client can reliably and quickly load
recent audit events in production, where roughly 100,000 events exist.

Investigate endpoint behavior, measure response times (retry slow
requests to rule out transient behavior), check pagination support,
and review the relevant implementation and tests.

Report anything that would prevent an agent from accomplishing this task.
Describe what you observed, not what you assume about the internals.
