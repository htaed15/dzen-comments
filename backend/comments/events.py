from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache

_VERSION_KEY = "comments:version"


def get_version() -> int:
    return cache.get(_VERSION_KEY, 1)


def bump_version() -> None:
    """Инвалидация кеша списков: меняем номер версии, старые ключи протухают сами."""
    cache.add(_VERSION_KEY, 1, timeout=None)
    cache.incr(_VERSION_KEY)


def publish(event_type: str, comment_id: int) -> None:
    """Сбросить кеш и разослать событие всем подключённым по WebSocket."""
    bump_version()
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        "comments",
        {"type": event_type, "payload": {"event": event_type, "id": comment_id}},
    )
