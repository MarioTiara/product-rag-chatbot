from openai import OpenAI

from app.agents.ai.openai_adapter import OpenAIAdapter
from app.core.configs import config
from app.agents.ai.ai_client import AIClient



class AIClientFactory:

    @staticmethod
    def create() -> AIClient:
        settings = config.get_settings()

        provider = settings.ai_provider.lower()

        if provider == "openai":
            client = OpenAI(
                api_key=settings.openai_api_key.get_secret_value(),
            )

            return OpenAIAdapter(
                client=client,
                model=settings.openai_model,
            )

        raise ValueError(
            f"Unsupported AI provider: {provider}"
        )