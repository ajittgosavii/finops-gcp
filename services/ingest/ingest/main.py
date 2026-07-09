"""The ingest job: pull billing, normalise to FOCUS 1.2, land it, snapshot it.

Two subcommands, run as a Cloud Run Job:

    python -m ingest.main ingest         connectors -> GCS Parquet -> focus_costs
    python -m ingest.main opportunities  read a window -> optimize -> opportunities

Why a batch job and not an API endpoint
---------------------------------------
The row-level detectors in `finops_core.engines.optimize` scan resource ids and
SKU strings across the whole window; running them per dashboard request would
scan the table on every load and their answer changes at most once a day. The
API reads the `opportunities` table this job writes. That split -- aggregates in
SQL for the API, row-level detection nightly here -- is the whole reason the
platform survives a utility-sized estate. See `services/api/app/repository.py`.

Idempotency, because a Cloud Run Job retries
--------------------------------------------
A job that a transient error restarts must not double-count. The FOCUS frame has
no natural primary key, so we cannot MERGE on one. Instead we land each run's
rows in a *run-scoped staging table* and then, inside one transaction, DELETE the
affected partitions (bounded on `ChargePeriodStart`, which the target requires)
for the bindings we processed and INSERT the staging rows. A re-run for the same
window deletes exactly what it re-inserts. The DML sets `maximum_bytes_billed`,
so a runaway replace fails rather than bills.

A note on types
---------------
The warehouse stores costs as NUMERIC (see `infra/bigquery/schema.sql`), but
pandas holds them as float64 and `df.to_parquet` writes them as Parquet DOUBLE.
BigQuery will not load a Parquet DOUBLE into a NUMERIC column. So staging holds
the decimals as FLOAT64 and the INSERT casts them to NUMERIC on the way into the
target. This is exactly the class of pin/type mismatch that only surfaces in a
Cloud Build, so it is handled here and stated plainly.

Everything a test needs is injected: the BigQuery client, the Parquet writer and
the connector factory are parameters, so the whole pipeline runs with fakes and
touches neither GCP nor the network. The engines are honest about what they
cannot see; this module is honest about what it did and did not load.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

import pandas as pd

from finops_core import config, focus
from finops_core import connectors as core_connectors
from finops_core.engines import optimize

ConnectorFactory = Callable[..., Any]
ParquetWriter = Callable[[pd.DataFrame, str], None]


# ==========================================================================
# Structured logging -- Cloud Logging parses a JSON line on stdout
# ==========================================================================


def log(severity: str, message: str, **fields: Any) -> None:
    """One JSON object per line. Never a secret value -- only labels and counts."""
    record: Dict[str, Any] = {"severity": severity, "message": message}
    record.update(fields)
    print(json.dumps(record, default=str), flush=True)


# ==========================================================================
# Settings -- env only, like the API service
# ==========================================================================


@dataclass(frozen=True)
class IngestSettings:
    project: Optional[str] = None
    dataset: str = "finops"
    focus_table: str = "focus_costs"
    opportunities_table: str = "opportunities"
    bucket: Optional[str] = None
    location: str = "us-central1"

    # A hard ceiling on the DML this job issues. BigQuery FAILS the job rather
    # than billing past it. 20 GiB at $6.25/TB is about 12 cents.
    max_bytes_billed: int = 20 * 1024**3

    # How far back a nightly ingest reaches. Two months catches late-arriving
    # and corrected line-items without rescanning the estate every night.
    lookback_months: int = 2

    # The optimization window. 24 months is what the detectors and the roadmap
    # reason over; it is also what the API's default analysis window assumes.
    opportunities_window_months: int = 24

    @property
    def focus_fqn(self) -> str:
        return f"{self.project}.{self.dataset}.{self.focus_table}"

    @property
    def opportunities_fqn(self) -> str:
        return f"{self.project}.{self.dataset}.{self.opportunities_table}"

    @classmethod
    def from_env(cls, source: Optional[Mapping[str, str]] = None) -> "IngestSettings":
        src = os.environ if source is None else source
        return cls(
            project=src.get("GOOGLE_CLOUD_PROJECT") or src.get("GCP_PROJECT"),
            dataset=src.get("BQ_DATASET", "finops"),
            focus_table=src.get("BQ_FOCUS_TABLE", "focus_costs"),
            opportunities_table=src.get("BQ_OPPORTUNITIES_TABLE", "opportunities"),
            bucket=src.get("GCS_BUCKET"),
            location=src.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
            max_bytes_billed=int(src.get("BQ_MAX_BYTES_BILLED", 20 * 1024**3)),
            lookback_months=int(src.get("INGEST_LOOKBACK_MONTHS", 2)),
            opportunities_window_months=int(src.get("OPPORTUNITIES_WINDOW_MONTHS", 24)),
        )


# ==========================================================================
# Column model -- derived from finops_core.focus.SCHEMA, never hand-listed
#
# The load and INSERT below build every column list and every schema from this
# one function, so a change to the FOCUS spec propagates without an edit here.
# ==========================================================================


@dataclass(frozen=True)
class Col:
    name: str
    kind: str  # 'string' | 'decimal' | 'datetime' | 'json'
    nullable: bool


def focus_columns() -> List[Col]:
    """The physical `focus_costs` columns, in schema.sql order.

    Every FOCUS 1.2 normative column + the six `tag_*` columns + provenance
    (`_ingested_at`, `_binding`). Types come straight from `focus.SCHEMA`; `json`
    columns (Tags, SkuPriceDetails) land as STRING, which is what schema.sql
    declares and what survives two vendors disagreeing on the key set.

    Nothing is filtered out here. The warehouse materialises the whole spec, and
    `services/api/tests/test_schema_parity.py` fails the build if it stops doing
    so -- which is the guard that would have caught the three pricing-currency
    columns that were once missing from the DDL and got mirrored into this file.
    """
    cols = [Col(c.name, c.dtype, c.nullable) for c in focus.SCHEMA]
    cols += [Col(f"tag_{t}", "string", nullable=False) for t in focus.CANONICAL_TAGS]
    cols += [Col("_ingested_at", "datetime", nullable=False), Col("_binding", "string", nullable=True)]
    return cols


# Target warehouse types (must match infra/bigquery/schema.sql exactly).
_TARGET_BQ_TYPE = {"string": "STRING", "decimal": "NUMERIC", "datetime": "TIMESTAMP", "json": "STRING"}
# Staging types: decimals as FLOAT64 so a Parquet DOUBLE loads without a cast.
_STAGE_BQ_TYPE = {"string": "STRING", "decimal": "FLOAT64", "datetime": "TIMESTAMP", "json": "STRING"}


def _stage_schema():
    from google.cloud import bigquery

    # Staging is lenient: every column NULLABLE, decimals FLOAT64. The target's
    # NOT NULL / NUMERIC constraints are enforced by the INSERT into it.
    return [bigquery.SchemaField(c.name, _STAGE_BQ_TYPE[c.kind], mode="NULLABLE") for c in focus_columns()]


def _pa_schema():
    """A pyarrow schema so an all-null column (e.g. ChargeClass) writes as a typed
    Parquet column, not a null-typed one BigQuery cannot load."""
    import pyarrow as pa

    kind_to_pa = {
        "string": pa.string(),
        "json": pa.string(),
        "decimal": pa.float64(),
        "datetime": pa.timestamp("us"),
    }
    return pa.schema([(c.name, kind_to_pa[c.kind]) for c in focus_columns()])


def _insert_select_lists() -> Tuple[str, str]:
    """Return (column_list, select_list) for `INSERT INTO target SELECT ... FROM stage`.

    Explicit, positionless column names -- never `SELECT *` -- so a reordered
    Parquet file cannot silently shift a value into the wrong column. Decimals
    are cast FLOAT64 -> NUMERIC here, which is the whole reason staging exists.
    """
    names = [c.name for c in focus_columns()]
    selects = []
    for c in focus_columns():
        if c.kind == "decimal":
            selects.append(f"CAST(`{c.name}` AS NUMERIC) AS `{c.name}`")
        else:
            selects.append(f"`{c.name}`")
    col_list = ", ".join(f"`{n}`" for n in names)
    select_list = ",\n               ".join(selects)
    return col_list, select_list


# ==========================================================================
# The one-frame-per-binding transform
# ==========================================================================


def _month_windows(start: date, end: date) -> List[Tuple[date, date]]:
    """[start, end) split into calendar-month [lo, hi) slices, to bound memory.

    A binding whose export is 2M line-items/month would blow the container's
    memory if fetched whole; the connectors take a range, so we ask a month at
    a time and log the row count of each.
    """
    windows: List[Tuple[date, date]] = []
    cur = date(start.year, start.month, 1)
    if cur < start:
        cur = start
    while cur < end:
        if cur.month == 12:
            nxt = date(cur.year + 1, 1, 1)
        else:
            nxt = date(cur.year, cur.month + 1, 1)
        windows.append((cur, min(nxt, end)))
        cur = nxt
    if not windows:
        windows.append((start, end))
    return windows


def _slug(label: str) -> str:
    keep = [ch.lower() if ch.isalnum() else "-" for ch in label]
    s = "".join(keep).strip("-")
    while "--" in s:
        s = s.replace("--", "-")
    return s or "binding"


@dataclass
class BindingResult:
    label: str
    status: str  # 'loaded' | 'empty' | 'failed'
    rows: int = 0
    gcs_uri: str = ""
    reason: str = ""

    @property
    def ok(self) -> bool:
        # A configured binding that connected counts as a success even at zero
        # rows. Only genuine failures (unconfigured, connect error, non-conformant)
        # count toward "every binding failed".
        return self.status in {"loaded", "empty"}


def _prepare_binding_frame(
    binding: config.AccountBinding,
    connector: Any,
    start: date,
    end: date,
    ingested_at: datetime,
) -> Optional[pd.DataFrame]:
    """Fetch, normalise, validate, explode + serialise tags, stamp provenance.

    Returns the concatenated frame for the binding, or None if it produced no
    rows. Raises `ValueError` if any month fails FOCUS validation -- the caller
    turns that into a per-binding abort, never a job abort.
    """
    frames: List[pd.DataFrame] = []
    for lo, hi in _month_windows(start, end):
        raw = connector.fetch_costs(lo, hi)
        if raw is None or len(raw) == 0:
            log("INFO", "binding month empty", binding=binding.label, month=lo.isoformat(), rows=0)
            continue

        frame = focus.normalize(raw)
        result = focus.validate(frame)
        if not result.ok:
            # Abort THIS binding only. A malformed feed must not corrupt the
            # warehouse, and it must not take down the clouds that are healthy.
            raise ValueError(
                f"{binding.label} {lo.isoformat()}: FOCUS validation failed -- "
                + "; ".join(result.errors[:5])
            )

        frame = focus.explode_tags(frame)   # Tags map -> tag_* columns
        frame = focus.serialize_tags(frame)  # Tags dict -> JSON STRING (schema.sql)
        # Stored tz-naive to sit alongside the other (naive) FOCUS timestamps; a
        # BigQuery TIMESTAMP is UTC by definition, so a naive UTC value is exact.
        stamp = pd.Timestamp(ingested_at)
        frame["_ingested_at"] = stamp.tz_convert("UTC").tz_localize(None) if stamp.tz is not None else stamp
        frame["_binding"] = binding.label
        log("INFO", "binding month fetched", binding=binding.label, month=lo.isoformat(), rows=int(len(frame)))
        frames.append(frame)

    if not frames:
        return None
    combined = pd.concat(frames, ignore_index=True)
    # Keep exactly the physical columns, in schema order, so the Parquet schema
    # and the load agree. Any 1.3 extension a connector emitted is dropped here.
    names = [c.name for c in focus_columns()]
    for n in names:
        if n not in combined.columns:
            combined[n] = pd.NA
    return combined[names]


# ==========================================================================
# BigQuery load + idempotent partition replace
# ==========================================================================


def _default_write_parquet(df: pd.DataFrame, uri: str) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pandas(df, schema=_pa_schema(), preserve_index=False)
    pq.write_table(table, uri)  # gs:// handled via fsspec/gcsfs


def _load_parquet_to_staging(bq: Any, uris: List[str], staging_fqn: str) -> None:
    from google.cloud import bigquery

    job_config = bigquery.LoadJobConfig(
        schema=_stage_schema(),
        source_format=bigquery.SourceFormat.PARQUET,
        # WRITE_APPEND: staging is a fresh, run-scoped table, so appending each
        # binding's file into it accumulates this run and nothing else.
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
    )
    job = bq.load_table_from_uri(uris, staging_fqn, job_config=job_config)
    job.result()


def partition_replace_script(target_fqn: str, staging_fqn: str) -> str:
    """The idempotent DML: replace the affected partitions for these bindings.

    Bounded on `ChargePeriodStart` because the target is
    `require_partition_filter = TRUE` -- and because bounding it is what prunes
    the DELETE to the partitions this run actually touched. One transaction, so
    a reader never sees the table mid-replace.
    """
    col_list, select_list = _insert_select_lists()
    return f"""
BEGIN TRANSACTION;

DELETE FROM `{target_fqn}`
WHERE DATE(ChargePeriodStart) BETWEEN @part_lo AND @part_hi
  AND _binding IN UNNEST(@bindings);

INSERT INTO `{target_fqn}` ({col_list})
SELECT {select_list}
FROM `{staging_fqn}`;

COMMIT TRANSACTION;
""".strip()


def _replace_partitions(
    bq: Any,
    settings: IngestSettings,
    staging_fqn: str,
    part_lo: date,
    part_hi: date,
    bindings: List[str],
) -> None:
    from google.cloud import bigquery

    sql = partition_replace_script(settings.focus_fqn, staging_fqn)
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("part_lo", "DATE", part_lo),
            bigquery.ScalarQueryParameter("part_hi", "DATE", part_hi),
            bigquery.ArrayQueryParameter("bindings", "STRING", bindings),
        ],
        maximum_bytes_billed=settings.max_bytes_billed,
        labels={"app": "finops", "job": "ingest"},
    )
    bq.query(sql, job_config=job_config).result()


# ==========================================================================
# ingest
# ==========================================================================


def run_ingest(
    settings: IngestSettings,
    accounts: List[config.AccountBinding],
    *,
    bq: Any,
    write_parquet: ParquetWriter,
    connector_factory: ConnectorFactory = core_connectors.get_connector,
    start: date,
    end: date,
    now: Optional[datetime] = None,
) -> int:
    """Run the ingest. Returns a process exit code.

    A binding that is unconfigured or failing contributes zero rows and is
    logged; it never aborts the job. The job exits non-zero only if EVERY
    binding failed -- otherwise a single dead payer would black out a working
    estate every night.
    """
    ingested_at = now or datetime.now(timezone.utc)
    dt_label = ingested_at.date().isoformat()

    if not accounts:
        log("WARNING", "no bindings configured (FINOPS_ACCOUNTS empty); nothing to ingest")
        return 0

    results: List[BindingResult] = []
    uris: List[str] = []
    processed_bindings: List[str] = []
    part_lo: Optional[date] = None
    part_hi: Optional[date] = None

    for binding in accounts:
        # Each binding carries ITS OWN secrets. We never merge in a shared global
        # key map: two AWS payers must never authenticate with each other's keys.
        try:
            connector = connector_factory(binding.connector, secrets=dict(binding.secret_map), **binding.option_map)
        except Exception as exc:  # unknown key, broken module
            log("ERROR", "connector construction failed", binding=binding.label, error=str(exc))
            results.append(BindingResult(binding.label, "failed", reason=str(exc)))
            continue

        try:
            probe = connector.test_connection()
        except Exception as exc:
            log("ERROR", "test_connection raised", binding=binding.label, error=str(exc))
            results.append(BindingResult(binding.label, "failed", reason=str(exc)))
            continue
        if not probe.ok:
            log("WARNING", "binding not connected; contributing zero rows", binding=binding.label, reason=probe.message)
            results.append(BindingResult(binding.label, "failed", reason=probe.message))
            continue

        try:
            frame = _prepare_binding_frame(binding, connector, start, end, ingested_at)
        except ValueError as exc:  # validation error -> abort this binding only
            log("ERROR", "binding aborted on FOCUS validation", binding=binding.label, error=str(exc))
            results.append(BindingResult(binding.label, "failed", reason=str(exc)))
            continue
        except Exception as exc:  # a connector fetch blew up -> skip, keep going
            log("ERROR", "binding fetch failed", binding=binding.label, error=str(exc))
            results.append(BindingResult(binding.label, "failed", reason=str(exc)))
            continue

        if frame is None or frame.empty:
            log("INFO", "binding connected but returned no rows", binding=binding.label, rows=0)
            results.append(BindingResult(binding.label, "empty", rows=0))
            continue

        uri = f"gs://{settings.bucket}/focus/dt={dt_label}/{_slug(binding.label)}.parquet"
        try:
            write_parquet(frame, uri)
        except Exception as exc:
            log("ERROR", "parquet write failed", binding=binding.label, uri=uri, error=str(exc))
            results.append(BindingResult(binding.label, "failed", reason=str(exc)))
            continue

        lo = frame["ChargePeriodStart"].min()
        hi = frame["ChargePeriodStart"].max()
        blo, bhi = pd.Timestamp(lo).date(), pd.Timestamp(hi).date()
        part_lo = blo if part_lo is None else min(part_lo, blo)
        part_hi = bhi if part_hi is None else max(part_hi, bhi)

        uris.append(uri)
        processed_bindings.append(binding.label)
        results.append(BindingResult(binding.label, "loaded", rows=int(len(frame)), gcs_uri=uri))
        log("INFO", "binding landed to GCS", binding=binding.label, rows=int(len(frame)), uri=uri)

    loaded = [r for r in results if r.status == "loaded"]
    if loaded:
        staging_fqn = f"{settings.project}.{settings.dataset}.{settings.focus_table}__stage_{uuid.uuid4().hex[:12]}"
        try:
            _load_parquet_to_staging(bq, uris, staging_fqn)
            assert part_lo is not None and part_hi is not None
            _replace_partitions(bq, settings, staging_fqn, part_lo, part_hi, processed_bindings)
            log(
                "INFO",
                "focus_costs partitions replaced",
                bindings=processed_bindings,
                partition_lo=part_lo.isoformat(),
                partition_hi=part_hi.isoformat(),
                rows=sum(r.rows for r in loaded),
            )
        finally:
            # Drop the run-scoped staging table whether or not the replace worked.
            try:
                bq.delete_table(staging_fqn, not_found_ok=True)
            except Exception as exc:
                log("WARNING", "staging table cleanup failed", table=staging_fqn, error=str(exc))

    ok = [r for r in results if r.ok]
    summary = {r.label: {"status": r.status, "rows": r.rows} for r in results}
    log(
        "INFO" if ok else "ERROR",
        "ingest complete",
        bindings=len(results),
        succeeded=len(ok),
        failed=len(results) - len(ok),
        rows=sum(r.rows for r in results),
        detail=summary,
    )
    # Exit non-zero ONLY if every binding failed.
    return 0 if ok else 1


# ==========================================================================
# opportunities
# ==========================================================================


def build_opportunities_frame(
    focus_df: pd.DataFrame,
    as_of: date,
    now: Optional[datetime] = None,
) -> pd.DataFrame:
    """Run every detector and shape the nightly snapshot row set.

    `opportunities_frame` drops the per-opportunity `evidence` dict (it is not a
    tabular column); we re-attach it here as a JSON STRING, keyed positionally to
    the same `opps` list it was built from, because the schema.sql table carries
    an `evidence` STRING and the API surfaces it. `as_of` and `_generated_at`
    make the snapshot addressable -- the API reads `WHERE as_of = MAX(as_of)`.
    """
    generated_at = now or datetime.now(timezone.utc)
    opps = optimize.detect_all(focus_df)
    frame = optimize.opportunities_frame(opps)
    if frame.empty:
        frame = frame.assign(evidence=pd.Series(dtype="object"))
    else:
        # opportunities_frame builds rows in opps order, so this stays aligned.
        frame["evidence"] = [json.dumps(o.evidence, default=str) for o in opps]
    frame.insert(0, "as_of", as_of.isoformat())  # STRING; PARSE_DATE on insert
    frame["_generated_at"] = generated_at
    return frame


_OPP_DECIMAL_COLS = {"monthly_savings", "annual_savings"}


def _opportunities_stage_schema():
    from google.cloud import bigquery

    # Mirrors schema.sql's opportunities table, with the same NUMERIC->FLOAT64 /
    # DATE->STRING staging shifts the focus load makes, cast back on INSERT.
    fields = [
        ("as_of", "STRING"),
        ("lever_id", "STRING"),
        ("lever_name", "STRING"),
        ("category", "STRING"),
        ("cloud", "STRING"),
        ("scope", "STRING"),
        ("monthly_savings", "FLOAT64"),
        ("annual_savings", "FLOAT64"),
        ("effort", "STRING"),
        ("risk", "STRING"),
        ("time_to_value", "STRING"),
        ("confidence", "FLOAT64"),
        ("evidence", "STRING"),
        ("resource_count", "INT64"),
        ("_generated_at", "TIMESTAMP"),
    ]
    return [bigquery.SchemaField(n, t, mode="NULLABLE") for n, t in fields]


def opportunities_replace_script(target_fqn: str, staging_fqn: str) -> str:
    """Replace exactly today's `as_of` partition. Idempotent on re-run.

    The API reads `WHERE as_of = (SELECT MAX(as_of) ...)`, so a half-written
    partition would be read as truth. One transaction: delete today, insert
    today, commit -- the reader sees the old snapshot or the new one, never a
    partial one.
    """
    return f"""
BEGIN TRANSACTION;

DELETE FROM `{target_fqn}` WHERE as_of = @as_of;

INSERT INTO `{target_fqn}`
  (as_of, lever_id, lever_name, category, cloud, scope, monthly_savings,
   annual_savings, effort, risk, time_to_value, confidence, evidence,
   resource_count, _generated_at)
SELECT
  PARSE_DATE('%Y-%m-%d', as_of),
  lever_id, lever_name, category, cloud, scope,
  CAST(monthly_savings AS NUMERIC),
  CAST(annual_savings AS NUMERIC),
  effort, risk, time_to_value, confidence, evidence,
  resource_count, _generated_at
FROM `{staging_fqn}`;

COMMIT TRANSACTION;
""".strip()


def run_opportunities(
    settings: IngestSettings,
    *,
    bq: Any,
    read_focus_window: Optional[Callable[[], pd.DataFrame]] = None,
    now: Optional[datetime] = None,
) -> int:
    """Read the trailing window, detect, and materialise the snapshot.

    `read_focus_window` is injected in tests; in production it queries the
    partition-bounded, byte-capped window below.
    """
    generated_at = now or datetime.now(timezone.utc)
    as_of = generated_at.date()

    reader = read_focus_window or (lambda: _read_focus_window(bq, settings))
    focus_df = reader()
    log("INFO", "opportunities window read", rows=int(len(focus_df)))

    frame = build_opportunities_frame(focus_df, as_of, now=generated_at)
    if frame.empty:
        log("WARNING", "no opportunities detected for window; writing empty snapshot", as_of=as_of.isoformat())

    staging_fqn = f"{settings.project}.{settings.dataset}.{settings.opportunities_table}__stage_{uuid.uuid4().hex[:12]}"
    try:
        _load_opportunities_to_staging(bq, frame, staging_fqn)
        _replace_opportunities(bq, settings, staging_fqn, as_of)
        log("INFO", "opportunities snapshot written", as_of=as_of.isoformat(), rows=int(len(frame)))
    finally:
        try:
            bq.delete_table(staging_fqn, not_found_ok=True)
        except Exception as exc:
            log("WARNING", "opportunities staging cleanup failed", table=staging_fqn, error=str(exc))
    return 0


def _read_focus_window(bq: Any, settings: IngestSettings) -> pd.DataFrame:
    from google.cloud import bigquery

    # The table is require_partition_filter = TRUE: this MUST bound
    # ChargePeriodStart or BigQuery rejects it. maximum_bytes_billed caps the
    # scan -- the one unavoidably wide read in the whole platform.
    sql = f"""
        SELECT *
        FROM `{settings.focus_fqn}`
        WHERE ChargePeriodStart >= TIMESTAMP(DATE_SUB(CURRENT_DATE(),
              INTERVAL {int(settings.opportunities_window_months)} MONTH))
    """
    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=settings.max_bytes_billed,
        labels={"app": "finops", "job": "opportunities"},
    )
    return bq.query(sql, job_config=job_config).to_dataframe()


def _load_opportunities_to_staging(bq: Any, frame: pd.DataFrame, staging_fqn: str) -> None:
    from google.cloud import bigquery

    job_config = bigquery.LoadJobConfig(
        schema=_opportunities_stage_schema(),
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
    )
    job = bq.load_table_from_dataframe(frame, staging_fqn, job_config=job_config)
    job.result()


def _replace_opportunities(bq: Any, settings: IngestSettings, staging_fqn: str, as_of: date) -> None:
    from google.cloud import bigquery

    sql = opportunities_replace_script(settings.opportunities_fqn, staging_fqn)
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("as_of", "DATE", as_of)],
        maximum_bytes_billed=settings.max_bytes_billed,
        labels={"app": "finops", "job": "opportunities"},
    )
    bq.query(sql, job_config=job_config).result()


# ==========================================================================
# CLI
# ==========================================================================


def _default_window(settings: IngestSettings, now: datetime) -> Tuple[date, date]:
    end = now.date()
    m = end.month - settings.lookback_months
    y = end.year
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1), end


def _parse_date(s: Optional[str]) -> Optional[date]:
    return date.fromisoformat(s) if s else None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="ingest.main", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="connectors -> GCS Parquet -> focus_costs")
    p_ingest.add_argument("--start", help="ISO date (default: first of the lookback month)")
    p_ingest.add_argument("--end", help="ISO date, exclusive upper bound (default: today)")

    sub.add_parser("opportunities", help="read a window -> optimize -> opportunities")

    args = parser.parse_args(argv)
    settings = IngestSettings.from_env()
    now = datetime.now(timezone.utc)

    from google.cloud import bigquery

    bq = bigquery.Client(project=settings.project)

    if args.command == "ingest":
        if not settings.bucket:
            log("ERROR", "GCS_BUCKET is required for ingest")
            return 2
        default_start, default_end = _default_window(settings, now)
        start = _parse_date(args.start) or default_start
        end = _parse_date(args.end) or default_end
        cfg = config.load_config(source=os.environ)
        log("INFO", "ingest starting", start=start.isoformat(), end=end.isoformat(), bindings=len(cfg.accounts))
        return run_ingest(
            settings,
            cfg.accounts,
            bq=bq,
            write_parquet=_default_write_parquet,
            start=start,
            end=end,
            now=now,
        )

    if args.command == "opportunities":
        log("INFO", "opportunities starting", window_months=settings.opportunities_window_months)
        return run_opportunities(settings, bq=bq, now=now)

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
