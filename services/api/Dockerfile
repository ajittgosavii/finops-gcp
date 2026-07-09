# The API service, for Cloud Run.
#
# Multi-stage so the runtime image carries no compiler and no build cache.
# `finops-core` is installed from the monorepo, not from an index -- it is the
# same source the Streamlit app runs and the nightly job imports.

FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build

# The core package first: it changes far less often than the service, so this
# layer stays cached across most deploys.
COPY packages/finops-core /build/packages/finops-core
COPY services/api/requirements.txt /build/requirements.txt

RUN python -m venv /venv \
 && /venv/bin/pip install --upgrade pip \
 && /venv/bin/pip install "/build/packages/finops-core[stats,connectors,gcp]" \
 && /venv/bin/pip install -r /build/requirements.txt


FROM python:3.12-slim AS runtime

# Cloud Run terminates TLS and injects PORT. Nothing else is assumed.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/venv/bin:$PATH" \
    PORT=8080 \
    DATA_SOURCE=bigquery \
    GOOGLE_GENAI_USE_VERTEXAI=TRUE

COPY --from=builder /venv /venv

WORKDIR /app
COPY services/api/app /app/app

# Never run as root, even behind Cloud Run's sandbox.
RUN useradd --create-home --uid 10001 finops && chown -R finops /app
USER finops

EXPOSE 8080

# One worker: the process holds no state, and Cloud Run scales by instance.
# Uvicorn's default proxy headers are correct behind Cloud Run's front end.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers
