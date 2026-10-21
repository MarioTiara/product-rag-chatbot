
from functools import lru_cache

from app.ai.chatbot_service import ChatbotOrchestrator
from app.configs import config
from app.services.conversation_store import ConversationStore
from app.services.product_service import ProductService
from app.database.connection import DatabaseConnection
from app.database.repositories.product_repository import ProductRepository

@lru_cache(maxsize=1)
def get_product_service() -> ProductService:
    settings= config.get_settings()
    db= DatabaseConnection(settings.database_path)
    repository=ProductRepository(db)
    return ProductService(repository)


@lru_cache(maxsize=1)
def get_conversation_store() -> ConversationStore:
    return ConversationStore()


@lru_cache(maxsize=1)
def get_chatbot_orchestrator() -> ChatbotOrchestrator:
    return ChatbotOrchestrator(
        product_service=get_product_service(),
        conversation_store=get_conversation_store(),
    )
