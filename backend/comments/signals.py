from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from . import events
from .models import Attachment, Comment
from .tasks import notify_parent_author, process_attachment


@receiver(post_save, sender=Comment)
def comment_created(sender, instance, created, **kwargs):
    if not created:
        return

    def after_commit():
        events.publish("comment.created", instance.pk)
        if instance.parent_id:
            notify_parent_author.delay(instance.pk)

    transaction.on_commit(after_commit)


@receiver(post_save, sender=Attachment)
def attachment_created(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(lambda: process_attachment.delay(instance.pk))
