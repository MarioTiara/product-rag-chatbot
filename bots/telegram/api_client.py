
import asyncio
from typing import Any

import httpx

from bots.telegram.config import TelegramBotConfig


class ProductApiClient:
    def __init__(self, config: TelegramBotConfig) -> None:
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.api_url,
            timeout=config.request_timeout,
        )
        self._access_token: str | None = None
        self._token_lock = asyncio.Lock()

    async def close(self) -> None:
        await self._client.aclose()

    async def _authenticate(self) -> str:
        """Obtain a new access token."""
        async with self._token_lock:
            # Another concurrent request may already have refreshed it.
            if self._access_token is not None:
                return self._access_token

            response = await self._client.post(
                "/auth/login",
                data={
                    "username": self.config.auth_username,
                    "password": self.config.auth_password,
                },
            )
            response.raise_for_status()

            result = response.json()
            access_token = result.get("access_token")

            if not access_token:
                raise RuntimeError(
                    "Auth response does not contain access_token"
                )

            self._access_token = access_token
            return access_token

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

        response = await self._client.post(
            path,
            json=json,
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        if response.status_code != 401:
            response.raise_for_status()
            return response.json()

        # The token may have expired or been revoked.
        # Clear it only if it is still the token used by this request.
        async with self._token_lock:
            if self._access_token == token:
                self._access_token = None

        # Obtain a fresh token and retry once.
        new_token = await self._get_token()

        retry_response = await self._client.post(
            path,
            json=json,
            headers={
                "Authorization": f"Bearer {new_token}",
            },
        )

        # If this also fails, propagate the HTTP error.
        retry_response.raise_for_status()
        return retry_response.json()
