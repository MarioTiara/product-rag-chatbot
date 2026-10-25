import asyncio
import logging
from typing import Any

import httpx

from bots.telegram.config import TelegramBotConfig
from bots.telegram.logging_config import setup_logging


setup_logging(log_filename="telegram_api.log")
logger = logging.getLogger(__name__)


class ProductApiClient:
    def __init__(self, config: TelegramBotConfig) -> None:
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.api_url,
            timeout=config.request_timeout,
        )
        self._access_token: str | None = None
        self._token_lock = asyncio.Lock()

        logger.info(
            "ProductApiClient initialized: api_url=%s",
            config.api_url,
        )

    async def close(self) -> None:
        await self._client.aclose()
        logger.info("HTTP client closed")

    async def _authenticate(self) -> str:
        """Obtain a new access token and log the authentication response."""
        async with self._token_lock:
            if self._access_token is not None:
                logger.info("Using cached access token")
                return self._access_token

            logger.info("Sending authentication request to /auth/login")

            try:
                response = await self._client.post(
                    "/auth/login",
                    data={
                        "username": self.config.auth_username,
                        "password": self.config.auth_password,
                    },
                )

                logger.info(
                    "Authentication HTTP status: %s",
                    response.status_code,
                )

                try:
                    response_body = response.json()
                except ValueError:
                    response_body = response.text

                # Never write the actual access token to logs.
                if isinstance(response_body, dict):
                    safe_body = response_body.copy()

                    if "access_token" in safe_body:
                        token_value = safe_body["access_token"]
                        safe_body["access_token"] = (
                            "[REDACTED]"
                            if token_value
                            else token_value
                        )

                    logger.info(
                        "Authentication response body: %s",
                        safe_body,
                    )
                else:
                    logger.info(
                        "Authentication response body: %s",
                        response_body,
                    )

                response.raise_for_status()

                if not isinstance(response_body, dict):
                    raise RuntimeError(
                        "Authentication response is not a JSON object"
                    )

                access_token = response_body.get("access_token")

                if not isinstance(access_token, str) or not access_token:
                    logger.error(
                        "Authentication failed: access_token missing"
                    )
                    raise RuntimeError(
                        "Auth response does not contain access_token"
                    )

                self._access_token = access_token

                logger.info(
                    "Authentication successful: access_token received"
                )

                return access_token

            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Authentication HTTP error: status=%s",
                    exc.response.status_code,
                )
                raise

            except httpx.RequestError:
                logger.exception(
                    "Network error during authentication"
                )
                raise

            except Exception:
                logger.exception(
                    "Unexpected authentication error"
                )
                raise

    async def _get_token(self) -> str:
        if self._access_token is not None:
            return self._access_token

        return await self._authenticate()

    async def post(
        self,
        path: str,
        json: dict[str, Any],
    ) -> dict[str, Any]:
        token = await self._get_token()

        logger.info("Sending API request: POST %s", path)

        response = await self._client.post(
            path,
            json=json,
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        logger.info(
            "API response: path=%s status=%s",
            path,
            response.status_code,
        )

        if response.status_code != 401:
            response.raise_for_status()
            return response.json()

        logger.warning(
            "API returned 401; refreshing access token"
        )

        async with self._token_lock:
            if self._access_token == token:
                self._access_token = None

        new_token = await self._get_token()

        retry_response = await self._client.post(
            path,
            json=json,
            headers={
                "Authorization": f"Bearer {new_token}",
            },
        )

        logger.info(
            "API retry response: path=%s status=%s",
            path,
            retry_response.status_code,
        )

        retry_response.raise_for_status()
        return retry_response.json()
