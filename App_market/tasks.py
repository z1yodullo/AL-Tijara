import asyncio
import json
from channels.layers import get_channel_layer
from asgiref.sync import sync_to_async
import logging

logger = logging.getLogger(__name__)


async def broadcast_prices():
    """
    Фоновая задача для рассылки текущих цен всем подключенным WebSocket клиентам.
    Запускается при старте сервера через Django Channels.
    """
    from App_market.services import get_ticker

    symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT', 'ADA/USDT']
    channel_layer = get_channel_layer()

    while True:
        try:
            for symbol in symbols:
                ticker = await sync_to_async(get_ticker)(symbol)
                if ticker:
                    room_group_name = f'prices_{symbol.replace("/", "_")}'
                    await channel_layer.group_send(
                        room_group_name,
                        {
                            'type': 'price_update',
                            'symbol': symbol,
                            'price': str(ticker['price']),
                            'change': str(ticker['change']),
                            'volume': str(ticker['volume']),
                        }
                    )
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Price broadcast error: {e}")
            await asyncio.sleep(10)
