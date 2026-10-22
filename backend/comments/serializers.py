import os

from django.core.validators import RegexValidator
from django.db import transaction
from rest_framework import serializers

from .models import Attachment, Comment, Profile
from .services.attachments import AttachmentError, AttachmentValidator
from .services.captcha import CaptchaService
from .services.identity import IdentityError, IdentityService
from .services.sanitizer import HtmlSanitizer, HtmlValidationError

USERNAME_VALIDATOR = RegexValidator(r"^[A-Za-z0-9]+$", "Только латинские буквы и цифры")
MAX_TEXT_LENGTH = 5000
PASSWORD_MIN_LENGTH = 6
ANONYMOUS_NAME = "Аноним"

# Имена полей формы, в которые попадает ошибка из IdentityService.
POST_FIELDS = {"username": "user_name", "email": "email"}
REGISTER_FIELDS = {"username": "username", "email": "email"}


def sanitize_text(value: str) -> str:
    try:
        cleaned = HtmlSanitizer().clean(value)
    except HtmlValidationError as exc:
        raise serializers.ValidationError(str(exc))
    if not cleaned:
        raise serializers.ValidationError("Сообщение не может быть пустым")
    return cleaned


def mask_email(email: str) -> str:
    """j***@example.com: e-mail публично не показываем."""
    name, _, domain = email.partition("@")
    return f"{name[:1]}***@{domain}"


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
    """Публичное представление комментария. Для анонимных автор скрыт полностью."""

    user_name = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    home_page = serializers.SerializerMethodField()
    attachments = AttachmentSerializer(many=True, read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id", "parent", "user_name", "profile", "email", "home_page",
            "is_anonymous", "text", "created_at", "attachments", "replies",
        ]

    def get_user_name(self, obj):
        return ANONYMOUS_NAME if obj.is_anonymous else obj.profile.username

    def get_profile(self, obj):
        return None if obj.is_anonymous else obj.profile.username

    def get_email(self, obj):
        return "" if obj.is_anonymous else mask_email(obj.profile.email)

    def get_home_page(self, obj):
        return "" if obj.is_anonymous else obj.profile.home_page

    def get_replies(self, obj):
        # children заполняется в views.build_tree (без запросов в цикле)
        return CommentSerializer(getattr(obj, "children", []), many=True).data


class ProfileCommentSerializer(serializers.ModelSerializer):
    root_id = serializers.SerializerMethodField()
    is_reply = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["id", "parent", "root_id", "is_reply", "text", "created_at"]

    def get_root_id(self, obj):
        return obj.root_id_or_self

    def get_is_reply(self, obj):
        return not obj.is_root


class ProfileSerializer(serializers.ModelSerializer):
    """Свой профиль (для автозаполнения формы): с полным e-mail."""

    class Meta:
        model = Profile
        fields = ["username", "email", "home_page"]


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
    anonymous = serializers.BooleanField(required=False, default=False)
    captcha_key = serializers.CharField(required=False, allow_blank=True)
    captcha_answer = serializers.CharField(required=False, allow_blank=True)
    file = serializers.FileField(required=False)

    def validate_text(self, value):
        return sanitize_text(value)

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user if request.user.is_authenticated else None
        errors = {}

        if user:
            if getattr(user, "profile", None) is None:
                raise serializers.ValidationError({"detail": "У аккаунта нет профиля"})
        else:
            for field in ("user_name", "email"):
                if not attrs.get(field):
                    errors[field] = "Обязательное поле"

        # CAPTCHA нужна всем, в том числе зарегистрированным.
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

        if user:
            profile = user.profile  # поля 1-3 берутся из профиля автоматически
        else:
            try:
                profile = IdentityService().for_guest(
                    validated["user_name"], validated["email"], validated.get("home_page", "")
                )
            except IdentityError as exc:
                raise serializers.ValidationError({POST_FIELDS[exc.kind]: str(exc)})

        parent = validated.get("parent")
        comment = Comment.objects.create(
            profile=profile,
            parent=parent,
            root=(parent.root or parent) if parent else None,
            text=validated["text"],
            is_anonymous=validated.get("anonymous", False),
            ip_address=self.context["ip"],
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        )
        if validated.get("file"):
            Attachment.objects.create(comment=comment, file=validated["file"], kind=validated["kind"])
        return comment


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=50, validators=[USERNAME_VALIDATOR])
    email = serializers.EmailField()
    home_page = serializers.URLField(required=False, allow_blank=True)
    password = serializers.CharField(
        write_only=True,
        min_length=PASSWORD_MIN_LENGTH,
        error_messages={"min_length": f"Пароль должен быть не короче {PASSWORD_MIN_LENGTH} символов"},
    )

    def validate_password(self, value):
        if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
            raise serializers.ValidationError("Пароль должен содержать и буквы, и цифры")
        return value

    def create(self, validated):
        try:
            return IdentityService().register(
                validated["username"],
                validated["email"],
                validated["password"],
                validated.get("home_page", ""),
            )
        except IdentityError as exc:
            raise serializers.ValidationError({REGISTER_FIELDS[exc.kind]: str(exc)})
