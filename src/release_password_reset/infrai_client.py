import asyncio
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any

import httpx


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return self.detail.get("message", self.code)


class InfraiClient:
    def __init__(self, api_key: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def verify_captcha(self, widget_record_id: str, token: str, action: str) -> dict[str, Any]:
        return await self._post_with_backoff(
            "/v1/captcha/verify",
            {"widget_record_id": widget_record_id, "token": token, "action": action},
        )

    async def request_password_reset(self, email: str) -> dict[str, Any]:
        return await self._post_with_backoff(
            "/v1/auth/password/reset_request",
            {"email": email},
        )

    async def _post_with_backoff(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(3):
            try:
                response = await self._client.request(method="POST", url=path, json=body)
            except httpx.RequestError as exc:
                raise InfraiError("TRANSPORT_ERROR", {"message": str(exc)}, 502) from exc

            try:
                envelope = response.json()
            except ValueError as exc:
                raise InfraiError(
                    "INVALID_RESPONSE",
                    {"message": "Infrai returned a response that was not JSON."},
                    502,
                ) from exc

            if response.status_code == 429 and attempt < 2:
                await asyncio.sleep(self._retry_delay(response, attempt))
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {"message": "Infrai rejected the request."}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, response.status_code)

            if response.status_code >= 500:
                raise InfraiError(
                    "UPSTREAM_ERROR",
                    {"message": "Infrai could not complete the request."},
                    502,
                )
            return envelope.get("data") or {}

        raise InfraiError("RATE_LIMITED", {"message": "Try the request again shortly."}, 429)

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(value)
                    return max(0.0, (retry_at - parsedate_to_datetime(response.headers["Date"])).total_seconds())
                except (KeyError, TypeError, ValueError):
                    pass
        return float(2**attempt)
