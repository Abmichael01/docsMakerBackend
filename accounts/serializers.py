from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from dj_rest_auth.serializers import UserDetailsSerializer

User = get_user_model()


ROLE_CODES = {
    "admin": "ZK7T-93XY",
    "user": "LQ5D-21VM",
}

class CustomUserDetailsSerializer(UserDetailsSerializer):
    role = serializers.SerializerMethodField()

    class Meta(UserDetailsSerializer.Meta):
        fields = UserDetailsSerializer.Meta.fields + ("role",)

    def get_role(self, user):
        if user.is_superuser:
            return ROLE_CODES["admin"]
        return ROLE_CODES["user"]

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

