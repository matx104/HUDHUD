# The studio: the live demo, one image, run on Azure Container Apps (docs/azure.md).
# Signs in with the app's managed identity: no keys or secrets are baked in or passed.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY packages/event-schema packages/event-schema
COPY apps/api apps/api
# pip's downloads live in a build cache outside the image: a build that fails on a slow connection
# keeps what it fetched, and the next one picks up from there.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --retries 10 --timeout 60 ./packages/event-schema "./apps/api[foundry,audit,telemetry,server]" \
    && useradd --uid 10001 --no-create-home studio

USER studio
EXPOSE 8080
CMD ["uvicorn", "court.server:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
