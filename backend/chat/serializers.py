"""
Chat 应用序列化器层（Serializer Layer）。

类比 SpringBoot：
  - Django Serializer 类似于 Spring Boot 中的 DTO（Data Transfer Object）+ @Validated 校验注解。
  - ModelSerializer 相当于自动映射 Entity -> JSON 的工具（类似 MapStruct 或 ModelMapper）。
  - Serializer（非 Model）相当于 @RequestBody 的请求体校验 DTO。
  - fields / read_only_fields 类比 @JsonProperty 的读写控制。
  - Meta 内部类相当于 DTO 的字段映射配置。

本模块定义了聊天系统中所有请求/响应的数据结构：
  - CreateChatSessionSerializer：创建会话请求体校验。
  - ChatSessionSerializer：会话基本信息序列化。
  - ChatSessionListSerializer：会话列表序列化（含最后一条消息预览）。
  - ChatMessageSerializer：消息序列化。
  - ChatSessionDetailSerializer：会话详情序列化（含消息列表）。
  - MemoryItemSerializer：记忆条目序列化。
  - MemoryEvidenceSerializer：记忆证据序列化。
  - MemoryPinSerializer：记忆置顶请求体校验。
"""

from rest_framework import serializers

from chat.models import ChatMessage, ChatSession, MemoryEvidence, MemoryItem


class CreateChatSessionSerializer(serializers.Serializer):
    """
    创建会话的请求体序列化器。

    类比 SpringBoot：
      - 相当于 @RequestBody 的 DTO 类，用于校验 POST /sessions 的请求参数。

    字段：
      - title: 会话标题（可选，最大 255 字符）。
      - context_filters: 上下文过滤器（可选，dict 类型，如 {"dataset_id": 1}）。
    """
    title = serializers.CharField(required=False, allow_blank=True, max_length=255)
    context_filters = serializers.DictField(required=False, default=dict)


class ChatSessionSerializer(serializers.ModelSerializer):
    """
    会话基本信息序列化器。

    类比 SpringBoot：
      - 相当于 Entity -> DTO 的自动映射器（MapStruct Mapper），
        将 ChatSession Model 转换为 JSON 输出。

    额外字段：
      - user_id: 从 user.id 提取的用户 ID。
      - session_id: 从 id 提取的会话 ID（别名）。
    """
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    session_id = serializers.IntegerField(source="id", read_only=True)

    class Meta:
        model = ChatSession
        fields = [
            "id",
            "session_id",
            "user_id",
            "title",
            "title_status",
            "title_source",
            "rolling_summary",
            "message_count",
            "last_message_at",
            "context_filters",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "session_id",
            "user_id",
            "title_status",
            "title_source",
            "rolling_summary",
            "message_count",
            "last_message_at",
            "created_at",
            "updated_at",
        ]


class ChatSessionListSerializer(ChatSessionSerializer):
    """
    会话列表序列化器，继承 ChatSessionSerializer 并追加最后一条消息预览。

    类比 SpringBoot：
      - 相当于扩展基类 DTO，为列表视图增加额外字段。
      - 类似于在 JPQL 查询中使用 @Formula 或构造器表达式添加计算字段。

    额外字段：
      - last_message_preview: 会话最后一条消息的内容片段（用于列表预览）。
    """
    last_message_preview = serializers.CharField(read_only=True, default="")

    class Meta(ChatSessionSerializer.Meta):
        fields = ChatSessionSerializer.Meta.fields + ["last_message_preview"]


class ChatMessageSerializer(serializers.ModelSerializer):
    """
    聊天消息序列化器。

    类比 SpringBoot：
      - 相当于 ChatMessage Entity -> DTO 映射器，
        将消息记录序列化为 JSON 返回给前端。

    字段：
      - id: 主键。
      - sequence: 会话内消息序号。
      - role: 消息角色（user/assistant/system）。
      - message_type: 消息类型（目前仅 text）。
      - status: 消息状态（pending/complete/failed）。
      - citations_json: 引用列表 JSON。
      - model_metadata_json: 模型元数据 JSON。
      - client_message_id: 客户端消息 ID（用于去重）。
      - content: 消息正文。
      - created_at / updated_at: 时间戳。
    """
    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "sequence",
            "role",
            "message_type",
            "status",
            "citations_json",
            "model_metadata_json",
            "client_message_id",
            "content",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "sequence",
            "status",
            "citations_json",
            "model_metadata_json",
            "client_message_id",
            "created_at",
            "updated_at",
        ]


class ChatSessionDetailSerializer(ChatSessionSerializer):
    """
    会话详情序列化器，继承 ChatSessionSerializer 并追加消息列表。

    类比 SpringBoot：
      - 相当于包含嵌套集合的 DTO（如 @OneToMany 的 DTO 投影），
        用于 GET /sessions/{id} 返回完整会话及所有关联消息。

    额外字段：
      - messages: 该会话下的全部消息列表（包含 message_type / status / citations_json / model_metadata_json 等字段）。
    """
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta(ChatSessionSerializer.Meta):
        fields = ChatSessionSerializer.Meta.fields + ["messages"]


class MemoryItemSerializer(serializers.ModelSerializer):
    """
    记忆条目序列化器。

    类比 SpringBoot：
      - 相当于 MemoryItem Entity -> DTO 映射器，用于记忆列表/详情的 JSON 输出。

    字段：
      - id: 主键。
      - memory_type: 记忆类型（user_preference / project_background / confirmed_fact / work_rule）。
      - scope_type: 作用域类型（user_global / project / dataset）。
      - scope_key: 作用域键值（如 dataset_id）。
      - title: 记忆标题。
      - content: 记忆内容正文。
      - confidence_score: 置信度评分（0~1，float 格式）。
      - source_kind: 来源方式（auto / manual）。
      - status: 状态（active / archived / deleted）。
      - pinned: 是否置顶。
      - updated_at: 最后更新时间。
    """
    confidence_score = serializers.FloatField(read_only=True)

    class Meta:
        model = MemoryItem
        fields = [
            "id",
            "memory_type",
            "scope_type",
            "scope_key",
            "title",
            "content",
            "confidence_score",
            "source_kind",
            "status",
            "pinned",
            "updated_at",
        ]
        read_only_fields = fields


class MemoryEvidenceSerializer(serializers.ModelSerializer):
    """
    记忆证据序列化器。

    类比 SpringBoot：
      - 相当于 MemoryEvidence Entity -> DTO 映射器，
        用于 GET /memories/{id}/evidence 返回证据链的 JSON 输出。

    额外字段：
      - session_id: 来源会话 ID（可为空）。
      - message_id: 来源消息 ID（可为空）。

    其他字段：
      - id: 主键。
      - evidence_excerpt: 证据摘要（截取自原文的关键片段）。
      - extractor_version: 提取器版本标识。
      - confirmation_status: 确认状态（pending / confirmed / rejected）。
      - created_at: 创建时间。
    """
    session_id = serializers.IntegerField(allow_null=True, read_only=True)
    message_id = serializers.IntegerField(allow_null=True, read_only=True)

    class Meta:
        model = MemoryEvidence
        fields = [
            "id",
            "session_id",
            "message_id",
            "evidence_excerpt",
            "extractor_version",
            "confirmation_status",
            "created_at",
        ]
        read_only_fields = fields


class MemoryPinSerializer(serializers.Serializer):
    """
    记忆置顶操作请求体序列化器。

    类比 SpringBoot：
      - 相当于 @RequestBody 的 DTO，用于校验 POST /memories/{id}/pin 的请求参数。

    字段：
      - pinned: bool，True 表示置顶，False 表示取消置顶。
    """
    pinned = serializers.BooleanField()
