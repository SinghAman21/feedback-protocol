FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE SPEC.md ./
COPY schema ./schema
COPY src ./src
COPY service ./service

RUN pip install --no-cache-dir fastapi "uvicorn[standard]" . \
 && rm -rf /root/.cache

ENV FEEDBACK_SERVICE_DB=/data/feedback.db \
    PORT=8000

VOLUME /data
EXPOSE 8000

CMD ["sh", "-c", "uvicorn --factory service.app:create_default_app --host 0.0.0.0 --port ${PORT:-8000}"]
