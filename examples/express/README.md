# Example Express service

```bash
npm install
npm start
```

Try it:

```bash
curl http://localhost:3000/.well-known/feedback-protocol
curl -X POST http://localhost:3000/feedback \
  -H 'Content-Type: application/json' \
  -d '{"type":"missing_feature","summary":"Users endpoint does not support pagination"}'
```
