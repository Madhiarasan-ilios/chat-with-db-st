"""
Custom LangChain tools for read-only MySQL access.
"""
from __future__ import annotations

import re
import sqlparse
from typing import List

from langchain_core.tools import tool
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool

from app.db.mysql import get_sql_database


# ---------------------------------------------------------------------------
# Re-usable helpers
# ---------------------------------------------------------------------------

_BLOCKED_KEYWORDS = frozenset(
    ["drop", "delete", "insert", "update", "alter", "create", "truncate", "replace"]
)


def is_safe_sql(sql_query: str, allowed_tables: List[str]) -> bool:
    """
    Light-weight safety check:
    1. Reject any DDL / DML statement.
    2. Confirm only allowed tables are referenced.

    For production, swap the table-extraction heuristic with a real
    SQL parser (e.g. ``sqlglot``) that handles sub-queries and CTEs.
    """
    q_lower = sql_query.lower()

    # Must be a SELECT
    if not q_lower.strip().startswith("select"):
        return False

    # Block mutation keywords
    if any(kw in q_lower for kw in _BLOCKED_KEYWORDS):
        return False

    # Extract table names that appear after FROM / JOIN
    referenced = set()
    for match in re.finditer(r"\b(?:from|join)\s+`?(\w+)`?", q_lower):
        referenced.add(match.group(1))

    if not referenced:
        return False  # Can't verify → block

    allowed = {t.lower() for t in allowed_tables}
    blocked = referenced - allowed
    if blocked:
        return False

    return True


def apply_row_level_security(
    sql_query: str,
    user_role: str,
    udise_code: str,
) -> str:
    """
    Inject a WHERE / AND clause that scopes the query to the caller's
    school (identified by ``udise_code``).

    Only applied when ``user_role == 'super_admin'``.
    The column name per table:
        students   → udise_code
        schools    → udise
        tc         → current_udise_code
    """
    if user_role != "super_admin" or not udise_code:
        return sql_query

    _TABLE_UDISE_COL = {
        "students": "udise_code",
        "schools": "udise",
        "tc": "current_udise_code",
    }

    q_lower = sql_query.lower()
    modified = sql_query

    for table, col in _TABLE_UDISE_COL.items():
        pattern = rf"\b(?:from|join)\s+`?{table}`?"
        if re.search(pattern, q_lower):
            filter_clause = f"{table}.{col} = '{udise_code}'"
            if " where " in modified.lower():
                # Prepend to existing WHERE
                idx = modified.lower().find(" where ") + len(" where ")
                modified = modified[:idx] + filter_clause + " AND " + modified[idx:]
            else:
                modified = modified.rstrip("; \n") + f" WHERE {filter_clause}"
            break  # one filter injection per query is enough for this use-case

    return modified


def clean_sql(raw: str) -> str:
    """Strip markdown fences and leading non-SELECT text."""
    raw = raw.replace("```sql", "").replace("```", "")
    up = raw.upper()
    if "SELECT" in up:
        raw = raw[up.find("SELECT"):]
    return raw.strip()


# ---------------------------------------------------------------------------
# LangChain tool (used inside graph nodes)
# ---------------------------------------------------------------------------

@tool
def run_sql_query(query: str) -> str:
    """Execute a read-only SQL SELECT against the school database and return results."""
    db = get_sql_database()
    executor = QuerySQLDatabaseTool(db=db)
    return executor.invoke(query)
