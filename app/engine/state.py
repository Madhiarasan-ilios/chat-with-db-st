from typing import TypedDict, Optional, List


class AgentState(TypedDict):
    # ── Input ──────────────────────────────────────────────
    question: str
    user_id: str
    user_role: str
    udise_code: str

    # ── Intermediate ───────────────────────────────────────
    schema: Optional[str]
    allowed_tables: Optional[List[str]]
    raw_query: Optional[str]
    cleaned_query: Optional[str]

    # ── Security gate ──────────────────────────────────────
    security_passed: Optional[bool]
    clarification_needed: Optional[bool]
    final_query: Optional[str]          # RBAC-modified query ready to execute

    # ── Output ─────────────────────────────────────────────
    result: Optional[str]               # Raw SQL result string
    answer: Optional[str]               # Final natural-language answer
    error: Optional[str]
