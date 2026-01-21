"""LLM provider configuration and factory."""

from typing import Literal

from langchain_core.language_models import BaseChatModel

from src.config.settings import Settings


def get_llm(
    settings: Settings,
    provider: Literal["anthropic", "openai", "ollama"] | None = None,
) -> BaseChatModel:
    """Get LLM instance based on provider configuration.

    Args:
        settings: Application settings
        provider: Override provider from settings

    Returns:
        Configured LLM instance
    """
    provider = provider or settings.llm_provider

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            streaming=True,
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            streaming=True,
        )
    elif provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model="llama3.1",
            streaming=True,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
