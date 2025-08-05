from django.db import models
from django.contrib.auth import get_user_model

Employee = get_user_model()


class Request(models.Model):
    TYPE_CHOICES = [
        ('vacation', 'Отпуск'),
        ('sick_leave', 'Больничный'),
        ('transfer', 'Перевод'),
        ('dismissal', 'Увольнение'),
        ('other', 'Другое'),
    ]
    STATUS_CHOICES = [
        ('pending', 'На рассмотрении'),
        ('approved', 'Одобрено'),
        ('rejected', 'Отклонено'),
    ]
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='requests')
    type = models.CharField('Тип заявления', choices=TYPE_CHOICES, max_length=32)
    date_from = models.DateField('Дата начала', null=True, blank=True)
    date_to = models.DateField('Дата окончания', null=True, blank=True)
    comment = models.TextField('Комментарий', blank=True)
    status = models.CharField(
        'Статус', choices=STATUS_CHOICES, max_length=16, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Заявление'
        verbose_name_plural = 'Заявления'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_type_display()} — {self.employee} ({self.get_status_display()})"

