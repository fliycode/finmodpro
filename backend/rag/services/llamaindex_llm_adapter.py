from collections.abc import Sequence

from pydantic import ConfigDict, Field

from llama_index.core.llms import (
    ChatMessage,
    ChatResponse,
    ChatResponseGen,
    CompletionResponse,
    CompletionResponseGen,
    CustomLLM,
    LLMMetadata,
)


class FinModProLLMAdapter(CustomLLM):
    """LlamaIndex LLM adapter wrapping the project's chat provider."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    provider: object | None = Field(default=None, exclude=True)
    model_name: str = "finmodpro-llm"

    @classmethod
    def class_name(cls) -> str:
        return "finmodpro_llm"

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            model_name=self.model_name,
            context_window=4096,
            num_output=1024,
            is_chat_model=True,
        )

    def _get_provider(self):
        provider = self.provider
        if provider is None:
            from llm.services.runtime_service import get_chat_provider

            provider = get_chat_provider()
            object.__setattr__(self, "provider", provider)
        return provider

    def _call_chat(self, messages: list[dict]) -> str:
        result = self._get_provider().chat(messages=messages)
        return result.content

    def complete(self, prompt: str, **kwargs) -> CompletionResponse:
        text = self._call_chat([{"role": "user", "content": prompt}])
        return CompletionResponse(text=text)

    def stream_complete(self, prompt: str, **kwargs) -> CompletionResponseGen:
        text = self.complete(prompt).text
        yield CompletionResponse(text=text, delta="")

    def chat(self, messages: Sequence[ChatMessage], **kwargs) -> ChatResponse:
        api_messages = [{"role": m.role.value, "content": m.content} for m in messages]
        text = self._call_chat(api_messages)
        return ChatResponse(message=ChatMessage(role="assistant", content=text))

    def stream_chat(self, messages: Sequence[ChatMessage], **kwargs) -> ChatResponseGen:
        response = self.chat(messages, **kwargs)
        yield response

    async def acomplete(self, prompt: str, **kwargs) -> CompletionResponse:
        return self.complete(prompt, **kwargs)

    async def astream_complete(self, prompt: str, **kwargs) -> CompletionResponseGen:
        for chunk in self.stream_complete(prompt, **kwargs):
            yield chunk

    async def achat(self, messages: Sequence[ChatMessage], **kwargs) -> ChatResponse:
        return self.chat(messages, **kwargs)

    async def astream_chat(self, messages: Sequence[ChatMessage], **kwargs) -> ChatResponseGen:
        for chunk in self.stream_chat(messages, **kwargs):
            yield chunk
