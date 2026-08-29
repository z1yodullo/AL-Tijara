from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('alerts/', views.alerts_view, name='alerts'),
    path('alerts/create/', views.create_alert_view, name='create_alert'),
    path('alerts/<int:alert_id>/delete/', views.delete_alert_view, name='delete_alert'),
    path('alerts/check/', views.check_alerts_view, name='check_alerts'),

    path('watchlist/', views.watchlist_view, name='watchlist'),
    path('watchlist/add/', views.add_to_watchlist_view, name='add_watchlist'),
    path('watchlist/<int:item_id>/remove/', views.remove_from_watchlist_view, name='remove_watchlist'),

    path('arbitrage/', views.arbitrage_view, name='arbitrage'),
    path('backtest/', views.backtest_view, name='backtest'),
    path('backtest/run/', views.run_backtest_view, name='run_backtest'),
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    path('pnl/', views.pnl_view, name='pnl'),
    path('export/', views.export_trades_view, name='export'),
    path('indicators/', views.indicators_view, name='indicators'),
]
