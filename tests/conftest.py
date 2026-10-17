from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from fastapi.testclient import TestClient

from app.chatbot import ChatbotOrchestrator
from app.conversation_store import ConversationStore
from app.database import DatabaseService
from app.dependencies import (
    get_chatbot_orchestrator,
    get_conversation_store,
    get_product_service,
)
from app.main import app
from app.product_service import ProductService


TEST_PRODUCTS = [
    {
        "sku": "ASUS-VIVO-8",
        "brand": "ASUS",
        "name": "ASUS VivoBook 14 X1404VA Laptop (14 Inch | Intel Core i5 | 8 GB | Windows 11 | 512 GB SSD)",
        "category": "laptop",
        "price": 1000.0,
        "processor_name": "Intel Core i5",
        "processor_brand": "Intel",
        "ram_expandable": "Yes",
        "ram": "8 GB",
        "ram_type": "DDR4",
        "ghz": "3.5 GHz",
        "display_type": "IPS",
        "display": "14 Inch",
        "gpu": "Intel UHD",
        "gpu_brand": "Intel",
        "ssd": "512 GB",
        "hdd": None,
        "stock": 3,
        "battery_life": "8 hours",
    },
    {
        "sku": "ASUS-VIVO-16",
        "brand": "ASUS",
        "name": "ASUS VivoBook 14 X1404VA Laptop (14 Inch | Intel Core i5 | 16 GB | Windows 11 | 512 GB SSD)",
        "category": "laptop",
        "price": 1200.0,
        "processor_name": "Intel Core i5",
        "processor_brand": "Intel",
        "ram_expandable": "Yes",
        "ram": "16 GB",
        "ram_type": "DDR4",
        "ghz": "3.5 GHz",
        "display_type": "IPS",
        "display": "14 Inch",
        "gpu": "Intel UHD",
        "gpu_brand": "Intel",
        "ssd": "512 GB",
        "hdd": None,
        "stock": 5,
        "battery_life": "8 hours",
    },
]


@dataclass
class FakeToolFunction:
    name: str
    arguments: str


@dataclass
class FakeToolCall:
    id: str
    type: str
    function: FakeToolFunction


@dataclass
class FakeMessage:
    content: str | None = None
    tool_calls: list[FakeToolCall] | None = None


@dataclass
class FakeChoice:
    message: FakeMessage
    finish_reason: str


@dataclass
class FakeResponse:
    id: str
    choices: list[FakeChoice]


class FakeChatCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self._counter = 0

    def create(self, model: str, messages, tools, tool_choice):  # noqa: ANN001
        self._counter += 1
        snapshot = json.loads(json.dumps(messages))
        self.calls.append(
            {
                "model": model,
                "messages": snapshot,
                "tools": tools,
                "tool_choice": tool_choice,
            }
        )

        last_user_index = max(index for index, item in enumerate(messages) if item["role"] == "user")
        current_user = messages[last_user_index]["content"]
        after_current_user = messages[last_user_index + 1 :]
        has_tool_after_current_user = any(item["role"] == "tool" for item in after_current_user)

        if current_user == "Tell me about ASUS VivoBook 14":
            if not has_tool_after_current_user:
                return FakeResponse(
                    id=f"resp-{self._counter}",
                    choices=[
                        FakeChoice(
                            message=FakeMessage(
                                content=None,
                                tool_calls=[
                                    FakeToolCall(
                                        id="call-1",
                                        type="function",
                                        function=FakeToolFunction(
                                            name="search_products",
                                            arguments=json.dumps(
                                                {"query": "ASUS VivoBook 14", "limit": 5}
                                            ),
                                        ),
                                    )
                                ],
                            ),
                            finish_reason="tool_calls",
                        )
                    ],
                )

            return FakeResponse(
                id=f"resp-{self._counter}",
                choices=[
                    FakeChoice(
                        message=FakeMessage(
                            content="ASUS VivoBook 14 is available in both 8 GB and 16 GB variants.",
                            tool_calls=None,
                        ),
                        finish_reason="stop",
                    )
                ],
            )

        if current_user == "What about the 8 GB version?":
            assert any(
                item["role"] == "user" and "Tell me about ASUS VivoBook 14" in item.get("content", "")
                for item in messages[:last_user_index]
            ), "previous conversation context was not passed to the LLM"

            if not has_tool_after_current_user:
                return FakeResponse(
                    id=f"resp-{self._counter}",
                    choices=[
                        FakeChoice(
                            message=FakeMessage(
                                content=None,
                                tool_calls=[
                                    FakeToolCall(
                                        id="call-2",
                                        type="function",
                                        function=FakeToolFunction(
                                            name="search_products",
                                            arguments=json.dumps(
                                                {"query": "ASUS VivoBook 14 8 GB", "limit": 5}
                                            ),
                                        ),
                                    )
                                ],
                            ),
                            finish_reason="tool_calls",
                        )
                    ],
                )

            return FakeResponse(
                id=f"resp-{self._counter}",
                choices=[
                    FakeChoice(
                        message=FakeMessage(
                            content="The 8 GB ASUS VivoBook 14 version is the one you discussed earlier.",
                            tool_calls=None,
                        ),
                        finish_reason="stop",
                    )
                ],
            )

        return FakeResponse(
            id=f"resp-{self._counter}",
            choices=[
                FakeChoice(
                    message=FakeMessage(content="Unsupported test prompt", tool_calls=None),
                    finish_reason="stop",
                )
            ],
        )


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.chat = type("ChatNamespace", (), {})()
        self.chat.completions = FakeChatCompletions()


@pytest.fixture()
def db_service(tmp_path: Path) -> DatabaseService:
    service = DatabaseService(tmp_path / "test.sqlite3")
    service.initialize()

    with service.connection() as connection:
        for product in TEST_PRODUCTS:
            connection.execute(
                """
                INSERT INTO products (
                    sku, brand, name, category, price, processor_name, processor_brand,
                    ram_expandable, ram, ram_type, ghz, display_type, display,
                    gpu, gpu_brand, ssd, hdd, stock, battery_life
                ) VALUES (
                    :sku, :brand, :name, :category, :price, :processor_name, :processor_brand,
                    :ram_expandable, :ram, :ram_type, :ghz, :display_type, :display,
                    :gpu, :gpu_brand, :ssd, :hdd, :stock, :battery_life
                )
                """,
                product,
            )
        connection.commit()

    return service


@pytest.fixture()
def product_service(db_service: DatabaseService) -> ProductService:
    return ProductService(database=db_service)


@pytest.fixture()
def conversation_store(db_service: DatabaseService) -> ConversationStore:
    return ConversationStore(database=db_service)


@pytest.fixture()
def fake_openai_client() -> FakeOpenAIClient:
    return FakeOpenAIClient()


@pytest.fixture()
def chatbot_orchestrator(
    product_service: ProductService,
    conversation_store: ConversationStore,
    fake_openai_client: FakeOpenAIClient,
) -> ChatbotOrchestrator:
    return ChatbotOrchestrator(
        product_service=product_service,
        conversation_store=conversation_store,
        client=fake_openai_client,  # type: ignore[arg-type]
        model="test-model",
        max_rounds=5,
        history_limit=10,
    )


@pytest.fixture()
def client(
    product_service: ProductService,
    conversation_store: ConversationStore,
    chatbot_orchestrator: ChatbotOrchestrator,
):
    app.dependency_overrides[get_product_service] = lambda: product_service
    app.dependency_overrides[get_conversation_store] = lambda: conversation_store
    app.dependency_overrides[get_chatbot_orchestrator] = lambda: chatbot_orchestrator

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
