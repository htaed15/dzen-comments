import django.db.models.deletion
import django.db.models.functions.text
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Profile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(max_length=50)),
                ("email", models.EmailField(max_length=254)),
                ("home_page", models.URLField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Comment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.TextField()),
                ("is_anonymous", models.BooleanField(default=False)),
                ("ip_address", models.GenericIPAddressField()),
                ("user_agent", models.CharField(blank=True, max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="replies",
                        to="comments.comment",
                    ),
                ),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="comments",
                        to="comments.profile",
                    ),
                ),
                (
                    "root",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="descendants",
                        to="comments.comment",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Attachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="attachments/%Y/%m/")),
                ("kind", models.CharField(choices=[("image", "image"), ("text", "text")], max_length=10)),
                (
                    "status",
                    models.CharField(
                        choices=[("processing", "processing"), ("ready", "ready"), ("failed", "failed")],
                        default="processing",
                        max_length=12,
                    ),
                ),
                (
                    "comment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attachments",
                        to="comments.comment",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="profile",
            index=models.Index(fields=["username"], name="profile_username_idx"),
        ),
        migrations.AddIndex(
            model_name="profile",
            index=models.Index(fields=["email"], name="profile_email_idx"),
        ),
        migrations.AddConstraint(
            model_name="profile",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower("username"), name="profile_username_ci_uniq"
            ),
        ),
        migrations.AddConstraint(
            model_name="profile",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower("email"), name="profile_email_ci_uniq"
            ),
        ),
        migrations.AddIndex(
            model_name="comment",
            index=models.Index(fields=["parent", "created_at"], name="cmt_parent_created_idx"),
        ),
        migrations.AddIndex(
            model_name="comment",
            index=models.Index(fields=["root", "created_at"], name="cmt_root_created_idx"),
        ),
        migrations.AddIndex(
            model_name="comment",
            index=models.Index(fields=["profile", "created_at"], name="cmt_profile_created_idx"),
        ),
    ]
