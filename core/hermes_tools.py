#!/usr/bin/env python3

import os
import secrets
import threading

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from persistent_workflow import persistent_document_workflow


app = FastAPI(
    title="Hermes Restricted Tools",
    version="2.0.5",
    description="Restricted document creation tools for Hermes.",
)

workflow_lock = threading.Lock()


class DocumentRequest(BaseModel):
    filename: str = Field(
        ...,
        description="New TXT filename, for example meeting-notes.txt",
        min_length=5,
        max_length=104,
    )

    text: str = Field(
        ...,
        description="Text to write into the document.",
        min_length=1,
        max_length=10000,
    )


def authenticate(authorization):
    expected = os.environ.get("HERMES_TOOL_TOKEN")

    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Tool authentication is not configured",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Bearer token required",
        )

    supplied = authorization.removeprefix("Bearer ").strip()

    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=403,
            detail="Invalid token",
        )


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.post(
    "/tools/create-document",
    operation_id="hermes_create_document",
    summary="Create a new text document",
    description=(
        "Create a new TXT document inside the Hermes Documents "
        "workspace. Never overwrite an existing file."
    ),
)
def create_document(
    request: DocumentRequest,
    authorization: str | None = Header(default=None),
):
    authenticate(authorization)

    if not workflow_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="Another Hermes document workflow is running",
        )

    try:
        report = persistent_document_workflow(
            request.filename,
            request.text,
        )

        if not report["success"]:
            raise HTTPException(
                status_code=422,
                detail=report,
            )

        return report

    finally:
        workflow_lock.release()
