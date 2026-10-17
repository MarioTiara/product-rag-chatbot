from __future__ import annotations


def test_create_conversation_and_persist_history(client, conversation_store):
    response = client.post(
        "/chat",
        json={"message": "Tell me about ASUS VivoBook 14"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation_id"]
    assert payload["answer"]

    history_response = client.get(f"/chat/{payload['conversation_id']}/history")
    assert history_response.status_code == 200

    history = history_response.json()
    assert history["conversation"]["conversation_id"] == payload["conversation_id"]
    assert len(history["messages"]) >= 4
    assert history["messages"][0]["role"] == "user"
    assert history["messages"][1]["role"] == "assistant"
    assert history["messages"][2]["role"] == "tool"
    assert history["messages"][-1]["role"] == "assistant"


def test_follow_up_uses_previous_context(client, fake_openai_client):
    first = client.post(
        "/chat",
        json={"message": "Tell me about ASUS VivoBook 14"},
    )
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]

    second = client.post(
        "/chat",
        json={
            "conversation_id": conversation_id,
            "message": "What about the 8 GB version?",
        },
    )

    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id
    assert "8 GB" in second.json()["answer"]

    calls = fake_openai_client.chat.completions.calls
    assert len(calls) >= 4

    second_turn_first_call_messages = calls[2]["messages"]
    assert any(
        item["role"] == "user" and item.get("content") == "Tell me about ASUS VivoBook 14"
        for item in second_turn_first_call_messages
    )
    assert any(
        item["role"] == "assistant" for item in second_turn_first_call_messages
    )


def test_invalid_conversation_id_returns_404(client):
    response = client.get("/chat/does-not-exist/history")
    assert response.status_code == 404

    response = client.post(
        "/chat",
        json={
            "conversation_id": "does-not-exist",
            "message": "Hello",
        },
    )
    assert response.status_code == 404
