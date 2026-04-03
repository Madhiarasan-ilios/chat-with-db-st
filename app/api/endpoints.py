"""
API route handlers.

Routes:
    POST /token  – issue a JWT for a mock super-admin user
    POST /chat   – run the LangGraph SQL-agent pipeline
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import MOCK_USERS, get_current_super_admin
from app.api.schemas import ChatRequest, ChatResponse, TokenRequest, TokenResponse
from app.core.config import settings
from app.core.security import create_access_token
from app.engine.graph import get_graph

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /token
# ---------------------------------------------------------------------------

@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Obtain a JWT access token",
    tags=["auth"],
)
async def login(req: TokenRequest) -> TokenResponse:
    """
    Issue a signed JWT for a recognised super-admin username.

    In production, replace ``MOCK_USERS`` with a real credential check
    (e.g. verify a hashed password, query a users table, etc.).
    """
    user = MOCK_USERS.get(req.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown username: {req.username!r}",
        )

    token = create_access_token(
        data={
            "sub": user["id"],
            "role": user["role"],
            "udise_code": user["udise_code"],
        }
    )
    return TokenResponse(access_token=token)


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask a natural-language question about school data",
    tags=["agent"],
)
async def chat(
    req: ChatRequest,
    current_user: Dict[str, Any] = Depends(get_current_super_admin),
) -> ChatResponse:
    """
    Run the LangGraph SQL-agent pipeline and return a natural-language answer.

    The JWT is used to:
    * Verify the caller is a super_admin.
    * Scope all generated queries to the caller's ``udise_code`` (row-level security).
    """
    graph = get_graph()

    agent_input = {
        "question": req.question,
        "user_id": current_user["id"],
        "user_role": current_user["role"],
        "udise_code": current_user["udise_code"],
        # remaining state keys start as None / empty
        "schema": None,
        "allowed_tables": None,
        "raw_query": None,
        "cleaned_query": None,
        "security_passed": None,
        "clarification_needed": None,
        "final_query": None,
        "result": None,
        "answer": None,
        "error": None,
    }

    try:
        final_state = await graph.ainvoke(agent_input)
    except Exception as exc:
        logger.exception("Graph invocation error for user=%s", current_user["id"])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your question.",
        ) from exc

    # Optionally expose the executed query in non-prod environments
    debug_query = None
    if settings.APP_ENV != "production":
        debug_query = final_state.get("final_query") or final_state.get("cleaned_query")

    return ChatResponse(
        question=req.question,
        answer=final_state.get("answer", "No answer generated."),
        debug_query=debug_query,
    )
