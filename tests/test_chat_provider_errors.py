from __future__ import annotations

import httpx
from openai import AuthenticationError


def test_chat_returns_503_when_openai_authentication_fails(
    client,
    chatbot_orchestrator,
    monkeypatch,
):
    response = httpx.Response(
        status_code=401,
        request=httpx.Request(
            "POST",
            "https://api.openai.com/v1/chat/completions",
        ),
        json={
            "error": {
                "message": "Your API key has been invalidated.",
                "type": None,
                "code": "token_invalidated",
                "param": None,
            },
            "status": 401,
        },
    )

    def raise_auth_error(*args, **kwargs):
        raise AuthenticationError(
            "Your API key has been invalidated.",
            response=response,
            body=response.json(),
        )

    monkeypatch.setattr(
        chatbot_orchestrator.client.chat.completions,
        "create",
        raise_auth_error,
    )

    api_response = client.post(
        "/chat",
        json={"message": "Hello"},
    )

    assert api_response.status_code == 503
    assert "OPENAI_API_KEY" in api_response.json()["detail"]
