from channels.generic.websocket import AsyncJsonWebsocketConsumer


class CommentsConsumer(AsyncJsonWebsocketConsumer):
    group = "comments"

    async def connect(self):
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    # Имена методов соответствуют типам событий: "comment.created" -> comment_created
    async def comment_created(self, event):
        await self.send_json(event["payload"])

    async def comment_updated(self, event):
        await self.send_json(event["payload"])
