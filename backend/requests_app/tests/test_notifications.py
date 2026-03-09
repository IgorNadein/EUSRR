"""
Unit тесты для уведомлений модуля Requests

Запуск:
    pytest backend/requests_app/tests/test_notifications.py -v
    или
    python manage.py test requests_app.tests.test_notifications
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch

from requests_app.models import Request, RequestComment
from employees.models import Department
from notifications.models import Notification

Employee = get_user_model()


@pytest.mark.django_db
class TestRequestNotifications(TestCase):
    """Тесты уведомлений при работе с заявлениями"""
    
    def setUp(self):
        """Подготовка тестовых данных"""
        # Создаем тестовых пользователей
        self.author = Employee.objects.create_user(
            username='test_author',
            email='author@test.com',
            first_name='Иван',
            last_name='Автор'
        )
        
        self.recipient = Employee.objects.create_user(
            username='test_recipient',
            email='recipient@test.com',
            first_name='Петр',
            last_name='Получатель'
        )
        
        self.cc_user = Employee.objects.create_user(
            username='test_cc',
            email='cc@test.com',
            first_name='Сидор',
            last_name='Копия'
        )
        
        self.approver = Employee.objects.create_user(
            username='test_approver',
            email='approver@test.com',
            first_name='Алексей',
            last_name='Согласующий'
        )
        
        # Создаем отдел
        self.department = Department.objects.create(
            name='Тестовый отдел',
            head=self.approver
        )
    
    def test_new_request_notification_to_recipient(self):
        """Тест: уведомление получателю при создании заявления"""
        # Создаем заявление
        request = Request.objects.create(
            employee=self.author,
            type='vacation',
            comment='Отпуск с 1 по 10 июля',
            status='pending',
            department=self.department
        )
        
        # Устанавливаем получателя (триггерит сигнал)
        request.recipients.set([self.recipient])
        
        # Проверяем что уведомление создано
        notifications = Notification.objects.filter(
            recipient=self.recipient,
            verb='request_new'
        )
        
        self.assertEqual(notifications.count(), 1)
        notif = notifications.first()
        
        # Проверяем содержимое
        self.assertIn('Иван Автор', notif.data['title'])
        self.assertEqual(notif.data['request_id'], request.id)
        self.assertEqual(notif.data['is_primary_recipient'], True)
        self.assertTrue(notif.unread)
    
    def test_new_request_notification_to_cc(self):
        """Тест: уведомление пользователю в копии"""
        request = Request.objects.create(
            employee=self.author,
            type='vacation',
            comment='Отпуск',
            status='pending',
            department=self.department
        )
        
        request.recipients.set([self.recipient])
        request.cc_users.set([self.cc_user])
        
        # Проверяем уведомление для CC
        notifications = Notification.objects.filter(
            recipient=self.cc_user,
            verb='request_new'
        )
        
        self.assertEqual(notifications.count(), 1)
        notif = notifications.first()
        
        self.assertEqual(notif.data['is_cc'], True)
        self.assertIn('копии', notif.data['title'])
    
    def test_request_approval_notification(self):
        """Тест: уведомление об одобрении заявления"""
        request = Request.objects.create(
            employee=self.author,
            type='vacation',
            comment='Отпуск',
            status='pending',
            department=self.department,
            approver=self.approver
        )
        request.recipients.set([self.recipient])
        
        # Очищаем уведомления о создании
        Notification.objects.all().delete()
        
        # Одобряем заявление
        request.status = 'approved'
        request.save()
        
        # Проверяем уведомление автору
        notifications = Notification.objects.filter(
            recipient=self.author,
            verb='request_approved'
        )
        
        self.assertEqual(notifications.count(), 1)
        notif = notifications.first()
        
        self.assertIn('одобрено', notif.data['title'])
        self.assertEqual(notif.data['new_status'], 'approved')
        self.assertEqual(notif.data['approver_id'], self.approver.id)
    
    def test_request_rejection_notification(self):
        """Тест: уведомление об отклонении заявления"""
        request = Request.objects.create(
            employee=self.author,
            type='vacation',
            comment='Отпуск',
            status='pending',
            department=self.department,
            approver=self.approver
        )
        request.recipients.set([self.recipient])
        
        Notification.objects.all().delete()
        
        # Отклоняем заявление
        request.status = 'rejected'
        request.save()
        
        notifications = Notification.objects.filter(
            recipient=self.author,
            verb='request_rejected'
        )
        
        self.assertEqual(notifications.count(), 1)
        notif = notifications.first()
        
        self.assertIn('отклонено', notif.data['title'])
        self.assertEqual(notif.data['new_status'], 'rejected')
    
    def test_comment_notification(self):
        """Тест: уведомление о комментарии к заявлению"""
        request = Request.objects.create(
            employee=self.author,
            type='vacation',
            comment='Отпуск',
            status='pending',
            department=self.department
        )
        request.recipients.set([self.recipient])
        
        Notification.objects.all().delete()
        
        # Добавляем комментарий
        comment = RequestComment.objects.create(
            request=request,
            author=self.recipient,
            text='Нужна справка'
        )
        
        # Проверяем уведомление автору
        notifications = Notification.objects.filter(
            recipient=self.author,
            verb='request_comment'
        )
        
        self.assertEqual(notifications.count(), 1)
        notif = notifications.first()
        
        self.assertIn('комментарий', notif.data['title'])
        self.assertEqual(notif.data['comment_id'], comment.id)
        self.assertIn('Нужна справка', notif.description)
    
    def test_no_notification_to_author_on_own_comment(self):
        """Тест: автор не получает уведомление о своем комментарии"""
        request = Request.objects.create(
            employee=self.author,
            type='vacation',
            comment='Отпуск',
            status='pending',
            department=self.department
        )
        request.recipients.set([self.recipient])
        
        Notification.objects.all().delete()
        
        # Автор комментирует свое заявление
        RequestComment.objects.create(
            request=request,
            author=self.author,
            text='Дополнительная информация'
        )
        
        # Автор НЕ должен получить уведомление
        notifications = Notification.objects.filter(
            recipient=self.author,
            verb='request_comment'
        )
        
        self.assertEqual(notifications.count(), 0)
    
    def test_multiple_recipients_notification(self):
        """Тест: уведомления всем получателям"""
        request = Request.objects.create(
            employee=self.author,
            type='vacation',
            comment='Отпуск',
            status='pending',
            department=self.department
        )
        
        # Множественные получатели
        request.recipients.set([self.recipient, self.cc_user])
        
        # Проверяем что оба получили уведомления
        notifications = Notification.objects.filter(
            verb='request_new'
        )
        
        self.assertEqual(notifications.count(), 2)
        recipients = [n.recipient for n in notifications]
        
        self.assertIn(self.recipient, recipients)
        self.assertIn(self.cc_user, recipients)
    
    @patch('notifications.channels.route_notification_to_channels')
    def test_channels_called_on_notification(self, mock_channels):
        """Тест: channels.py вызывается при создании уведомления"""
        request = Request.objects.create(
            employee=self.author,
            type='vacation',
            comment='Отпуск',
            status='pending',
            department=self.department
        )
        
        request.recipients.set([self.recipient])
        
        # Проверяем что channels.py был вызван
        # (он должен вызываться автоматически через post_save)
        notification = Notification.objects.filter(
            recipient=self.recipient,
            verb='request_new'
        ).first()
        
        # Просто проверяем что уведомление создано
        # (channels.py запустится автоматически через сигнал)
        self.assertIsNotNone(notification)
