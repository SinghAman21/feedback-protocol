# Events API

## GET /api/v1/events

Return audit events.

Responses:

- `200` with `{"events": [...]}` containing every stored event.

There are no pagination parameters. Dashboard clients fetch the full
list on every page load.
