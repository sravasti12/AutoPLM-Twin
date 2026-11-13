"""Production request budgets and durable concurrency around existing service operations."""

import asyncio
import logging
import os
import time
from email.message import Message

from fastapi import Depends, HTTPException, Request
from pymongo.errors import PyMongoError

from app.oidc_auth import get_validator
from app.review_auth import ReviewPrincipal, authorized_reviewer
from app.security_store import get_security_store, identity_key

logger = logging.getLogger("autoplm.security")


async def engineering_operation(request: Request, principal: ReviewPrincipal = Depends(authorized_reviewer)):
    if os.getenv("AUTOPLM_ENVIRONMENT", "local") == "local":
        yield principal
        return
    try:
        store = get_security_store()
        identity = identity_key(get_validator().config.issuer, principal.subject)
        media = Message()
        media["content-type"] = request.headers.get("content-type") or "application/json"
        subtype = media.get_content_subtype()
        is_json = media.get_content_maintype() == "application" and (
            subtype == "json" or subtype.endswith("+json")
        )
        body = {}
        # Match FastAPI's case-insensitive MIME parsing, including parameters and +json.
        # Inspect missing-header JSON conservatively; FastAPI retains its own acceptance policy.
        # Request.body/json cache their results, leaving the body readable by downstream handlers.
        if is_json and await request.body():
            try:
                body = await request.json()
            except ValueError:
                raise HTTPException(422, "Malformed engineering JSON request") from None
        if not isinstance(body, dict):
            raise HTTPException(422, "Engineering request must be an object")
        llm = (
            body.get("mode") == "llm"
            or body.get("mapper") == "llm"
            or request.query_params.get("mapper") == "llm"
        )
        if llm and os.getenv("AUTOPLM_ENABLE_LLM", "false") != "true":
            raise HTTPException(403, "Live provider execution is disabled")
        for key, limit in (("max_steps", 12), ("ticks", 100), ("fleets", 10)):
            if key in body and (type(body[key]) is not int or not 1 <= body[key] <= limit):
                raise HTTPException(422, "Production execution bounds exceeded")
        upload = body.get("dataset")
        if (
            isinstance(upload, dict)
            and isinstance(upload.get("records"), list)
            and len(upload["records"]) > 500
        ):
            raise HTTPException(422, "Production upload record bound exceeded")
        store.quota(identity, "executions")
        if llm:
            store.quota(identity, "llm_minute")
            store.quota(identity, "llm_day")
        with store.lock():
            yield principal
    except PyMongoError:
        logger.warning("security_event=execution_control_unavailable")
        raise HTTPException(503, "Engineering execution control unavailable") from None


async def engineering_decision(request: Request, principal: ReviewPrincipal = Depends(authorized_reviewer)):
    if os.getenv("AUTOPLM_ENVIRONMENT", "local") == "local":
        yield principal
        return
    try:
        store = get_security_store()
        store.quota(identity_key(get_validator().config.issuer, principal.subject), "decisions")
        # Serialize decisions on the same resource, independent of caller or process.
        with store.lock(request.url.path), store.lock():
            yield principal
    except PyMongoError:
        logger.warning("security_event=decision_control_unavailable")
        raise HTTPException(503, "Engineering decision control unavailable") from None


class RequestSizeLimit:
    def __init__(self, app, max_bytes=2_000_000):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or os.getenv("AUTOPLM_ENVIRONMENT", "local") == "local":
            return await self.app(scope, receive, send)
        body = bytearray()
        deadline = time.monotonic() + 10
        while True:
            try:
                message = await asyncio.wait_for(receive(), timeout=max(0, deadline - time.monotonic()))
            except TimeoutError:
                from starlette.responses import JSONResponse

                logger.warning("security_event=request_body_timeout")
                return await JSONResponse({"detail": "Request body timed out"}, status_code=408)(
                    scope, receive, send
                )
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.max_bytes:
                from starlette.responses import JSONResponse

                logger.warning("security_event=request_too_large")
                return await JSONResponse({"detail": "Request too large"}, status_code=413)(
                    scope, receive, send
                )
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        consumed = False

        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        return await self.app(scope, replay, send)
