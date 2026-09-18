from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Protocol

from openai import AsyncOpenAI

from app.core.config import settings
from app.services.embedding import get_openai_client

Message = dict[str, str]


class ChatModel(Protocol):
    async def complete(self, messages: list[Message]) -> str: ...
    def stream(self, messages: list[Message]) -> AsyncIterator[str]: ...


class OpenAIChatModel:
    def __init__(self, client: AsyncOpenAI, model: str, temperature: float, max_tokens: int) -> None:
        self.client = client
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def complete(self, messages: list[Message]) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return (response.choices[0].message.content or "").strip()

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        async with stream:
            async for event in stream:
                if event.choices and event.choices[0].delta.content:
                    yield event.choices[0].delta.content


@lru_cache
def get_chat_model() -> ChatModel:
    return OpenAIChatModel(
        get_openai_client(),
        model=settings.OPENAI_CHAT_MODEL,
        temperature=settings.RAG_TEMPERATURE,
        max_tokens=settings.RAG_MAX_OUTPUT_TOKENS,
    )
