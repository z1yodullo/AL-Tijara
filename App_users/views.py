from django.shortcuts import render

from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from .forms import UserRegistrationForm, UserLoginForm
from .models import DemoAccount, DemoOrder, RealAccount


def register_view(request):
    """
    Регистрация
    """
    if request.user.is_authenticated:
        return redirect('trading:dashboard')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Регистрация успешна! Теперь вы можете войти.')
            return redirect('users:login')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'users/register.html', {'form': form})


def login_view(request):
    """
    Вход
    """
    if request.user.is_authenticated:
        return redirect('trading:dashboard')
    
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            
            if user:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {user.username}!')
                return redirect('trading:dashboard')
            else:
                messages.error(request, 'Неверное имя пользователя или пароль.')
    else:
        form = UserLoginForm()
    
    return render(request, 'users/login.html', {'form': form})


def logout_view(request):
    """
    Выход
    """
    logout(request)
    messages.info(request, 'Вы вышли из аккаунта.')
    return redirect('users:login')


@login_required
def profile_view(request):
    """
    Профиль пользователя
    """
    user = request.user
    demo_account = user.demo_account

    demo_balance = demo_account.get_balance('USDT')
    total_value = demo_account.total_value_usdt or demo_balance

    real_balance = 0
    if hasattr(user, 'real_account'):
        real_balance = user.real_account.get_balance('USDT')

    orders = DemoOrder.objects.filter(account=demo_account, status='FILLED')
    total_trades = orders.count()
    win_trades = orders.filter(error_message__icontains='WIN').count()
    lose_trades = total_trades - win_trades
    win_rate = round(win_trades / total_trades * 100, 1) if total_trades > 0 else 0

    watchlist_count = user.watchlist.count()

    return render(request, 'users/profile.html', {
        'demo_balance': demo_balance,
        'total_value': total_value,
        'real_balance': real_balance,
        'total_trades': total_trades,
        'win_trades': win_trades,
        'lose_trades': lose_trades,
        'win_rate': win_rate,
        'watchlist_count': watchlist_count,
    })