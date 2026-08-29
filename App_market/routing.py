from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/prices/(?P<symbol>[^/]+)/$', consumers.PriceConsumer.as_asgi()),
    re_path(r'ws/orderbook/(?P<symbol>[^/]+)/$', consumers.OrderBookConsumer.as_asgi()),
]
