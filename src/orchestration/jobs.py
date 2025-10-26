"""
Compatibility shim to reference the primary Dagster job definitions.

The authoritative job definitions now live under the top-level ``src`` package.
This module simply re-exports them so any legacy imports continue to work.
"""

from src.orchestration.jobs import ingest_job as ingest_job  # noqa: F401

__all__ = ["ingest_job"]
