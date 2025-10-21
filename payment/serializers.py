from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "reference", "amount", "status", "created_at", "updated_at"]


class PaymentVerificationSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=100)

    def validate_reference(self, value):
        """
        Validate that the reference is in the correct format.
        """
        if not value:
            raise serializers.ValidationError("Reference is required")
        return value


from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "reference", "amount", "status", "created_at", "updated_at"]


class PaymentVerificationSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=100)

    def validate_reference(self, value):
        """
        Validate that the reference is in the correct format.
        """
        if not value:
            raise serializers.ValidationError("Reference is required")
        return value
