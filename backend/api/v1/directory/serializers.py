"""Serializers для directory API."""

from rest_framework import serializers


class DirectoryLoginResponseSerializer(serializers.Serializer):
    username = serializers.CharField(allow_blank=True, allow_null=True)
    source = serializers.ChoiceField(
        choices=("db", "ldap", "none", "ldap_not_found")
    )
    is_cached = serializers.BooleanField()
    is_ldap_managed = serializers.BooleanField()

