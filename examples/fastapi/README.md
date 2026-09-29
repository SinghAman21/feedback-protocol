# Example FastAPI service

```bash
pip install feedback-protocol uvicorn
uvicorn app:app --reload --port 8000
```

Try it:

```bash
curl http://localhost:8000/.well-known/feedback-protocol
curl -X POST http://localhost:8000/feedback \
  -H 'Content-Type: application/json' \
  -d '{"type":"missing_feature","summary":"Users endpoint does not support pagination"}'
```
