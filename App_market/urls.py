from django.urls import path
from . import views

app_name = 'market'

urlpatterns = [
    path('api/price/', views.price_view, name='price'),
    path('api/live-price/', views.live_price_view, name='live_price'),
    path('api/prices/', views.prices_view, name='prices'),
    path('api/orderbook/', views.order_book_view, name='orderbook'),
    path('api/klines/', views.klines_view, name='klines'),
    path('api/exchange-info/', views.exchange_info_view, name='exchange_info'),
    path('api/search/', views.search_symbols_view, name='search'),
]