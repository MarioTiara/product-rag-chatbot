from __future__ import annotations

import json


def _first_tool_call_arguments(conversation_store, conversation_id: str) -> dict[str, object]:
    messages = conversation_store.get_messages(conversation_id)
    assistant_message = next(message for message in messages if message.role == "assistant" and message.tool_calls)
    tool_call = assistant_message.tool_calls[0]
    return json.loads(tool_call["function"]["arguments"])


def test_chat_uses_search_tool_for_cheapest_i7_with_min_ram(client, conversation_store, db_service):
    response = client.post(
        "/chat",
        json={
            "message": "Carikan saya pilihan laptop termurah dengan spesifikasi minimal Intel Core i7 dan RAM 16 GB.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"]

    tool_arguments = _first_tool_call_arguments(conversation_store, payload["conversation_id"])
    assert tool_arguments["processor_brand"] == "Intel"
    assert tool_arguments["processor_name"] == "Intel Core i7"
    assert tool_arguments["min_ram"] == 16
    assert tool_arguments["sort_by"] == "price"
    assert tool_arguments["sort_order"] == "asc"

    with db_service.connect() as connection:
        expected = connection.execute(
            """
            SELECT name
            FROM products
            WHERE ram_gb >= ?
              AND LOWER(processor_name) LIKE ?
            ORDER BY price ASC, brand, name
            LIMIT 1
            """,
            (16, "%i7%"),
        ).fetchone()

    assert expected is not None
    assert expected[0] in payload["answer"]
    assert "tidak tersedia" not in payload["answer"].lower()


def test_chat_returns_no_match_only_when_search_results_are_empty(client, conversation_store):
    response = client.post(
        "/chat",
        json={
            "message": "Carikan laptop dengan Intel Core i7 dan RAM 64 GB.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"]

    tool_arguments = _first_tool_call_arguments(conversation_store, payload["conversation_id"])
    assert tool_arguments["min_ram"] == 64
    assert "couldn't find" in payload["answer"].lower()
