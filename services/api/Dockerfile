# The API service, for Cloud Run.
#
# Multi-stage so the runtime image carries no compiler and no build cache.
# `finops-core` is installed from the monorepo, not from an index -- it is the
# same source the Streamlit app runs and the nightly job imports.

# The React client is built here and served by the API from the same origin, so
# there is one Cloud Run service and one hostname. The alternative -- a second
# service or a bucket behind a load balancer -- buys independent release cycles
# that this platform does not currently need, and costs a CORS configuration
# that can be got wrong.
#
# VITE_API_BASE is deliberately NOT set: web/src/lib/api.ts falls back to an
# empty base, which makes every call relative and therefore same-origin.
FROM node:20-slim AS web

WORKDIR /web
# package.json and the lockfile first, so `npm ci` is cached until a dependency
# actually changes rather than on every source edit.
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build


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
    DATA_SOURCE=demo \
    GOOGLE_GENAI_USE_VERTEXAI=TRUE

COPY --from=builder /venv /venv

WORKDIR /app
COPY services/api/app /app/app

# The built SPA. main.py serves it from /app/web and falls back to index.html
# for client-side routes; if this directory is absent the API still starts and
# simply serves no UI, which is what happens in local development.
COPY --from=web /web/dist /app/web

# Never run as root, even behind Cloud Run's sandbox.
RUN useradd --create-home --uid 10001 finops && chown -R finops /app
USER finops

EXPOSE 8080

# One worker: the process holds no state, and Cloud Run scales by instance.
# Uvicorn's default proxy headers are correct behind Cloud Run's front end.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers
