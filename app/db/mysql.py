"""
MySQL read-only connection pool.

A single SQLAlchemy engine is created once and reused for the lifetime of
the process.  The SQLDatabase wrapper (LangChain) is recreated on first
call and cached thereafter.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

from app.core.config import settings

logger = logging.getLogger(__name__)

# Tables the LLM is allowed to inspect and query
INCLUDED_TABLES = [
    "students",
    "schools",
    "school_users",
    "admin_profile",
    "student_transfer",
    "tc",
    "tc_files",
    "student_otp",
    "admin_otp",
    "superadmin_otp",
]


@lru_cache(maxsize=1)
def get_engine():
    """Return a connection-pooled SQLAlchemy engine (read-only user recommended)."""
    url = settings.database_url
    logger.info("Creating MySQL engine → %s:%s/%s", settings.DB_HOST, settings.DB_PORT, settings.DB_NAME)
    return create_engine(
        url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,      # detect stale connections
        connect_args={
            "connect_timeout": 10,
            "read_timeout": 30,
        },
    )


@lru_cache(maxsize=1)
def get_sql_database() -> SQLDatabase:
    """Return the LangChain SQLDatabase wrapper (cached singleton)."""
    engine = get_engine()
    logger.info("Initialising LangChain SQLDatabase with tables: %s", INCLUDED_TABLES)
    return SQLDatabase(
        engine=engine,
        include_tables=INCLUDED_TABLES,
        sample_rows_in_table_info=2,   # keep schema prompt lean
    )
