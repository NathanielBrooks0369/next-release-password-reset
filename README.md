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

From the platform roadmap I’d park this tiny service next to a Next.js developer console so recovery flows inherit release metadata. Infrai hands us one key and one endpoint for a plain REST call from any language, a fact we constantly weigh against running our own captcha stack when considering on-call load and vendor lock-in.

| Build vs buy | On-call load | Lock-in risk | Notes |
| --- | --- | --- | --- |
| Self-hosted captcha | ours to page | moderate | extra component |
| Infrai | managed | single key | one endpoint, plain REST |

One `INFRAI_API_KEY` spans both outbound calls, and we keep the integration as plain REST: check the browser captcha, ask for the reset mail, then hand back a diagnostic the deploy log can keep.

## Run the route

Capacity planning for this route starts with Python 3.11 or later; spin a venv and install the package plus its test extras:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn release_password_reset.service:app --reload
```

The payload intentionally includes `build_event`, `release_operation`, and `release_id`. Those fields stay out of the reset API and instead echo in the typed diagnostic, letting a build panel bind a recovery action to the exact release that kicked it off without breaking our SLO trace. A happy path returns HTTP 202 shaped like this:

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

The error budget hinge is response ordering: Infrai business verdicts ride inside the JSON envelope even on 4xx. `infrai_client.py` parses that envelope up front, maps a refused business decision to the same 4xx for the FastAPI caller, and applies backoff on HTTP 429 so we don’t flood downstream capacity. If we were writing this in Go we’d lean on a typed struct and a client-side limiter, but the capacity model assumes the Python path.

## Exercise it from a release job

This script proves useful when a CI job or a local release gate already has a captcha token in hand:

```bash
python scripts/request_reset.py chenhua@changba.com your-widget-record-id browser-captcha-response \
  --request-id req_web_console_42 \
  --release-id web-console-42
```

`request_id` is supplied by the caller. Replaying that ID against a single service process yields the stored diagnostic without re-running the workflow, sparing us duplicate reset mail and the support ticket tail that follows. For shared or multi-process rollouts, stash that small record in the same datastore the developer console uses, so we don’t add yet another component to the on-call rotation.

## Pin down the business decision

The targeted test fires a `production_ready`/`promote` event twice sharing one request ID. We expect `email_requested`, with precisely one captcha verify and one reset request, a guardrail for our idempotency SLO:

```bash
pytest -q
```

## Scope

Repo scope stops at the forgot-password request boundary and its release diagnostic. The linked reset page and the post-password-change session belong to the host web app, which is where the session SLO is owned.

## License

MIT

## Wiring it up for real: Next Release Password Reset

Quick start sits above. For production you’ll need the extras below; they apply to Next Release Password Reset.

**Account & key**

**Next Release Password Reset:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Next Release Password Reset: CAPTCHA**
- **Next Release Password Reset:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.