"""DRF request serializers for OPS definition item writes."""

from rest_framework import serializers


class DefinitionItemWriteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=120)
    label = serializers.CharField(max_length=240)
    meta = serializers.DictField(required=False, default=dict)
    sortOrder = serializers.IntegerField(required=False, min_value=0, default=100)
    isActive = serializers.BooleanField(required=False, default=True)
    parentIds = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True, default=list
    )


class DefinitionItemPatchSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=120, required=False)
    label = serializers.CharField(max_length=240, required=False)
    meta = serializers.DictField(required=False)
    sortOrder = serializers.IntegerField(required=False, min_value=0)
    isActive = serializers.BooleanField(required=False)
    parentIds = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True
    )
