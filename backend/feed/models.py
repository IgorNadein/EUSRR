# backend\feed\models.py
from django.db import models
from employees.models import Department
from django.contrib.auth import get_user_model


Employee = get_user_model()


class Post(models.Model):
    TYPE_CHOICES = [
        ('company', 'Новость компании'),
        ('department', 'Новость отдела'),
        ('personal', 'Публикация сотрудника'),
    ]
    author = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='posts')
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=200)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    pinned = models.BooleanField(default=False)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    image = models.ImageField(upload_to='feed/images/', blank=True, null=True)
    attachment = models.FileField(
        upload_to='feed/attachments/', blank=True, null=True)

    class Meta:
        ordering = ['-pinned', '-created_at']

    def __str__(self):
        return self.title


class Comment(models.Model):
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Комментарий от {self.author} к "{self.post}"'
