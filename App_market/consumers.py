import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import logging

logger = logging.getLogger(__name__)


class PriceConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer для получения цен в реальном времени.
    Подписывается на обновления цен выбранных торговых пар.
    """

    async def connect(self):
        """
        Устанавливает WebSocket соединение.
        Присоединяется к группе prices для получения обновлений.
        """
        self.symbol = self.scope['url_route']['kwargs'].get('symbol', 'BTC/USDT')
        self.room_group_name = f'prices_{self.symbol.replace("/", "_")}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        await self.send(text_data=json.dumps({
            'type': 'connected',
            'symbol': self.symbol,
            'message': f'Connected to {self.symbol} price stream'
        }))

    async def disconnect(self, close_code):
        """
        Закрывает WebSocket соединение и отписывается от группы.
        """
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """
        Обрабатывает входящие сообщения от клиента.
        """
        try:
            data = json.loads(text_data)
            if data.get('type') == 'subscribe':
                self.symbol = data.get('symbol', self.symbol)
                self.room_group_name = f'prices_{self.symbol.replace("/", "_")}'
                await self.channel_layer.group_add(
                    self.room_group_name,
                    self.channel_name
                )
        except json.JSONDecodeError:
            pass

    async def price_update(self, event):
        """
        Отправляет обновление цены клиенту.
        Вызывается из группы при получении нового курса.
        """
        await self.send(text_data=json.dumps({
            'type': 'price_update',
            'symbol': event['symbol'],
            'price': event['price'],
            'change': event.get('change', 0),
            'volume': event.get('volume', 0),
        }))


class OrderBookConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer для получения стакана заказов в реальном времени.
    """

    async def connect(self):
        """
        Устанавливает соединение для обновлений стакана.
        """
        self.symbol = self.scope['url_route']['kwargs'].get('symbol', 'BTC/USDT')
        self.room_group_name = f'orderbook_{self.symbol.replace("/", "_")}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        """
        Закрывает соединение стакана.
        """
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def orderbook_update(self, event):
        """
        Отправляет обновление стакана клиенту.
        """
        await self.send(text_data=json.dumps({
            'type': 'orderbook_update',
            'symbol': event['symbol'],
            'bids': event.get('bids', []),
            'asks': event.get('asks', []),
        }))
