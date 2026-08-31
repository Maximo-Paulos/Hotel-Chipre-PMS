"""Transport schemas for authenticated field-level collaboration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CollaborationTicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_type: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    resource_id: int = Field(gt=0)


class CollaborationTicketResponse(BaseModel):
    ticket: str
    expires_in: int
    resource_type: str
    resource_id: int


class CollaborationPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # ``pending`` is used by a newly opened editor until its first successful
    # server response supplies the opaque SHA-256 revision.  The server still
    # compares the submitted base_values field-by-field before applying it.
    base_revision: str = Field(min_length=1, max_length=128, pattern=r"^(?:pending|[0-9a-f]{64})$")
    changes: dict[str, Any] = Field(default_factory=dict)
    # The server uses these values only to detect same-field edits. They are
    # never trusted as the current resource and are validated against the same
    # field allowlist as ``changes``.
    base_values: dict[str, Any] = Field(default_factory=dict)
