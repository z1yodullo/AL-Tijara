from django.urls import path
from . import views

app_name = 'trading'

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('trading/', views.trading_view, name='trading'),
    path('trade/', views.trade_view, name='trade'),
    path('history/', views.history_view, name='history'),

    path('api/order/create/', views.create_order_view, name='create_order'),
    path('api/order/<int:order_id>/cancel/', views.cancel_order_view, name='cancel_order'),
    path('api/demo/reset/', views.reset_demo_account_view, name='reset_demo'),
    path('api/trade/klines/', views.trade_klines_api, name='trade_klines'),
    path('api/trade/place/', views.place_binary_trade, name='place_trade'),
    path('api/trade/balance/', views.account_balance_api, name='account_balance'),
    path('api/trade/result/', views.trade_result_api, name='trade_result'),
    path('api/trade/analyze/', views.market_analyze_api, name='market_analyze'),
]