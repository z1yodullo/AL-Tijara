from django.shortcuts import render

from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import UserRegistrationForm, UserLoginForm
from .models import DemoAccount


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
    demo_account = request.user.demo_account
    
    return render(request, 'users/profile.html', {
        'demo_balance': demo_account.balance,
        'total_value': demo_account.total_value_usdt,
    })