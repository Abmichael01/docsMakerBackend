from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from dj_rest_auth.serializers import UserDetailsSerializer
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str

User = get_user_model()


ROLE_CODES = {
    "admin": "ZK7T-93XY",
    "user": "LQ5D-21VM",
}

class CustomUserDetailsSerializer(UserDetailsSerializer):
    role = serializers.SerializerMethodField()
    wallet_balance = serializers.SerializerMethodField()
    total_purchases = serializers.SerializerMethodField()
    downloads = serializers.SerializerMethodField()

    class Meta(UserDetailsSerializer.Meta):
        fields = UserDetailsSerializer.Meta.fields + ( 
            "email",
            "role",
            "wallet_balance",
            "total_purchases",
            "downloads",
        )

    def get_role(self, user):
        if user.is_superuser:
            return ROLE_CODES["admin"]
        return ROLE_CODES["user"]

    def get_wallet_balance(self, user):
        return getattr(user.wallet, "balance", 0)

    def get_total_purchases(self, user):
        return user.purchased_templates.count()

    def get_downloads(self, user):
        return user.downloads


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=6,
        style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"}
    )

    def validate(self, data): # type: ignore
        username = data.get("username")
        password = data.get("password")

        if username and password:
            user = authenticate(request=self.context.get("request"), username=username, password=password)
            if not user:
                raise serializers.ValidationError({"error": ("Invalid credentials")})
        else:
            raise serializers.ValidationError({"error": ("Both username and password are required")})

        data["user"] = user
        return data


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is not registered, please try again.")
        return value

class ResetPasswordConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=6)

    def validate(self, attrs):
        try:
            uid = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError):
            raise serializers.ValidationError("Invalid user")

        if not PasswordResetTokenGenerator().check_token(user, attrs["token"]):
            raise serializers.ValidationError("Invalid or expired token")

        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        password = self.validated_data["password"]
        user.set_password(password)
        user.save()
        return user
    
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate(self, attrs):
        user = self.context['request'].user
        if not user.check_password(attrs['old_password']):
            raise serializers.ValidationError("Old password is incorrect.")
        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError("New password must be different.")
        return attrs
