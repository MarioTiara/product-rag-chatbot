
from functools import lru_cache

from app.chatbot import ChatbotOrchestrator
from app.product_service import ProductService


@lru_cache(maxsize=1)
def get_product_service() -> ProductService:
    return ProductService()


@lru_cache(maxsize=1)
def get_chatbot_orchestrator() -> ChatbotOrchestrator:
    return ChatbotOrchestrator(product_service=get_product_service())
