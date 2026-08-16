from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Payment, Prediction, Profile


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=40)
    password = serializers.CharField(min_length=6, write_only=True)
    referral = serializers.CharField(max_length=40, required=False, allow_blank=True)

    def validate_email(self, value):
        email = value.lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return email

    def create(self, validated):
        user = User.objects.create_user(
            username=validated['email'],
            email=validated['email'],
            password=validated['password'],
            first_name=validated['name'][:150],
        )
        Profile.objects.create(
            user=user,
            phone=validated['phone'],
            referral=validated.get('referral') or '',
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            'id', 'kind', 'country', 'amount', 'transaction_id', 'sender_name',
            'paid_from', 'screenshot', 'status', 'admin_note', 'created_at',
        )
        read_only_fields = ('id', 'status', 'admin_note', 'created_at', 'amount')


class PredictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prediction
        fields = ('id', 'game', 'cost', 'payload', 'created_at')
