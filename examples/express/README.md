# Example Express service

```bash
npm install
npm start
```

Try it:

1. Successful protocol discovery:

```bash
curl http://localhost:3000/.well-known/feedback-protocol
# → {"version": "0.1", "feedback_endpoint": "/feedback", "methods": ["POST"]}
```

2. Missing-feature submission:

```bash
curl -X POST http://localhost:3000/feedback \
  -H 'Content-Type: application/json' \
  -d '{"type":"missing_feature","summary":"Users endpoint does not support pagination"}'
# → {"id": "fb_…", "status": "received"}
```

3. Bug submission (evidence-rich, still schema-valid):

```bash
curl -X POST http://localhost:3000/feedback \
  -H 'Content-Type: application/json' \
  -d '{"type":"bug","summary":"POST /api/v1/projects returns 500","goal":"Create a project","attempt":{"method":"POST","path":"/api/v1/projects"},"observed":{"status":500},"expected":"201 per the API docs","request_id":"req_123","agent":{"name":"example-agent"}}'
# → {"id": "fb_…", "status": "received"}
```
