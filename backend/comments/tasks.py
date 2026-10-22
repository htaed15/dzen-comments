import logging

from celery import shared_task
from django.core.mail import send_mail
from django.utils.html import strip_tags

from . import events
from .models import Attachment, Comment
from .services.attachments import AttachmentProcessor

logger = logging.getLogger(__name__)


@shared_task
def process_attachment(attachment_id: int) -> None:
    attachment = Attachment.objects.filter(pk=attachment_id).first()
    if attachment is None:
        return
    try:
        AttachmentProcessor().process(attachment)
        attachment.status = "ready"
    except Exception:
        logger.exception("Не удалось обработать вложение %s", attachment_id)
        attachment.status = "failed"
    attachment.save(update_fields=["status"])
    events.publish("comment.updated", attachment.comment_id)


@shared_task
def notify_parent_author(comment_id: int) -> None:
    comment = (
        Comment.objects.filter(pk=comment_id, parent__isnull=False)
        .select_related("author", "parent__author")
        .first()
    )
    if comment is None:
        return
    send_mail(
        subject=f"Новый ответ на ваш комментарий от {comment.author.user_name}",
        message=strip_tags(comment.text),
        from_email=None,
        recipient_list=[comment.parent.author.email],
        fail_silently=True,
    )
