from channels.generic.websocket import AsyncJsonConsumer

class OrderConsumer(AsyncJsonConsumer):
    async def connect(self):
        await self.accept()
        await self.channel_layer.group_add(
            "orders",
            self.channel_name
        )

    async def order_update(self, event):
        await self.send_json(event)
