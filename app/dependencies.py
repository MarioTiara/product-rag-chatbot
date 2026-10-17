
from functools import lru_cache

from app.conversation_store import ConversationStore
from app.chatbot import ChatbotOrchestrator
from app.product_service import ProductService


@lru_cache(maxsize=1)
def get_product_service() -> ProductService:
    return ProductService()


@lru_cache(maxsize=1)
def get_conversation_store() -> ConversationStore:
    return ConversationStore()


@lru_cache(maxsize=1)
def get_chatbot_orchestrator() -> ChatbotOrchestrator:
    return ChatbotOrchestrator(
        product_service=get_product_service(),
        conversation_store=get_conversation_store(),
    )
