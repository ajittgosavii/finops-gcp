"""The warehouse DDL must not drift from the FOCUS specification.

`infra/bigquery/schema.sql` and `finops_core.focus.SCHEMA` describe the same
table. They are written in different languages, by different hands, at different
times -- which is exactly the situation in which one quietly loses a column.

It already happened once. The DDL omitted the three FOCUS 1.2 pricing-currency
columns. They are Conditional, not optional: a payer that bills in a currency
other than the billing currency carries its native-currency prices there, and a
missing column silently discards the only record of what was actually quoted.
Nothing would have failed. The numbers would just have been wrong for one payer.

So: assert it, rather than hope.
"""

from __future__ import annotations

import os
import re

import pytest

from finops_core import focus

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SCHEMA_SQL = os.path.join(ROOT, "infra", "bigquery", "schema.sql")

_COLUMN = re.compile(r"^\s{2}(\w+)\s+(STRING|TIMESTAMP|NUMERIC|INT64|FLOAT64|DATE)", re.M)

# Columns the DDL adds on top of the spec: our own provenance, and the six
# canonical allocation tags materialised on ingest so the filter row and the
# clustering key have something typed to bite on.
PROVENANCE = {"_ingested_at", "_binding"}


@pytest.fixture(scope="module")
def ddl() -> str:
    if not os.path.exists(SCHEMA_SQL):
        pytest.skip("schema.sql not present")
    return open(SCHEMA_SQL, encoding="utf-8").read()


def _focus_costs_columns(ddl: str) -> set:
    body = ddl.split("focus_costs`")[1].split("PARTITION BY")[0]
    return {m.group(1) for m in _COLUMN.finditer(body)}


def test_every_focus_column_exists_in_the_warehouse(ddl: str) -> None:
    declared = _focus_costs_columns(ddl)
    spec = {c.name for c in focus.SCHEMA}
    missing = spec - declared
    assert not missing, f"schema.sql is missing FOCUS columns: {sorted(missing)}"


def test_the_warehouse_invents_no_columns(ddl: str) -> None:
    declared = _focus_costs_columns(ddl)
    spec = {c.name for c in focus.SCHEMA}
    tags = {f"tag_{t}" for t in focus.CANONICAL_TAGS}
    extra = declared - spec - tags - PROVENANCE
    assert not extra, f"schema.sql declares columns FOCUS does not define: {sorted(extra)}"


def test_the_mandatory_columns_are_not_null(ddl: str) -> None:
    body = ddl.split("focus_costs`")[1].split("PARTITION BY")[0]
    for name in focus.MANDATORY_COLUMNS:
        col = focus.COLUMN_BY_NAME[name]
        if col.nullable:
            continue  # ChargeClass is Mandatory but nullable by design
        line = next((ln for ln in body.splitlines() if re.match(rf"^\s{{2}}{name}\s", ln)), None)
        assert line, f"{name} missing from schema.sql"
        assert "NOT NULL" in line, f"{name} is Mandatory and not nullable, but the DDL allows NULL"


def test_the_cost_guards_are_declared(ddl: str) -> None:
    """Both guards live in the DDL, not in convention. A query with no bound on
    the partition key is rejected by BigQuery rather than silently scanning two
    years of data."""
    assert "PARTITION BY DATE(ChargePeriodStart)" in ddl
    assert "CLUSTER BY ProviderName, ServiceCategory, tag_application" in ddl
    assert "require_partition_filter = TRUE" in ddl


def test_the_opportunities_snapshot_is_partitioned_by_as_of(ddl: str) -> None:
    """The API reads `WHERE as_of = (SELECT MAX(as_of) ...)`, so the nightly job
    must be able to replace exactly one partition."""
    assert "PARTITION BY as_of" in ddl
