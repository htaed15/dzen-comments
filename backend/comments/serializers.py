import os

from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.db import transaction
from rest_framework import serializers

from .models import Attachment, Author, Comment
from .services.attachments import AttachmentError, AttachmentValidator
from .services.captcha import CaptchaService
from .services.sanitizer import HtmlSanitizer, HtmlValidationError

USERNAME_VALIDATOR = RegexValidator(r"^[A-Za-z0-9]+$", "Только латинские буквы и цифры")
MAX_TEXT_LENGTH = 5000
PASSWORD_MIN_LENGTH = 6


def sanitize_text(value: str) -> str:
    try:
        cleaned = HtmlSanitizer().clean(value)
    except HtmlValidationError as exc:
        raise serializers.ValidationError(str(exc))
    if not cleaned:
        raise serializers.ValidationError("Сообщение не может быть пустым")
    return cleaned


# ---------- чтение ----------


class AttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ["id", "url", "name", "kind", "status"]

    def get_url(self, obj):
        return obj.file.url

    def get_name(self, obj):
        return os.path.basename(obj.file.name)


class CommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="author.user_name")
    email = serializers.CharField(source="author.email")
    home_page = serializers.CharField(source="author.home_page")
    attachments = AttachmentSerializer(many=True, read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id", "parent", "user_name", "email", "home_page",
            "text", "created_at", "attachments", "replies",
        ]

    def get_replies(self, obj):
        # children заполняется в views.build_tree (без запросов в цикле)
        return CommentSerializer(getattr(obj, "children", []), many=True).data


# ---------- запись ----------


class PreviewSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=MAX_TEXT_LENGTH)

    def validate_text(self, value):
        return sanitize_text(value)


class CommentCreateSerializer(serializers.Serializer):
    user_name = serializers.CharField(max_length=50, required=False, validators=[USERNAME_VALIDATOR])
    email = serializers.EmailField(required=False)
    home_page = serializers.URLField(required=False, allow_blank=True)
    text = serializers.CharField(max_length=MAX_TEXT_LENGTH)
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Comment.objects.all(), required=False, allow_null=True
    )
    captcha_key = serializers.CharField(required=False, allow_blank=True)
    captcha_answer = serializers.CharField(required=False, allow_blank=True)
    file = serializers.FileField(required=False)

    def validate_text(self, value):
        return sanitize_text(value)

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user if request.user.is_authenticated else None

        if user:
            attrs.setdefault("user_name", user.username)
            attrs.setdefault("email", user.email or f"{user.username}@users.local")
        else:
            errors = {}
            for field in ("user_name", "email"):
                if not attrs.get(field):
                    errors[field] = "Обязательное поле"
            if not CaptchaService().verify(attrs.get("captcha_key", ""), attrs.get("captcha_answer", "")):
                errors["captcha_answer"] = "Неверная CAPTCHA"
            if errors:
                raise serializers.ValidationError(errors)

        uploaded = attrs.get("file")
        if uploaded:
            try:
                attrs["kind"] = AttachmentValidator().validate(uploaded)
            except AttachmentError as exc:
                raise serializers.ValidationError({"file": str(exc)})
        return attrs

    @transaction.atomic
    def create(self, validated):
        request = self.context["request"]
        user = request.user if request.user.is_authenticated else None

        author, _ = Author.objects.get_or_create(
            user=user,
            user_name=validated["user_name"],
            email=validated["email"],
            home_page=validated.get("home_page", ""),
            ip_address=self.context["ip"],
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        )
        parent = validated.get("parent")
        comment = Comment.objects.create(
            author=author,
            parent=parent,
            root=(parent.root or parent) if parent else None,
            text=validated["text"],
        )
        if validated.get("file"):
            Attachment.objects.create(comment=comment, file=validated["file"], kind=validated["kind"])
        return comment


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=30, validators=[USERNAME_VALIDATOR])
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        min_length=PASSWORD_MIN_LENGTH,
        error_messages={"min_length": f"Пароль должен быть не короче {PASSWORD_MIN_LENGTH} символов"},
    )

    def validate_username(self, value):
        if get_user_model().objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Это имя уже занято")
        return value

    def validate_password(self, value):
        if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
            raise serializers.ValidationError("Пароль должен содержать и буквы, и цифры")
        return value

    def create(self, validated):
        return get_user_model().objects.create_user(**validated)
