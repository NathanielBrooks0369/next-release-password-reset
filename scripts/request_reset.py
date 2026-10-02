import argparse
import asyncio
import json
import os

from release_password_reset.infrai_client import InfraiClient
from release_password_reset.reset_workflow import BuildEvent, ReleaseOperation, ResetRequest, ResetWorkflow


async def main() -> None:
    parser = argparse.ArgumentParser(description="Request a reset email for a developer-tools release.")
    parser.add_argument("email")
    parser.add_argument("widget_record_id")
    parser.add_argument("captcha_token")
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--release-id", required=True)
    args = parser.parse_args()

    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise SystemExit("Set INFRAI_API_KEY before running this script.")

    client = InfraiClient(api_key)
    try:
        result = await ResetWorkflow(client).run(
            ResetRequest(
                request_id=args.request_id,
                email=args.email,
                widget_record_id=args.widget_record_id,
                captcha_token=args.captcha_token,
                build_event=BuildEvent.PRODUCTION_READY,
                release_operation=ReleaseOperation.PROMOTE,
                release_id=args.release_id,
            )
        )
        print(json.dumps(result.model_dump(mode="json"), indent=2))
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
