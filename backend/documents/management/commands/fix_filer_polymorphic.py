"""
Management command для исправления polymorphic_ctype_id в django-filer File объектах
"""
from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from filer.models import File, Image


class Command(BaseCommand):
    help = 'Исправляет polymorphic_ctype_id для всех filer.File объектов'

    def handle(self, *args, **options):
        self.stdout.write('Исправление polymorphic_ctype_id для filer.File объектов...')

        # Получаем ContentType для базового File класса
        file_ctype = ContentType.objects.get_for_model(File)
        image_ctype = ContentType.objects.get_for_model(Image)
        
        # Используем прямой SQL чтобы избежать проблем с polymorphic
        with connection.cursor() as cursor:
            # Проверяем сколько файлов без polymorphic_ctype_id
            cursor.execute(
                "SELECT COUNT(*) FROM filer_file WHERE polymorphic_ctype_id IS NULL"
            )
            count = cursor.fetchone()[0]
            
            if count == 0:
                self.stdout.write(self.style.SUCCESS('Все файлы уже имеют правильный polymorphic_ctype_id'))
                return
            
            self.stdout.write(f'Найдено {count} файлов без polymorphic_ctype_id')
            
            # Обновляем файлы с типом image/*
            cursor.execute(
                """
                UPDATE filer_file 
                SET polymorphic_ctype_id = %s 
                WHERE polymorphic_ctype_id IS NULL 
                AND mime_type LIKE 'image/%%'
                """,
                [image_ctype.id]
            )
            image_fixed = cursor.rowcount
            
            # Обновляем остальные файлы
            cursor.execute(
                """
                UPDATE filer_file 
                SET polymorphic_ctype_id = %s 
                WHERE polymorphic_ctype_id IS NULL
                """,
                [file_ctype.id]
            )
            file_fixed = cursor.rowcount
        
        total_fixed = image_fixed + file_fixed
        self.stdout.write(self.style.SUCCESS(
            f'Успешно исправлено {total_fixed} файлов '
            f'({image_fixed} изображений, {file_fixed} остальных)'
        ))
