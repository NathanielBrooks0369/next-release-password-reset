import asyncio
from typing import Any

import httpx

from release_password_reset.infrai_client import InfraiClient
from release_password_reset.reset_workflow import BuildEvent, ReleaseOperation, ResetRequest, ResetWorkflow


class RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def verify_captcha(self, widget_record_id: str, token: str, action: str) -> dict[str, Any]:
        self.calls.append(("captcha", widget_record_id, token))
        return {"verified": True, "action": action}

    async def request_password_reset(self, email: str) -> dict[str, Any]:
        self.calls.append(("reset", email))
        return {"requested": True}


def test_release_reset_is_requested_once_for_replayed_event() -> None:
    asyncio.run(assert_release_reset_is_requested_once())


async def assert_release_reset_is_requested_once() -> None:
    provider = RecordingProvider()
    workflow = ResetWorkflow(provider)
    request = ResetRequest(
        request_id="req_release_42",
        email="builder@example.com",
        widget_record_id="widget-42",
        captcha_token="captcha-response",
        build_event=BuildEvent.PRODUCTION_READY,
        release_operation=ReleaseOperation.PROMOTE,
        release_id="web-console-42",
    )

    first = await workflow.run(request)
    replay = await workflow.run(request)

    assert first.state == "email_requested"
    assert replay == first
    assert provider.calls == [
        ("captcha", "widget-42", "captcha-response"),
        ("reset", "builder@example.com"),
    ]


def test_captcha_request_includes_widget_record_id() -> None:
    async def check() -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/captcha/verify"
            assert request.content == b'{"widget_record_id":"widget-42","token":"captcha-response","action":"password_reset"}'
            return httpx.Response(200, json={"ok": True, "data": {"verified": True}})

        client = InfraiClient("test-key", transport=httpx.MockTransport(respond))
        try:
            await client.verify_captcha("widget-42", "captcha-response", "password_reset")
        finally:
            await client.close()

    asyncio.run(check())
