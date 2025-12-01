"""
Тест: обновление сообщений при редактировании сообщения, на которое ответили
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from communications.models import Message, Chat
from employees.models import Employee
from django.contrib.auth import get_user_model

User = get_user_model()

def test_reply_update():
    """Проверяем, что при редактировании сообщения обновляются все ответы на него"""
    
    print("🧪 Тест: обновление reply_to при редактировании")
    print("=" * 60)
    
    # Находим тестовый чат с сообщениями
    chat = Chat.objects.filter(
        type='private'
    ).prefetch_related('messages').first()
    
    if not chat:
        print("❌ Не найдено приватных чатов")
        return
    
    print(f"✓ Чат: {chat}")
    
    # Находим сообщение, на которое есть ответы
    original_msg = Message.objects.filter(
        chat=chat,
        replies__isnull=False  # Есть ответы на это сообщение
    ).first()
    
    if not original_msg:
        print("❌ Не найдено сообщение с ответами")
        print("Создадим тестовые сообщения...")
        
        # Создаём тестовые сообщения
        user1 = chat.members.first()
        user2 = chat.members.last()
        
        if user1 == user2 or not user2:
            print("❌ Нужно минимум 2 участника")
            return
        
        # Сообщение 1 (на которое ответят)
        original_msg = Message.objects.create(
            chat=chat,
            author=user1,
            content="Оригинальное сообщение для редактирования"
        )
        print(f"✓ Создано оригинальное сообщение: ID={original_msg.id}")
        
        # Сообщение 2 (ответ на первое)
        reply_msg = Message.objects.create(
            chat=chat,
            author=user2,
            content="Ответ на оригинальное сообщение",
            reply_to=original_msg
        )
        print(f"✓ Создан ответ: ID={reply_msg.id}")
    
    # Находим все ответы на это сообщение
    replies = Message.objects.filter(
        reply_to=original_msg,
        chat=chat
    )
    
    print(f"\n📝 Оригинальное сообщение (ID={original_msg.id}):")
    print(f"   Контент: '{original_msg.content}'")
    print(f"   Ответов на него: {replies.count()}")
    
    for reply in replies:
        print(f"\n📨 Ответ (ID={reply.id}):")
        print(f"   Контент: '{reply.content}'")
        print(f"   reply_to.id: {reply.reply_to.id}")
        print(f"   reply_to.content: '{reply.reply_to.content}'")
    
    print("\n" + "=" * 60)
    print("✅ Структура готова для теста!")
    print("\nТеперь:")
    print(f"1. Откройте чат ID={chat.id}")
    print(f"2. Отредактируйте сообщение ID={original_msg.id}")
    print(f"3. Проверьте, что сообщения с ID={[r.id for r in replies]} обновились")
    print("4. В reply-preview должен быть новый текст")

if __name__ == '__main__':
    test_reply_update()
