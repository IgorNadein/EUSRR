import os
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .forms import ProfileUpdateForm
from bots.models import BotSubscriber
from dotenv import load_dotenv

load_dotenv()

USERNAME_TELEGRAM_BOT = os.getenv('USERNAME_TELEGRAM_BOT')

@login_required
def profile(request):
    bot_sub, _ = BotSubscriber.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileUpdateForm(instance=request.user)

    tg_link = f"https://t.me/{USERNAME_TELEGRAM_BOT}"

    return render(request, 'profile.html', {
        'form': form,
        'tg_link': tg_link,
        'bot_sub': bot_sub,
    })

@login_required
def avatar_remove(request):
    if request.method == 'POST':
        user = request.user
        if user.avatar:
            user.avatar.delete(save=True)
            messages.success(request, 'Аватар успешно удалён')
        return redirect('profile')
    return redirect('profile')
