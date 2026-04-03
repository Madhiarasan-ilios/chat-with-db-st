"""
LangGraph node functions.

Each node receives the full AgentState and returns a *partial* dict
that LangGraph merges back into the state.
"""
from __future__ import annotations

import logging
from typing import List

import boto3
from langchain_aws import ChatBedrockConverse          # ChatBedrockConverse is preferred in langchain-aws v1
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate      # PromptTemplate lives in langchain_core in v1

from app.core.config import settings
from app.db.mysql import get_sql_database
from app.engine.state import AgentState
from app.engine.tools import (
    apply_row_level_security,
    clean_sql,
    is_safe_sql,
    run_sql_query,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared LLM instance (created once at import time)
# ---------------------------------------------------------------------------

_bedrock_client = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)

# ChatBedrockConverse is the recommended client in langchain-aws >= 0.2
# It uses the Bedrock Converse API which supports all current Claude models
_llm = ChatBedrockConverse(
    model=settings.BEDROCK_MODEL_ID,
    client=_bedrock_client,
)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SQL_PROMPT = PromptTemplate.from_template(
    """
You are an expert SQL assistant who converts user questions into SQL queries
to retrieve data from a relational database.

User's Role: {user_role}
Associated UDISE Code (school context): {udise_code}
Allowed Tables (ONLY use these): {allowed_tables_list}

IMPORTANT:
- Return ONLY raw SQL query starting with SELECT
- DO NOT include ```sql, markdown, explanations, or any preamble
- ONLY reference tables from the Allowed Tables list
- DO NOT add WHERE clauses for udise_code yourself; the system applies row-level security

Database schema:
{schema}

Table relationships:
- school_users.school_id → schools.school_id
- students.udise_code ↔ schools.udise
- tc.student_uuid → students.uuid
- tc_files.ticket_id → tc.tc_id

QUERY RULES:
- MySQL syntax only (LIKE not ILIKE, backticks for reserved words)
- COUNT(*) for counts, LIMIT 1 when one result needed
- NEVER expose: password, password_hash, otp_code
- For student/admin specific lookups that lack an identifier, return exactly:
  "Please provide student details such as name, UUID, or registered mobile number."

EXAMPLES:
Q: how many students are there
SELECT COUNT(*) AS student_count FROM students;

Q: list schools in Chennai
SELECT school_name, district FROM schools WHERE district LIKE '%Chennai%';

Q: TC status for Vihaan Aarav Jain
SELECT t.tc_id, t.student_name, t.tc_status, t.updated_at
FROM tc t WHERE t.student_name LIKE '%Vihaan Aarav Jain%' LIMIT 1;

Question: {question}
"""
)

_ANSWER_PROMPT = PromptTemplate.from_template(
    """
You are a helpful assistant. Convert the SQL result into a clear, concise,
natural-language response. Do NOT mention SQL, queries, tables, or databases.

Rules:
1. Empty result → "No record found for the given details."
2. Clarification was requested → repeat the clarification message politely.
3. Security block → "I'm sorry, that query cannot be executed for security reasons."
4. Otherwise → provide clear details naturally (names, statuses, counts, etc.)

Question: {question}
SQL Query: {query}
SQL Result: {result}
Answer:
"""
)

_generate_sql = _SQL_PROMPT | _llm | StrOutputParser()
_format_answer = _ANSWER_PROMPT | _llm | StrOutputParser()


# ---------------------------------------------------------------------------
# Allowed-table registry per role
# ---------------------------------------------------------------------------

def _allowed_tables_for_role(role: str) -> List[str]:
    if role == "super_admin":
        return [
            "students", "schools", "school_users", "admin_profile",
            "student_transfer", "tc", "tc_files",
            "student_otp", "admin_otp", "superadmin_otp",
        ]
    return []


# ---------------------------------------------------------------------------
# Node 1 – Fetch schema + allowed tables
# ---------------------------------------------------------------------------

def node_fetch_schema(state: AgentState) -> dict:
    logger.info("[node] fetch_schema | user=%s role=%s", state["user_id"], state["user_role"])
    db = get_sql_database()
    allowed = _allowed_tables_for_role(state["user_role"])
    schema = db.get_table_info()
    return {"schema": schema, "allowed_tables": allowed}


# ---------------------------------------------------------------------------
# Node 2 – Generate SQL with LLM
# ---------------------------------------------------------------------------

def node_generate_sql(state: AgentState) -> dict:
    logger.info("[node] generate_sql | question=%s", state["question"])
    raw = _generate_sql.invoke(
        {
            "question": state["question"],
            "schema": state["schema"],
            "user_role": state["user_role"],
            "udise_code": state["udise_code"],
            "allowed_tables_list": ", ".join(state["allowed_tables"] or []),
        }
    )
    cleaned = clean_sql(raw)
    logger.debug("[node] generate_sql | cleaned_query=%s", cleaned)
    return {"raw_query": raw, "cleaned_query": cleaned}


# ---------------------------------------------------------------------------
# Node 3 – Security guard (validate + apply RBAC)
# ---------------------------------------------------------------------------

def node_security_guard(state: AgentState) -> dict:
    query = state.get("cleaned_query", "")
    allowed = state.get("allowed_tables", [])

    # LLM asked for more info instead of generating SQL
    if "please provide" in query.lower():
        logger.info("[node] security_guard | clarification requested")
        return {
            "clarification_needed": True,
            "security_passed": False,
            "final_query": None,
        }

    # Safety checks
    if not is_safe_sql(query, allowed):
        logger.warning("[node] security_guard | BLOCKED query: %s", query)
        return {
            "clarification_needed": False,
            "security_passed": False,
            "final_query": None,
        }

    # Apply row-level security (inject udise_code WHERE clause)
    secured_query = apply_row_level_security(
        query, state["user_role"], state["udise_code"]
    )
    logger.info("[node] security_guard | PASSED | final_query=%s", secured_query)
    return {
        "clarification_needed": False,
        "security_passed": True,
        "final_query": secured_query,
    }


# ---------------------------------------------------------------------------
# Node 4 – Execute SQL
# ---------------------------------------------------------------------------

def node_execute_sql(state: AgentState) -> dict:
    logger.info("[node] execute_sql | query=%s", state.get("final_query"))
    try:
        result = run_sql_query.invoke(state["final_query"])
    except Exception as exc:
        logger.error("[node] execute_sql | error: %s", exc)
        result = f"Error executing query: {exc}"
    return {"result": result}


# ---------------------------------------------------------------------------
# Node 5 – Format final answer
# ---------------------------------------------------------------------------

def node_format_answer(state: AgentState) -> dict:
    # Decide what result string to send to the LLM formatter
    if state.get("clarification_needed"):
        result_text = "Please provide student details such as name, UUID, or registered mobile number."
    elif not state.get("security_passed"):
        result_text = "__SECURITY_BLOCKED__"
    else:
        result_text = state.get("result", "No result.")

    answer = _format_answer.invoke(
        {
            "question": state["question"],
            "query": state.get("final_query") or state.get("cleaned_query") or "",
            "result": result_text,
        }
    )
    logger.info("[node] format_answer | answer=%s", answer[:120])
    return {"answer": answer}
