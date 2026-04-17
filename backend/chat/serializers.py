from rest_framework import serializers

from chat.models import ChatMessage, ChatSession


class CreateChatSessionSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True, max_length=255)
    context_filters = serializers.DictField(required=False, default=dict)


class ChatSessionSerializer(serializers.ModelSerializer):
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
    last_message_preview = serializers.CharField(read_only=True, default="")

    class Meta(ChatSessionSerializer.Meta):
        fields = ChatSessionSerializer.Meta.fields + ["last_message_preview"]


class ChatMessageSerializer(serializers.ModelSerializer):
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
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta(ChatSessionSerializer.Meta):
        fields = ChatSessionSerializer.Meta.fields + ["messages"]
