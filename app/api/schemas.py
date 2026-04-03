"""
Pydantic schemas for all API request and response bodies.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# /token
# ---------------------------------------------------------------------------

class TokenRequest(BaseModel):
    username: str = Field(..., examples=["super_admin_schoolA"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# /chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=512,
        examples=["How many students are enrolled in my school?"],
    )


class ChatResponse(BaseModel):
    question: str
    answer: str
    # Optionally expose the final (RBAC-modified) query in non-production envs
    debug_query: Optional[str] = None


# ---------------------------------------------------------------------------
# Generic error
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    detail: str
