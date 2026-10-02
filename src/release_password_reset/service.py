import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request

from .infrai_client import InfraiClient, InfraiError
from .reset_workflow import ResetDiagnostic, ResetRequest, ResetWorkflow


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set INFRAI_API_KEY before starting the service.")
    client = InfraiClient(api_key)
    app.state.infrai_client = client
    app.state.reset_workflow = ResetWorkflow(client)
    yield
    await client.close()


app = FastAPI(title="Release password reset", lifespan=lifespan)


@app.post("/password/forgot", response_model=ResetDiagnostic, status_code=202)
async def forgot_password(payload: ResetRequest, request: Request) -> ResetDiagnostic:
    workflow: ResetWorkflow = request.app.state.reset_workflow
    try:
        return await workflow.run(payload)
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
