from django.conf import settings
from django.db import models


class Author(models.Model):
    """Данные, которые помогают идентифицировать клиента (имя, e-mail, IP, браузер)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="comment_authors",
    )
    user_name = models.CharField(max_length=50, db_index=True)
    email = models.EmailField(db_index=True)
    home_page = models.URLField(blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_name} <{self.email}>"


class Comment(models.Model):
    author = models.ForeignKey(Author, on_delete=models.PROTECT, related_name="comments")
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
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["parent", "created_at"], name="cmt_parent_created_idx"),
            models.Index(fields=["root", "created_at"], name="cmt_root_created_idx"),
        ]

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
