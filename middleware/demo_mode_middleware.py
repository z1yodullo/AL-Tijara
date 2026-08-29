from django.shortcuts import redirect
from django.urls import reverse

class DemoModeMiddleware:
    """
    Если пользователь в демо-режиме, передаёт объект демо-счета в запрос.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if hasattr(request.user, 'demo_account'):
                request.demo_account = request.user.demo_account
            else:
                try:
                    from App_users.models import DemoAccount
                    request.demo_account = DemoAccount.objects.create(user=request.user)
                except:
                    pass

            if hasattr(request.user, 'real_account'):
                request.real_account = request.user.real_account
            else:
                try:
                    from App_users.models import RealAccount
                    request.real_account = RealAccount.objects.create(
                        user=request.user,
                        balance={'USDT': 0.0, 'BTC': 0.0, 'ETH': 0.0, 'BNB': 0.0}
                    )
                except:
                    pass
        
        response = self.get_response(request)
        return response