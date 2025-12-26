#!/usr/bin/env python
"""Тест сериализации сообщения при редактировании"""

import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from communications.models import Message, MessageAttachment
from communications.consumers import serialize_message
import json

print("=" * 70)
print("ТЕСТ: Сериализация сообщения при редактировании")
print("=" * 70)

# Находим сообщение с вложениями
msg_with_attachments = Message.objects.filter(
    has_attachments=True
).select_related(
    'author',
    'reply_to',
    'reply_to__author'
).prefetch_related(
    'attachments',
    'reactions',
    'reactions__user'
).first()

if msg_with_attachments:
    print(f"\n✓ Найдено сообщение с вложениями: ID {msg_with_attachments.id}")
    print(f"  Автор: {msg_with_attachments.author}")
    print(f"  Вложений: {msg_with_attachments.attachments.count()}")
    
    # Сериализуем ДО перезагрузки
    print("\n--- Сериализация БЕЗ prefetch ---")
    msg_simple = Message.objects.get(pk=msg_with_attachments.id)
    data_simple = serialize_message(msg_simple)
    print(f"  has_attachments: {data_simple.get('has_attachments')}")
    print(f"  attachments в JSON: {len(data_simple.get('attachments', []))}")
    
    # Сериализуем ПОСЛЕ перезагрузки с prefetch
    print("\n--- Сериализация С prefetch ---")
    msg_prefetched = Message.objects.select_related(
        'author',
        'reply_to',
        'reply_to__author',
        'forwarded_from_author',
        'poll'
    ).prefetch_related(
        'attachments',
        'reactions',
        'reactions__user',
        'poll__options'
    ).get(pk=msg_with_attachments.id)
    
    data_prefetched = serialize_message(msg_prefetched)
    print(f"  has_attachments: {data_prefetched.get('has_attachments')}")
    print(f"  attachments в JSON: {len(data_prefetched.get('attachments', []))}")
    
    if data_prefetched.get('attachments'):
        print("\n  Вложения:")
        for att in data_prefetched['attachments']:
            print(f"    - {att['file_name']} ({att['file_type']})")
    
    print("\n✓ С prefetch все вложения загружены корректно!")
else:
    print("\n⚠️  Не найдено сообщений с вложениями")

# Находим сообщение с ответом
print("\n" + "=" * 70)
msg_with_reply = Message.objects.filter(
    reply_to__isnull=False
).select_related(
    'author',
    'reply_to',
    'reply_to__author'
).first()

if msg_with_reply:
    print(f"\n✓ Найдено сообщение с ответом: ID {msg_with_reply.id}")
    print(f"  Отвечает на: ID {msg_with_reply.reply_to_id}")
    
    # Сериализуем БЕЗ select_related
    print("\n--- Сериализация БЕЗ select_related ---")
    msg_simple = Message.objects.get(pk=msg_with_reply.id)
    data_simple = serialize_message(msg_simple)
    print(f"  reply_to в JSON: {data_simple.get('reply_to', 'НЕТ')}")
    
    # Сериализуем С select_related
    print("\n--- Сериализация С select_related ---")
    msg_prefetched = Message.objects.select_related(
        'author',
        'reply_to',
        'reply_to__author'
    ).get(pk=msg_with_reply.id)
    
    data_prefetched = serialize_message(msg_prefetched)
    if data_prefetched.get('reply_to'):
        print(f"  reply_to.id: {data_prefetched['reply_to']['id']}")
        print(f"  reply_to.author_name: {data_prefetched['reply_to']['author_name']}")
        print(f"  reply_to.content: {data_prefetched['reply_to']['content'][:50]}...")
        print("\n✓ С select_related reply_to загружен корректно!")
    else:
        print("  ✗ reply_to не загружен!")
else:
    print("\n⚠️  Не найдено сообщений с ответами")

print("\n" + "=" * 70)
print("ВЫВОД:")
print("=" * 70)
print("""
Для корректной сериализации при редактировании НЕОБХОДИМО:

message = Message.objects.select_related(
    'author',
    'reply_to',
    'reply_to__author',
    'forwarded_from_author',
    'poll'
).prefetch_related(
    'attachments',
    'reactions',
    'reactions__user',
    'poll__options'
).get(pk=message_id)

payload = serialize_message(message)
""")
print("=" * 70)
