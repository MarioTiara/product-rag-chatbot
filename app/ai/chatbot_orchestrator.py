
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from openai import AuthenticationError, OpenAI

from app.ai.ai_client import AIClient, OpenAIAdapter
from app.ai.answer_formatter import AnswerFormatter
from app.ai.exceptions import ChatProviderAuthenticationError
from app.ai.message_mapper import MessageMapper
from app.ai.product_chat_agent import ProductChatAgent
from app.configs.config import get_settings
from app.services.conversation_service import ConversationService
from app.services.product_service import ProductService


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a helpful frontline customer service assistant for a store. "
    "Respond naturally and professionally in the user's language. "
    "Use the provided tools for factual product information, including "
    "product details, prices, stock availability, and product searches. "
    "Never invent product data, prices, or stock quantities. "
    "Use get_product_details when the exact product name is known. "
    "Use search_products when finding products by keywords, specifications, "
    "brand, price range, or other filters. "
    "Use check_product_availability to check whether a specific product "
    "is in stock. A product not found is different from a product with "
    "zero stock. "
    "Use get_total_stock for aggregate stock quantity questions. "
    "For minimum RAM requirements, use min_ram. "
    "For Intel Core i7, use processor_brand='Intel' and "
    "processor_name='Intel Core i7'. "
    "For cheapest products, use sort_by='price' and sort_order='asc'. "
    "For most expensive products, use sort_by='price' and "
    "sort_order='desc'. "
    "Only claim that no products match when tool results support "
    "that conclusion. "
    "Use previous conversation messages to understand follow-up questions, "
    "but always use tools to verify current product information. "
    "Do not claim that an order has been placed or a purchase completed "
    "unless a corresponding tool explicitly confirms that action."
)


@dataclass(slots=True)
class ChatbotResult:
    conversation_id: str
    answer: str
    tool_calls: list[str]
    user_message_id: str
    assistant_message_id: str
    channel_conversation_id: int | None = None


class ChatbotOrchestrator:
    """Coordinate provider setup, conversation history, and final answers."""

    def __init__(
        self,
        product_service: ProductService | None = None,
        conversation_service: ConversationService | None = None,
        conversation_store: ConversationService | None = None,
        agent: ProductChatAgent | None = None,
        ai_client: AIClient | None = None,
        client: OpenAI | None = None,
        model: str | None = None,
        max_rounds: int = 5,
        history_limit: int | None = None,
        message_mapper: MessageMapper | None = None,
        answer_formatter: AnswerFormatter | None = None,
    ) -> None:
        settings = get_settings()

        if max_rounds < 1:
            raise ValueError("max_rounds must be at least 1")

        self.history_limit = (
            history_limit
            if history_limit is not None
            else settings.chat_history_limit
        )

        if self.history_limit < 1:
            raise ValueError("history_limit must be at least 1")

        self.product_service = product_service or ProductService()

        self.conversation_service = (
            conversation_service
            or conversation_store
            or ConversationService(
                history_limit=self.history_limit
            )
        )

        self.message_mapper = message_mapper or MessageMapper()
        self.answer_formatter = answer_formatter or AnswerFormatter()

        self.model = model or settings.openai_model

        if agent is not None:
            self.agent = agent
        else:
            if ai_client is None:
                provider_client = client or OpenAI(
                    api_key=settings.openai_api_key.get_secret_value()
                )
                ai_client = OpenAIAdapter(
                    client=provider_client,
                    model=self.model,
                )

            self.agent = ProductChatAgent(
                ai_client=ai_client,
                product_service=self.product_service,
                conversation_service=self.conversation_service,
                max_rounds=max_rounds,
            )

    def chat(
        self,
        message: str,
        conversation_id: str | None = None,
        *,
        user_id: str | None = None,
        channel: str | None = None,
        channel_chat_id: str | None = None,
        channel_thread_id: str = "",
        channel_user_id: str | None = None,
        channel_message_id: str | None = None,
    ) -> ChatbotResult:
        message = message.strip()

        if not message:
            raise ValueError("Message cannot be empty")

        context = self.conversation_service.prepare_message(
            message=message,
            conversation_id=conversation_id,
            user_id=user_id,
            channel=channel,
            channel_chat_id=channel_chat_id,
            channel_thread_id=channel_thread_id,
            channel_user_id=channel_user_id,
            channel_message_id=channel_message_id,
        )

        active_conversation_id = context["conversation_id"]
        user_message_id = context["user_message_id"]
        channel_conversation_id = context.get(
            "channel_conversation_id"
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self.message_mapper.records_to_openai_messages(
                context["history"]
            ),
            {"role": "user", "content": message},
        ]

        logger.info(
            "chat.start conversation_id=%s channel=%s "
            "history_items=%s model=%s",
            active_conversation_id,
            channel,
            len(context["history"]),
            self.model,
        )

        try:
            agent_result = self.agent.generate(
                messages,
                conversation_id=active_conversation_id,
            )
        except AuthenticationError as exc:
            logger.error(
                "chat.provider_authentication_failed "
                "conversation_id=%s model=%s",
                active_conversation_id,
                self.model,
            )
            raise ChatProviderAuthenticationError(
                "AI provider authentication failed. "
                "Check the configured provider credentials."
            ) from exc
        except Exception:
            logger.exception(
                "chat.generation_failed conversation_id=%s",
                active_conversation_id,
            )
            raise

        final_answer = agent_result.answer

        if agent_result.last_search_result is not None:
            final_answer = self.answer_formatter.finalize_search_answer(
                final_answer,
                agent_result.last_search_result,
            )

        saved_assistant_message = (
            self.conversation_service.save_assistant_message(
                conversation_id=active_conversation_id,
                content=final_answer,
            )
        )

        logger.info(
            "chat.completed conversation_id=%s tool_calls=%s",
            active_conversation_id,
            agent_result.tool_calls,
        )

        return ChatbotResult(
            conversation_id=active_conversation_id,
            answer=final_answer,
            tool_calls=agent_result.tool_calls,
            user_message_id=user_message_id,
            assistant_message_id=saved_assistant_message["id"],
            channel_conversation_id=channel_conversation_id,
        )
