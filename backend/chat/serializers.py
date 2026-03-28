from rest_framework import serializers

from chat.models import ChatMessage, ChatSession


class CreateChatSessionSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True, max_length=255)
    context_filters = serializers.DictField(required=False, default=dict)


class ChatSessionSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        model = ChatSession
        fields = [
            "id",
            "user_id",
            "title",
            "context_filters",
            "created_at",
            "updated_at",
        ]


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "sequence",
            "role",
            "message_type",
            "content",
            "created_at",
            "updated_at",
        ]


class ChatSessionDetailSerializer(ChatSessionSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta(ChatSessionSerializer.Meta):
        fields = ChatSessionSerializer.Meta.fields + ["messages"]
