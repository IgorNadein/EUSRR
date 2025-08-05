# from django.shortcuts import render, redirect
# from django.contrib.auth.decorators import login_required
# import secrets

# @login_required
# def generate_messenger_token(request):
#     user = request.user
#     user.registration_token = secrets.token_hex(16)
#     user.save(update_fields=['registration_token'])
#     telegram_link = f"https://t.me/your_bot?start={user.registration_token}"
#     # Можно также вернуть QR-код
#     return render(request, 'users/messenger_token.html', {
#         'telegram_link': telegram_link,
#         'token': user.registration_token,
#     })
