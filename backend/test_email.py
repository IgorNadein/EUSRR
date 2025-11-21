#!/usr/bin/env python3
"""
Тестовый скрипт для проверки отправки email через SMTP Яндекса
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Настройки из .env
EMAIL_HOST = "smtp.yandex.ru"
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_HOST_USER = "robotail-info@yandex.ru"
EMAIL_HOST_PASSWORD = "wogrpijpzbtiuptx"
DEFAULT_FROM_EMAIL = "Robotail <robotail-info@yandex.ru>"

# Получатель
TO_EMAIL = "igor_26reg@mail.ru"

def test_email():
    print("=" * 50)
    print("Тест отправки email через Яндекс SMTP")
    print("=" * 50)
    print(f"Хост: {EMAIL_HOST}:{EMAIL_PORT}")
    print(f"От кого: {EMAIL_HOST_USER}")
    print(f"Кому: {TO_EMAIL}")
    print(f"SSL: {EMAIL_USE_SSL}")
    print()

    # Создаем сообщение
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Тестовое письмо - проверка SMTP"
    msg['From'] = DEFAULT_FROM_EMAIL
    msg['To'] = TO_EMAIL

    # Текст письма
    text = "Это тестовое письмо для проверки настроек SMTP."
    html = """
    <html>
      <head></head>
      <body>
        <h2>Тестовое письмо</h2>
        <p>Это тестовое письмо для проверки настроек SMTP Яндекса.</p>
        <p>Если вы получили это письмо, значит настройки корректны.</p>
      </body>
    </html>
    """

    part1 = MIMEText(text, 'plain', 'utf-8')
    part2 = MIMEText(html, 'html', 'utf-8')
    msg.attach(part1)
    msg.attach(part2)

    try:
        print("Подключение к SMTP серверу...")
        if EMAIL_USE_SSL:
            server = smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT, timeout=10)
        else:
            server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=10)
            server.starttls()
        
        print("✓ Подключение установлено")
        
        print("Авторизация...")
        server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        print("✓ Авторизация успешна")
        
        print("Отправка письма...")
        server.send_message(msg)
        print("✓ Письмо отправлено!")
        
        server.quit()
        print()
        print("=" * 50)
        print("SUCCESS! Письмо успешно отправлено на", TO_EMAIL)
        print("=" * 50)
        
    except smtplib.SMTPAuthenticationError as e:
        print()
        print("=" * 50)
        print("ОШИБКА АВТОРИЗАЦИИ!")
        print("=" * 50)
        print(f"Код ошибки: {e.smtp_code}")
        print(f"Сообщение: {e.smtp_error.decode('utf-8')}")
        print()
        print("Возможные причины:")
        print("1. Неверный пароль приложения")
        print("2. Доступ заблокирован для данного IP-адреса")
        print("3. Необходимо создать новый пароль приложения в настройках Яндекса")
        print()
        print("Решение:")
        print("1. Зайдите на https://passport.yandex.ru/profile")
        print("2. Перейдите в раздел 'Пароли и авторизация'")
        print("3. Создайте новый пароль приложения")
        print("4. Обновите EMAIL_HOST_PASSWORD в .env файле")
        
    except smtplib.SMTPException as e:
        print()
        print("=" * 50)
        print("ОШИБКА SMTP!")
        print("=" * 50)
        print(f"Ошибка: {e}")
        
    except Exception as e:
        print()
        print("=" * 50)
        print("ОБЩАЯ ОШИБКА!")
        print("=" * 50)
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_email()
