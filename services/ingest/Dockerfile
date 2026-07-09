# The ingest job, for Cloud Run Jobs.
#
# Same multi-stage shape as services/api/Dockerfile: a builder venv, then a
# runtime image with no compiler and no build cache. This one installs the cloud
# SDKs (`aws`, `azure`, `gcp`) because it is the process that actually pulls
# billing data through the connectors -- the API never does.

FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build

# Core first: it changes far less often than the job, so this layer stays cached.
COPY packages/finops-core /build/packages/finops-core
COPY services/ingest/requirements.txt /build/requirements.txt

RUN python -m venv /venv \
 && /venv/bin/pip install --upgrade pip \
 && /venv/bin/pip install "/build/packages/finops-core[stats,connectors,gcp,aws,azure]" \
 && /venv/bin/pip install -r /build/requirements.txt


FROM python:3.12-slim AS runtime

# Cloud Run Jobs inject no PORT; the job runs to completion and exits. Vertex is
# not used here, so no GENAI env. DATA_SOURCE is irrelevant -- this process reads
# connectors and writes BigQuery directly.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/venv/bin:$PATH"

COPY --from=builder /venv /venv

WORKDIR /app
COPY services/ingest/ingest /app/ingest

# Never run as root, even inside the Cloud Run sandbox.
RUN useradd --create-home --uid 10001 finops && chown -R finops /app
USER finops

# argparse subcommands: the Cloud Scheduler job passes `ingest` or `opportunities`
# as the container args, appended to this entrypoint.
ENTRYPOINT ["python", "-m", "ingest.main"]
