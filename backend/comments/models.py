from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class Profile(models.Model):
    """Профиль пользователя.

    Создаётся при регистрации или при первом сообщении под новым именем.
    Имя и e-mail уникальны без учёта регистра, e-mail привязан к одному имени.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="profile",
    )
    username = models.CharField(max_length=50)
    email = models.EmailField()
    home_page = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("username"), name="profile_username_ci_uniq"),
            models.UniqueConstraint(Lower("email"), name="profile_email_ci_uniq"),
        ]
        indexes = [
            models.Index(fields=["username"], name="profile_username_idx"),
            models.Index(fields=["email"], name="profile_email_idx"),
        ]

    @property
    def is_registered(self) -> bool:
        return self.user_id is not None

    def __str__(self):
        return self.username


class Comment(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.PROTECT, related_name="comments")
    # Непосредственный родитель (для каскадного отображения).
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    # Корневой комментарий ветки: позволяет загрузить всё дерево одним запросом.
    root = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="descendants",
        editable=False,
    )
    text = models.TextField()  # уже очищенный HTML
    # Анонимный комментарий: автор известен системе, но публично скрыт.
    is_anonymous = models.BooleanField(default=False)
    # Данные, по которым можно идентифицировать клиента.
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["parent", "created_at"], name="cmt_parent_created_idx"),
            models.Index(fields=["root", "created_at"], name="cmt_root_created_idx"),
            models.Index(fields=["profile", "created_at"], name="cmt_profile_created_idx"),
        ]

    @property
    def is_root(self) -> bool:
        return self.parent_id is None

    @property
    def root_id_or_self(self) -> int:
        return self.root_id or self.pk

    def __str__(self):
        return f"Comment #{self.pk}"


class Attachment(models.Model):
    KIND_CHOICES = [("image", "image"), ("text", "text")]
    STATUS_CHOICES = [
        ("processing", "processing"),
        ("ready", "ready"),
        ("failed", "failed"),
    ]

    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="attachments/%Y/%m/")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="processing")
