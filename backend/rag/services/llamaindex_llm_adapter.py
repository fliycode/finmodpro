"""
LlamaIndex LLM 适配器 —— 将项目自定义的 Chat Provider 封装为 LlamaIndex 兼容的 LLM 模型。
类比 SpringBoot: 相当于适配器模式中的 Adapter，将项目内置的 Chat API 封装为
LlamaIndex 框架要求的 CustomLLM 接口，支持同步和异步的 complete/chat 调用。
"""

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
    """
    LlamaIndex LLM 适配器，包装项目内置的 chat provider。

    类比 SpringBoot: 相当于一个 @Service Bean 实现了 LlamaIndex 的 LLM 接口，
    内部委托给 llm.services.runtime_service.get_chat_provider() 获取的实例。

    属性:
        provider: chat provider 实例，延迟加载。
        model_name (str): 模型名称标识。
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    provider: object | None = Field(default=None, exclude=True)
    model_name: str = "finmodpro-llm"

    @classmethod
    def class_name(cls) -> str:
        """返回 LlamaIndex 中使用的类名标识。"""
        return "finmodpro_llm"

    @property
    def metadata(self) -> LLMMetadata:
        """
        返回 LLM 的元数据信息。

        返回:
            LLMMetadata: 包含模型名称、上下文窗口大小 (4096)、
                         最大输出 token 数 (1024) 和是否聊天模型的标识。
        """
        return LLMMetadata(
            model_name=self.model_name,
            context_window=4096,
            num_output=1024,
            is_chat_model=True,
        )

    def _get_provider(self):
        """
        获取并缓存 chat provider 实例（惰性加载）。

        返回:
            object: chat provider 实例，支持 chat(messages) 方法。
        """
        provider = self.provider
        if provider is None:
            from llm.services.runtime_service import get_chat_provider

            provider = get_chat_provider()
            object.__setattr__(self, "provider", provider)
        return provider

    def _call_chat(self, messages: list[dict]) -> str:
        """
        调用 chat provider 并返回生成的文本内容。

        参数:
            messages (list[dict]): 消息列表，每个元素包含 role 和 content 字段。

        返回:
            str: LLM 生成的回复文本。
        """
        result = self._get_provider().chat(messages=messages)
        return result.content

    def complete(self, prompt: str, **kwargs) -> CompletionResponse:
        """
        同步补全接口 —— 给定提示词，返回 LLM 生成的补全文本。

        参数:
            prompt (str): 提示词文本。
            **kwargs: 其他可选参数。

        返回:
            CompletionResponse: 包含生成文本的补全响应。
        """
        text = self._call_chat([{"role": "user", "content": prompt}])
        return CompletionResponse(text=text)

    def stream_complete(self, prompt: str, **kwargs) -> CompletionResponseGen:
        """
        流式补全接口 —— 以生成器方式逐步返回补全结果。

        参数:
            prompt (str): 提示词文本。
            **kwargs: 其他可选参数。

        返回:
            CompletionResponseGen: 补全响应的生成器（逐 token 产出）。
        """
        text = self.complete(prompt).text
        yield CompletionResponse(text=text, delta="")

    def chat(self, messages: Sequence[ChatMessage], **kwargs) -> ChatResponse:
        """
        同步聊天接口 —— 给定对话历史，返回 LLM 的聊天响应。

        参数:
            messages (Sequence[ChatMessage]): LlamaIndex ChatMessage 序列。
            **kwargs: 其他可选参数。

        返回:
            ChatResponse: 包含助手消息的聊天响应。
        """
        api_messages = [{"role": m.role.value, "content": m.content} for m in messages]
        text = self._call_chat(api_messages)
        return ChatResponse(message=ChatMessage(role="assistant", content=text))

    def stream_chat(self, messages: Sequence[ChatMessage], **kwargs) -> ChatResponseGen:
        """
        流式聊天接口 —— 以生成器方式逐步返回聊天结果。

        参数:
            messages (Sequence[ChatMessage]): LlamaIndex ChatMessage 序列。
            **kwargs: 其他可选参数。

        返回:
            ChatResponseGen: 聊天响应的生成器。
        """
        response = self.chat(messages, **kwargs)
        yield response

    async def acomplete(self, prompt: str, **kwargs) -> CompletionResponse:
        """
        异步补全接口。

        参数:
            prompt (str): 提示词文本。
            **kwargs: 其他可选参数。

        返回:
            CompletionResponse: 包含生成文本的补全响应。
        """
        return self.complete(prompt, **kwargs)

    async def astream_complete(self, prompt: str, **kwargs) -> CompletionResponseGen:
        """
        异步流式补全接口。

        参数:
            prompt (str): 提示词文本。
            **kwargs: 其他可选参数。

        返回:
            CompletionResponseGen: 补全响应的异步生成器。
        """
        for chunk in self.stream_complete(prompt, **kwargs):
            yield chunk

    async def achat(self, messages: Sequence[ChatMessage], **kwargs) -> ChatResponse:
        """
        异步聊天接口。

        参数:
            messages (Sequence[ChatMessage]): LlamaIndex ChatMessage 序列。
            **kwargs: 其他可选参数。

        返回:
            ChatResponse: 包含助手消息的聊天响应。
        """
        return self.chat(messages, **kwargs)

    async def astream_chat(self, messages: Sequence[ChatMessage], **kwargs) -> ChatResponseGen:
        """
        异步流式聊天接口。

        参数:
            messages (Sequence[ChatMessage]): LlamaIndex ChatMessage 序列。
            **kwargs: 其他可选参数。

        返回:
            ChatResponseGen: 聊天响应的异步生成器。
        """
        for chunk in self.stream_chat(messages, **kwargs):
            yield chunk
