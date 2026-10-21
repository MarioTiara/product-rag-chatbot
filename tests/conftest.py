from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("PRICE_CONVERSION_RATE", "190")

import pytest
from fastapi.testclient import TestClient

from app.ai.chatbot_service import ChatbotOrchestrator
from app.api.dependencies import (
    get_chatbot_orchestrator,
    get_conversation_store,
    get_product_service,
)
from app.api.routers.chat import router as chat_router  # noqa: F401
from app.database.connection import DatabaseConnection
from app.database.repositories.conversation_repository import ConversationRepository
from app.database.repositories.product_repository import ProductRepository
from app.main import app
from app.services.conversation_store import ConversationStore
from app.services.product_service import ProductService


TEST_PRODUCTS = [
    {
        "id": "prod-asus-8",
        "product_id": "P-001",
        "brand": "ASUS",
        "model": "VivoBook 14",
        "product_code": "ASUS-VIVO-8",
        "name": "ASUS VivoBook 14 X1404VA Laptop (14 Inch | Intel Core i5 | 8 GB | Windows 11 | 512 GB SSD)",
        "os": "Windows 11",
        "price": 1000.0,
        "processor_name": "Intel Core i5",
        "processor_brand": "Intel",
        "ram_expandable": 1,
        "ram_gb": 8,
        "ram_type": "DDR4",
        "processor_ghz": 3.5,
        "display_type": "IPS",
        "display_inch": 14.0,
        "gpu": "Intel UHD",
        "gpu_brand": "Intel",
        "ssd_gb": 512,
        "hdd_gb": None,
        "stock": 3,
        "battery_life": "8 hours",
        "tags": "vivo,asus",
    },
    {
        "id": "prod-asus-16",
        "product_id": "P-002",
        "brand": "ASUS",
        "model": "VivoBook 14",
        "product_code": "ASUS-VIVO-16",
        "name": "ASUS VivoBook 14 X1404VA Laptop (14 Inch | Intel Core i5 | 16 GB | Windows 11 | 512 GB SSD)",
        "os": "Windows 11",
        "price": 1200.0,
        "processor_name": "Intel Core i5",
        "processor_brand": "Intel",
        "ram_expandable": 1,
        "ram_gb": 16,
        "ram_type": "DDR4",
        "processor_ghz": 3.5,
        "display_type": "IPS",
        "display_inch": 14.0,
        "gpu": "Intel UHD",
        "gpu_brand": "Intel",
        "ssd_gb": 512,
        "hdd_gb": None,
        "stock": 5,
        "battery_life": "8 hours",
        "tags": "vivo,asus",
    },
    {
        "id": "prod-i7-8",
        "product_id": "P-003",
        "brand": "Dell",
        "model": "Inspiron 14",
        "product_code": "DELL-I7-8",
        "name": "Dell Inspiron 14 Laptop (14 Inch | Intel Core i7 | 8 GB | Windows 11 | 512 GB SSD)",
        "os": "Windows 11",
        "price": 800.0,
        "processor_name": "Intel Core i7 (11th Gen)",
        "processor_brand": "Intel",
        "ram_expandable": 1,
        "ram_gb": 8,
        "ram_type": "DDR4",
        "processor_ghz": 4.2,
        "display_type": "IPS",
        "display_inch": 14.0,
        "gpu": "Intel Iris Xe",
        "gpu_brand": "Intel",
        "ssd_gb": 512,
        "hdd_gb": None,
        "stock": 4,
        "battery_life": "10 hours",
        "tags": "dell,inspiron",
    },
    {
        "id": "prod-i7-16",
        "product_id": "P-004",
        "brand": "Dell",
        "model": "Inspiron 14",
        "product_code": "DELL-I7-16",
        "name": "Dell Inspiron 14 Laptop (14 Inch | Intel Core i7 | 16 GB | Windows 11 | 512 GB SSD)",
        "os": "Windows 11",
        "price": 1000.0,
        "processor_name": "Intel Core i7 (11th Gen)",
        "processor_brand": "Intel",
        "ram_expandable": 1,
        "ram_gb": 16,
        "ram_type": "DDR4",
        "processor_ghz": 4.2,
        "display_type": "IPS",
        "display_inch": 14.0,
        "gpu": "Intel Iris Xe",
        "gpu_brand": "Intel",
        "ssd_gb": 512,
        "hdd_gb": None,
        "stock": 3,
        "battery_life": "10 hours",
        "tags": "dell,inspiron",
    },
    {
        "id": "prod-i9-16",
        "product_id": "P-005",
        "brand": "HP",
        "model": "Pavilion 14",
        "product_code": "HP-I9-16",
        "name": "HP Pavilion 14 Laptop (14 Inch | Intel Core i9 | 16 GB | Windows 11 | 1 TB SSD)",
        "os": "Windows 11",
        "price": 900.0,
        "processor_name": "Intel Core i9 (12th Gen)",
        "processor_brand": "Intel",
        "ram_expandable": 0,
        "ram_gb": 16,
        "ram_type": "DDR4",
        "processor_ghz": 4.8,
        "display_type": "IPS",
        "display_inch": 14.0,
        "gpu": "Intel Iris Xe",
        "gpu_brand": "Intel",
        "ssd_gb": 1024,
        "hdd_gb": None,
        "stock": 2,
        "battery_life": "9 hours",
        "tags": "hp,pavilion",
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
                                            arguments=json.dumps({"query": "ASUS VivoBook 14", "limit": 5}),
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
                                            arguments=json.dumps({"query": "ASUS VivoBook 14", "ram_gb": 8, "limit": 5}),
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

        if current_user == "Carikan saya pilihan laptop termurah dengan spesifikasi minimal Intel Core i7 dan RAM 16 GB.":
            if not has_tool_after_current_user:
                return FakeResponse(
                    id=f"resp-{self._counter}",
                    choices=[
                        FakeChoice(
                            message=FakeMessage(
                                content=None,
                                tool_calls=[
                                    FakeToolCall(
                                        id="call-cheapest-i7",
                                        type="function",
                                        function=FakeToolFunction(
                                            name="search_products",
                                            arguments=json.dumps(
                                                {
                                                    "processor_name": "Intel Core i7",
                                                    "processor_brand": "Intel",
                                                    "min_ram": 16,
                                                    "sort_by": "price",
                                                    "sort_order": "asc",
                                                    "limit": 5,
                                                }
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
                            content="Maaf, saat ini tidak tersedia produk yang cocok.",
                            tool_calls=None,
                        ),
                        finish_reason="stop",
                    )
                ],
            )

        if current_user == "Carikan laptop dengan Intel Core i7 dan RAM 64 GB.":
            if not has_tool_after_current_user:
                return FakeResponse(
                    id=f"resp-{self._counter}",
                    choices=[
                        FakeChoice(
                            message=FakeMessage(
                                content=None,
                                tool_calls=[
                                    FakeToolCall(
                                        id="call-empty-i7",
                                        type="function",
                                        function=FakeToolFunction(
                                            name="search_products",
                                            arguments=json.dumps(
                                                {
                                                    "processor_name": "Intel Core i7",
                                                    "processor_brand": "Intel",
                                                    "min_ram": 64,
                                                    "sort_by": "price",
                                                    "sort_order": "asc",
                                                    "limit": 5,
                                                }
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
                            content="Maaf, saat ini tidak tersedia produk yang cocok.",
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


def _create_schema(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            product_id TEXT,
            brand TEXT NOT NULL,
            model TEXT,
            product_code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            os TEXT,
            price REAL,
            processor_name TEXT,
            processor_brand TEXT,
            ram_expandable INTEGER NOT NULL DEFAULT 0,
            ram_gb INTEGER,
            ram_type TEXT,
            processor_ghz REAL,
            display_type TEXT,
            display_inch REAL,
            gpu TEXT,
            gpu_brand TEXT,
            ssd_gb INTEGER,
            hdd_gb INTEGER,
            stock INTEGER NOT NULL DEFAULT 0,
            battery_life TEXT,
            tags TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            tool_calls_json TEXT,
            tool_call_id TEXT,
            tool_name TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
        """
    )


@pytest.fixture()
def db_service(tmp_path: Path) -> DatabaseConnection:
    db = DatabaseConnection(tmp_path / "test.sqlite3")
    with db.connect() as connection:
        _create_schema(connection)
        for product in TEST_PRODUCTS:
            connection.execute(
                """
                INSERT INTO products (
                    id, product_id, brand, model, product_code, name, os, price,
                    processor_name, processor_brand, ram_expandable, ram_gb,
                    ram_type, processor_ghz, display_type, display_inch, gpu,
                    gpu_brand, ssd_gb, hdd_gb, stock, battery_life, tags
                ) VALUES (
                    :id, :product_id, :brand, :model, :product_code, :name, :os, :price,
                    :processor_name, :processor_brand, :ram_expandable, :ram_gb,
                    :ram_type, :processor_ghz, :display_type, :display_inch, :gpu,
                    :gpu_brand, :ssd_gb, :hdd_gb, :stock, :battery_life, :tags
                )
                """,
                product,
            )
    return db


@pytest.fixture()
def product_service(db_service: DatabaseConnection) -> ProductService:
    return ProductService(ProductRepository(db_service))


@pytest.fixture()
def conversation_store(db_service: DatabaseConnection) -> ConversationStore:
    return ConversationStore(ConversationRepository(db_service))


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
