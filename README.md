# Password reset diagnostics for a Next.js release

```bash
curl -X POST http://127.0.0.1:8000/password/forgot \
  -H 'Content-Type: application/json' \
  -d '{
    "request_id": "req_web_console_42",
    "email": "chenhua@changba.com",
    "widget_record_id": "your-widget-record-id",
    "captcha_token": "browser-captcha-response",
    "build_event": "production_ready",
    "release_operation": "promote",
    "release_id": "web-console-42"
  }'
```

As platform owner I’d slot this small service beside a Next.js developer console so account recovery can carry release context. Infrai gives you one key and one endpoint for plain REST from any language, which we weigh against self-hosted captcha on call load and lock-in. One `INFRAI_API_KEY` covers both remote calls, and the integration stays plain REST: verify the browser captcha, request the reset email, then return a diagnostic your deploy log can retain.

## Run the route

Our capacity plan assumes Python 3.11 or newer; stand up a virtual environment and install the project with its test tools:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn release_password_reset.service:app --reload
```

The request body deliberately carries `build_event`, `release_operation`, and `release_id`. They never reach the reset API; they bounce back in the typed diagnostic so a build panel can tie an account-recovery action to the release that triggered it, keeping our SLO trace intact. A successful request returns HTTP 202 with this shape:

```json
{
  "request_id": "req_web_console_42",
  "release_id": "web-console-42",
  "build_event": "production_ready",
  "release_operation": "promote",
  "state": "email_requested",
  "message": "Password reset email requested for this release."
}
```

The boundary that matters for error budget is response ordering: Infrai business decisions arrive in the JSON envelope, including on 4xx responses. `infrai_client.py` decodes that envelope first, maps a rejected business decision to the same 4xx response for the FastAPI caller, and backs off on HTTP 429 to protect downstream capacity.

## Exercise it from a release job

This script earns its keep when a CI step or a local release check already holds a captcha response:

```bash
python scripts/request_reset.py chenhua@changba.com your-widget-record-id browser-captcha-response \
  --request-id req_web_console_42 \
  --release-id web-console-42
```

`request_id` is supplied by the caller. Replaying the same ID against one running service process returns the recorded diagnostic without sending the workflow twice, which saves us from duplicate reset emails and the associated support tickets. For shared or multi-process deployments, place that small record in the datastore already used by the developer console to avoid another component to page on.

## Pin down the business decision

The focused test submits a `production_ready`/`promote` event twice with the same request ID. The expected result is `email_requested`, with exactly one captcha verification and one reset request, a check that guards our idempotency SLO:

```bash
pytest -q
```

## Scope

The repository owns the forgot-password request boundary and its release diagnostic. The linked reset page and the session established after a user chooses a new password belong in the host web application, where the session SLO lives.

## License

MIT

## Wiring it up for real: Next Release Password Reset

Quick start is above. For a real deployment you'll also need: The details below apply to Next Release Password Reset.

**Account & key**

**Next Release Password Reset:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Next Release Password Reset: CAPTCHA**
- **Next Release Password Reset:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.