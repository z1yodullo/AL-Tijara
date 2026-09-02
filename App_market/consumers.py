import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import logging

logger = logging.getLogger(__name__)


class PriceConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer для получения цен в реальном времени.
    Активно пушит цены каждые 200мс для плавных обновлений.
    """

    async def connect(self):
        self.symbol = self.scope['url_route']['kwargs'].get('symbol', 'BTC/USDT')
        self.room_group_name = f'prices_{self.symbol.replace("/", "_")}'
        self._pushing = False

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

        self._pushing = True
        asyncio.ensure_future(self._push_prices())

    async def _push_prices(self):
        while self._pushing:
            try:
                ticker = await asyncio.to_thread(self._get_ticker, self.symbol)
                if ticker:
                    await self.send(text_data=json.dumps({
                        'type': 'price_update',
                        'symbol': self.symbol,
                        'price': str(ticker.get('price', 0)),
                        'change': str(ticker.get('change', 0)),
                        'volume': str(ticker.get('volume', 0)),
                    }))
            except Exception as e:
                logger.debug(f"Price push error for {self.symbol}: {e}")
            await asyncio.sleep(0.2)

    def _get_ticker(self, symbol):
        from App_market.services import get_ticker
        return get_ticker(symbol)

    async def disconnect(self, close_code):
        self._pushing = False
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
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
