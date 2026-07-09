"""The ingest Cloud Run Job.

Connectors -> GCS Parquet -> BigQuery `focus_costs`, then a nightly materialise
of the `opportunities` snapshot. This package imports `finops_core` for the
FOCUS contract and the optimization detectors and owns nothing about the schema
itself -- if `finops_core.focus.SCHEMA` changes, the load schema below follows.
"""
