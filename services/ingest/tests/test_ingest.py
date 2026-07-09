"""Ingest tests. No network, no GCP.

A fake BigQuery client captures every load and every DML without touching
Google; the Parquet "writer" keeps the frame in memory so the assertions can
read it. The demo connector supplies conformant rows; two stub connectors supply
the failure modes the job must survive -- an unconfigured payer and a payer whose
feed is not FOCUS-conformant.

The contract these pin:
  * one dead binding does not black out a working estate,
  * a malformed feed aborts that binding and only that binding,
  * Tags land as a JSON STRING and provenance columns are stamped,
  * the opportunities snapshot carries `as_of` and a JSON `evidence` string,
  * the idempotent replace bounds ChargePeriodStart and caps bytes billed.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pandas as pd
import pytest

pytest.importorskip("google.cloud.bigquery")

from finops_core import config  # noqa: E402
from finops_core import connectors as core_connectors  # noqa: E402
from finops_core.connectors.base import ConnectionResult  # noqa: E402

from ingest import main  # noqa: E402


# ---------------------------------------------------------------- fakes


class _FakeJob:
    def __init__(self, df=None):
        self._df = df if df is not None else pd.DataFrame()

    def result(self):
        return None

    def to_dataframe(self):
        return self._df


class _FakeBQ:
    """Captures loads and DML. Never reaches Google."""

    def __init__(self):
        self.uri_loads = []
        self.df_loads = []
        self.queries = []
        self.deleted = []

    def load_table_from_uri(self, uris, destination, job_config=None):
        self.uri_loads.append((uris, destination, job_config))
        return _FakeJob()

    def load_table_from_dataframe(self, df, destination, job_config=None):
        self.df_loads.append((df.copy(), destination, job_config))
        return _FakeJob()

    def query(self, sql, job_config=None):
        self.queries.append((sql, job_config))
        return _FakeJob()

    def delete_table(self, name, not_found_ok=False):
        self.deleted.append(name)


class _FailingConnector:
    """Connected? No. Stands in for an unconfigured payer."""

    def test_connection(self) -> ConnectionResult:
        return ConnectionResult(ok=False, message="Not configured. Missing secret(s): AWS_ACCESS_KEY_ID")

    def fetch_costs(self, start, end):  # pragma: no cover - never reached
        raise AssertionError("fetch_costs must not run on an unconnected binding")


class _BadDataConnector:
    """Connects, then returns rows that are not FOCUS-conformant."""

    def test_connection(self) -> ConnectionResult:
        return ConnectionResult(ok=True, message="ok")

    def fetch_costs(self, start, end):
        # A single row with no mandatory values. `focus.normalize` adds the
        # mandatory columns as null, and `focus.validate` then rejects them.
        return pd.DataFrame([{"nonsense": 1, "ChargePeriodStart": pd.Timestamp("2026-05-15")}])


def _factory(key, secrets=None, **options):
    if key == "demo":
        return core_connectors.get_connector("demo", secrets=secrets, **options)
    if key == "failing":
        return _FailingConnector()
    if key == "bad":
        return _BadDataConnector()
    raise KeyError(key)


def _settings():
    return main.IngestSettings(project="proj", dataset="finops", bucket="bkt")


def _bindings():
    return [
        config.AccountBinding(cloud="AWS", connector="demo", name="Demo payer"),
        config.AccountBinding(cloud="AWS", connector="failing", name="Broken payer"),
        config.AccountBinding(cloud="AWS", connector="bad", name="Malformed payer"),
    ]


_NOW = datetime(2026, 7, 9, 3, 15, tzinfo=timezone.utc)
_WINDOW = (date(2026, 5, 1), date(2026, 6, 1))  # one calendar month


# ---------------------------------------------------------------- ingest


def _run_ingest():
    captured = {}

    def write_parquet(df, uri):
        captured[uri] = df.copy()

    bq = _FakeBQ()
    code = main.run_ingest(
        _settings(),
        _bindings(),
        bq=bq,
        write_parquet=write_parquet,
        connector_factory=_factory,
        start=_WINDOW[0],
        end=_WINDOW[1],
        now=_NOW,
    )
    return code, captured, bq


def test_a_failing_binding_does_not_abort_the_job():
    code, captured, bq = _run_ingest()
    # The demo binding loaded, so the job succeeds despite two failed bindings.
    assert code == 0
    assert len(captured) == 1, "only the demo binding should have landed a Parquet file"
    (uri,) = captured
    assert uri.startswith("gs://bkt/focus/dt=2026-07-09/")
    assert "demo-payer" in uri


def test_validation_error_aborts_only_that_binding():
    code, captured, bq = _run_ingest()
    # The malformed binding produced rows but failed FOCUS validation, so it
    # contributed nothing -- yet the demo binding still landed.
    assert code == 0
    assert len(captured) == 1
    assert "malformed-payer" not in next(iter(captured))
    # Exactly the demo binding's rows drive the single partition-replace.
    assert len(bq.uri_loads) == 1
    assert len(bq.queries) == 1


def test_tags_are_serialised_to_a_json_string():
    _, captured, _ = _run_ingest()
    frame = next(iter(captured.values()))
    tags = frame["Tags"].iloc[0]
    assert isinstance(tags, str), "Tags must be a JSON STRING to match schema.sql"
    assert isinstance(json.loads(tags), dict)


def test_provenance_columns_are_present():
    _, captured, _ = _run_ingest()
    frame = next(iter(captured.values()))
    assert "_binding" in frame.columns and "_ingested_at" in frame.columns
    assert (frame["_binding"] == "Demo payer").all()
    assert frame["_ingested_at"].notna().all()
    # The six canonical allocation tags were exploded into typed columns.
    for tag in ("tag_application", "tag_environment", "tag_business_unit"):
        assert tag in frame.columns


def test_job_fails_only_when_every_binding_fails():
    bq = _FakeBQ()
    code = main.run_ingest(
        _settings(),
        [
            config.AccountBinding(cloud="AWS", connector="failing", name="Broken A"),
            config.AccountBinding(cloud="AWS", connector="bad", name="Broken B"),
        ],
        bq=bq,
        write_parquet=lambda df, uri: None,
        connector_factory=_factory,
        start=_WINDOW[0],
        end=_WINDOW[1],
        now=_NOW,
    )
    assert code == 1
    assert bq.queries == [], "nothing landed, so no partition replace should run"


# ---------------------------------------------------------------- idempotent replace


def test_partition_replace_bounds_the_partition_and_caps_bytes():
    _, _, bq = _run_ingest()
    sql, job_config = bq.queries[0]
    # Bounded on the partition column -- the target is require_partition_filter=TRUE.
    assert "ChargePeriodStart" in sql
    assert "DATE(ChargePeriodStart) BETWEEN @part_lo AND @part_hi" in sql
    assert "_binding IN UNNEST(@bindings)" in sql
    # A runaway replace fails rather than bills.
    assert job_config.maximum_bytes_billed == _settings().max_bytes_billed
    # Idempotent shape: delete the partitions, then insert; one transaction.
    assert "BEGIN TRANSACTION" in sql and "COMMIT TRANSACTION" in sql
    assert "INSERT INTO" in sql and "SELECT *" not in sql  # explicit columns only


def test_partition_replace_casts_decimals_to_numeric():
    """Parquet DOUBLE cannot load into a NUMERIC column, so the INSERT casts."""
    _, _, bq = _run_ingest()
    sql, _ = bq.queries[0]
    assert "CAST(`EffectiveCost` AS NUMERIC)" in sql
    assert "CAST(`BilledCost` AS NUMERIC)" in sql


# ---------------------------------------------------------------- opportunities


def _demo_focus_df():
    from finops_core.connectors.demo import build_demo_dataset

    df, _, _ = build_demo_dataset(months=12)
    return df


def test_opportunities_frame_has_as_of_and_json_evidence():
    frame = main.build_opportunities_frame(_demo_focus_df(), date(2026, 7, 9), now=_NOW)
    assert not frame.empty, "the demo estate has detectable opportunities"
    assert "as_of" in frame.columns
    assert (frame["as_of"] == "2026-07-09").all()
    assert "_generated_at" in frame.columns
    ev = frame["evidence"].iloc[0]
    assert isinstance(ev, str), "evidence must be a JSON STRING for the opportunities table"
    assert isinstance(json.loads(ev), dict)


def test_opportunities_run_replaces_todays_partition_with_a_capped_query():
    bq = _FakeBQ()
    df = _demo_focus_df()
    code = main.run_opportunities(_settings(), bq=bq, read_focus_window=lambda: df, now=_NOW)
    assert code == 0
    # One dataframe load into staging, then one transactional replace.
    assert len(bq.df_loads) == 1
    sql, job_config = bq.queries[0]
    assert "DELETE FROM" in sql and "as_of = @as_of" in sql
    assert "PARSE_DATE('%Y-%m-%d', as_of)" in sql
    assert job_config.maximum_bytes_billed == _settings().max_bytes_billed
    assert any(p.name == "as_of" for p in job_config.query_parameters)


def test_opportunities_read_window_bounds_charge_period():
    """The trailing-window read must bound ChargePeriodStart (the table rejects an
    unbounded query) and cap bytes billed."""
    bq = _FakeBQ()
    main._read_focus_window(bq, _settings())
    sql, job_config = bq.queries[0]
    assert "ChargePeriodStart >=" in sql
    assert job_config.maximum_bytes_billed == _settings().max_bytes_billed
