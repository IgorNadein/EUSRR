"""
Management команда для заполнения размеров существующих изображений
"""
from django.core.management.base import BaseCommand
from communications.models import MessageAttachment
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Заполняет поля width и height для существующих изображений'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать изменения без сохранения в БД',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Получаем все изображения без размеров
        attachments = MessageAttachment.objects.filter(
            file_type='image',
            width__isnull=True
        )

        total = attachments.count()
        self.stdout.write(f'Найдено {total} изображений без размеров')

        updated = 0
        errors = 0

        for att in attachments:
            try:
                if not att.file:
                    self.stdout.write(self.style.WARNING(
                        f'Attachment #{att.id}: файл не найден'
                    ))
                    continue

                # Открываем файл без сохранения его в память целиком
                with att.file.open('rb') as f:
                    image = Image.open(f)
                    width, height = image.size

                if dry_run:
                    self.stdout.write(
                        f'Attachment #{att.id}: {width}x{height} (dry-run)'
                    )
                else:
                    att.width = width
                    att.height = height
                    att.save(update_fields=['width', 'height'])
                    self.stdout.write(self.style.SUCCESS(
                        f'Attachment #{att.id}: {width}x{height}'
                    ))

                updated += 1

            except Exception as e:
                errors += 1
                self.stdout.write(self.style.ERROR(
                    f'Attachment #{att.id}: ошибка - {e}'
                ))

        self.stdout.write(self.style.SUCCESS(
            f'\nОбработано: {updated}/{total}, ошибок: {errors}'
        ))
