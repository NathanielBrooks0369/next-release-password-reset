from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field


class BuildEvent(StrEnum):
    PREVIEW_READY = "preview_ready"
    PRODUCTION_READY = "production_ready"


class ReleaseOperation(StrEnum):
    PREVIEW = "preview"
    PROMOTE = "promote"


class ResetRequest(BaseModel):
    request_id: str = Field(min_length=8, max_length=80)
    email: str = Field(min_length=3, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    widget_record_id: str = Field(min_length=1)
    captcha_token: str = Field(min_length=1)
    build_event: BuildEvent
    release_operation: ReleaseOperation
    release_id: str = Field(min_length=1, max_length=120)


class ResetDiagnostic(BaseModel):
    request_id: str
    release_id: str
    build_event: BuildEvent
    release_operation: ReleaseOperation
    state: str
    message: str


class ResetProvider(Protocol):
    async def verify_captcha(self, widget_record_id: str, token: str, action: str) -> dict[str, Any]:
        """Verify the browser response for this action."""

    async def request_password_reset(self, email: str) -> dict[str, Any]:
        """Ask the provider to send the reset email."""


class ResetWorkflow:
    def __init__(self, provider: ResetProvider) -> None:
        self._provider = provider
        self._completed: dict[str, ResetDiagnostic] = {}

    async def run(self, request: ResetRequest) -> ResetDiagnostic:
        previous = self._completed.get(request.request_id)
        if previous is not None:
            return previous

        await self._provider.verify_captcha(request.widget_record_id, request.captcha_token, "password_reset")
        await self._provider.request_password_reset(str(request.email))

        result = ResetDiagnostic(
            request_id=request.request_id,
            release_id=request.release_id,
            build_event=request.build_event,
            release_operation=request.release_operation,
            state="email_requested",
            message="Password reset email requested for this release.",
        )
        self._completed[request.request_id] = result
        return result
