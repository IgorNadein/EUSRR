from rest_framework import serializers


class NotificationActorSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()
    type = serializers.CharField(required=False, allow_null=True)


class NotificationItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    message = serializers.CharField()
    short_message = serializers.CharField()
    is_read = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    category = serializers.CharField()
    action_url = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    verb = serializers.CharField()
    description = serializers.CharField()
    actor = NotificationActorSerializer(required=False, allow_null=True)
    unread = serializers.BooleanField()
    public = serializers.BooleanField()
    deleted = serializers.BooleanField()
    emailed = serializers.BooleanField()
    timestamp = serializers.DateTimeField()
    timesince = serializers.CharField()


class NotificationsListResponseSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    unread_count = serializers.IntegerField()
    notifications = NotificationItemSerializer(many=True)


class CountResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()


class StatusResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField(required=False)
    notification_id = serializers.IntegerField(required=False)
    count = serializers.IntegerField(required=False)
    deleted_count = serializers.IntegerField(required=False)
    device_id = serializers.IntegerField(required=False)
    created = serializers.BooleanField(required=False)
    verbs = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )


class VerbTypeSerializer(serializers.Serializer):
    verb = serializers.CharField()
    name = serializers.CharField()
    total = serializers.IntegerField()
    unread = serializers.IntegerField()


class VerbTypesResponseSerializer(serializers.Serializer):
    verb_types = VerbTypeSerializer(many=True)


class MarkAllAsReadRequestSerializer(serializers.Serializer):
    verb = serializers.CharField(required=False)


class MarkCategoryAsReadRequestSerializer(serializers.Serializer):
    verbs = serializers.ListField(child=serializers.CharField())
    category = serializers.CharField(required=False)


class ChannelPreferencesSerializer(serializers.Serializer):
    web_enabled = serializers.BooleanField()
    email_enabled = serializers.BooleanField()
    email_frequency = serializers.CharField()
    push_enabled = serializers.BooleanField()
    dnd_enabled = serializers.BooleanField()
    dnd_start_time = serializers.CharField(required=False, allow_null=True)
    dnd_end_time = serializers.CharField(required=False, allow_null=True)
    disabled_verbs = serializers.ListField(child=serializers.CharField())


class UpdateChannelPreferencesSerializer(serializers.Serializer):
    web_enabled = serializers.BooleanField(required=False)
    email_enabled = serializers.BooleanField(required=False)
    email_frequency = serializers.CharField(required=False)
    push_enabled = serializers.BooleanField(required=False)
    dnd_enabled = serializers.BooleanField(required=False)
    dnd_start_time = serializers.CharField(required=False, allow_null=True)
    dnd_end_time = serializers.CharField(required=False, allow_null=True)
    disabled_verbs = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )


class VapidPublicKeyResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField(required=False)
    vapid_public_key = serializers.CharField(required=False, allow_null=True)


class PushKeysSerializer(serializers.Serializer):
    p256dh = serializers.CharField()
    auth = serializers.CharField()


class SubscribePushRequestSerializer(serializers.Serializer):
    endpoint = serializers.CharField()
    keys = PushKeysSerializer()
    device_name = serializers.CharField(required=False)


class UnsubscribePushRequestSerializer(serializers.Serializer):
    endpoint = serializers.CharField(required=False)
