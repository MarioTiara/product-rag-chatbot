
from __future__ import annotations

import logging
import re
import time
import uuid

from fastapi import FastAPI, Request
from starlette.responses import Response

from app.core.observability.context import request_id_var


logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def get_request_id(request: Request) -> str:
    """Use a valid incoming request ID or generate a new UUID."""

    incoming_id = request.headers.get(REQUEST_ID_HEADER, "").strip()

    if incoming_id and VALID_REQUEST_ID.fullmatch(incoming_id):
        return incoming_id

    return str(uuid.uuid4())


def register_observability_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def trace_request(
        request: Request,
        call_next,
    ) -> Response:
        request_id = get_request_id(request)
        token = request_id_var.set(request_id)

        started_at = time.perf_counter()
        status_code = 500

        # Only accept known channel names; never trust arbitrary
        # client-provided values as internal identity.
        incoming_channel = request.headers.get(
            "X-Client-Channel", "api"
        ).lower()

        channel = (
            incoming_channel
            if incoming_channel in {"api", "telegram"}
            else "api"
        )

        from app.core.observability.context import channel_var

        channel_token = channel_var.set(channel)

        request.state.request_id = request_id

        try:
            logger.info(
                "HTTP request started",
                extra={
                    "event": "http_request_started",
                    "http_method": request.method,
                    "path": request.url.path,
                },
            )

            response = await call_next(request)
            status_code = response.status_code

            response.headers[REQUEST_ID_HEADER] = request_id

            return response

        except Exception as exc:
            logger.exception(
                "HTTP request failed",
                extra={
                    "event": "http_request_failed",
                    "http_method": request.method,
                    "path": request.url.path,
                    "error_type": type(exc).__name__,
                },
            )
            raise

        finally:
            duration_ms = round(
                (time.perf_counter() - started_at) * 1000,
                2,
            )

            log_method = (
                logger.error
                if status_code >= 500
                else logger.warning
                if status_code >= 400
                else logger.info
            )

            log_method(
                "HTTP request completed",
                extra={
                    "event": "http_request_completed",
                    "http_method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )

            channel_var.reset(channel_token)
            request_id_var.reset(token)
