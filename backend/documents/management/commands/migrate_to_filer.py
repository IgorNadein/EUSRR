# documents/management/commands/migrate_to_filer.py
"""
Команда для миграции данных из старых моделей Document и DocumentAcknowledgement
в новые модели DocumentV2 и DocumentAcknowledgementV2 с использованием django-filer.

Команда:
    python manage.py migrate_to_filer [--dry-run]

Опции:
    --dry-run: Запуск без изменений в БД (только показать что будет сделано)
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.core.files import File
from filer.models import File as FilerFile
from documents.models import Document, DocumentAcknowledgement, DocumentV2, DocumentAcknowledgementV2
import os


class Command(BaseCommand):
    help = 'Миграция документов из старой модели в DocumentV2 с django-filer'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Запуск без изменений в БД (только показать что будет сделано)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 Режим DRY-RUN: изменения не будут сохранены в БД'))
        
        # Счетчики
        documents_migrated = 0
        acknowledgements_migrated = 0
        errors = 0
        
        # Получаем все документы из старой модели
        old_documents = Document.objects.all().select_related('uploaded_by').prefetch_related(
            'departments', 'recipients', 'acknowledgements'
        )
        
        total = old_documents.count()
        self.stdout.write(f'📁 Найдено документов для миграции: {total}')
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS('✅ Нет документов для миграции'))
            return
        
        # Начинаем миграцию
        with transaction.atomic():
            for old_doc in old_documents:
                try:
                    self.stdout.write(f'\n📄 Миграция: {old_doc.title} (ID: {old_doc.id})')
                    
                    # 1. Создаем FilerFile из старого файла
                    filer_file = None
                    if old_doc.file:
                        self.stdout.write(f'   📎 Загрузка файла: {old_doc.file.name}')
                        
                        if not dry_run:
                            # Открываем файл и создаем FilerFile
                            with old_doc.file.open('rb') as f:
                                original_filename = os.path.basename(old_doc.file.name)
                                
                                filer_file = FilerFile.objects.create(
                                    file=File(f, name=original_filename),
                                    original_filename=original_filename,
                                    name=old_doc.title,
                                    owner=old_doc.uploaded_by,
                                )
                                self.stdout.write(self.style.SUCCESS(f'   ✅ Filer файл создан: {filer_file.id}'))
                    
                    # 2. Создаем новый DocumentV2
                    if not dry_run:
                        new_doc = DocumentV2.objects.create(
                            title=old_doc.title,
                            file=filer_file,
                            description=old_doc.description,
                            uploaded_by=old_doc.uploaded_by,
                            uploaded_at=old_doc.uploaded_at,
                            sent_to_all=old_doc.sent_to_all,
                        )
                        
                        # Копируем M2M отношения
                        new_doc.departments.set(old_doc.departments.all())
                        new_doc.recipients.set(old_doc.recipients.all())
                        
                        self.stdout.write(self.style.SUCCESS(f'   ✅ DocumentV2 создан: {new_doc.id}'))
                        documents_migrated += 1
                        
                        # 3. Мигрируем acknowledgements
                        acknowledgements = old_doc.acknowledgements.all()
                        for ack in acknowledgements:
                            DocumentAcknowledgementV2.objects.create(
                                document=new_doc,
                                user=ack.user,
                                acknowledged_at=ack.acknowledged_at,
                            )
                            acknowledgements_migrated += 1
                        
                        if acknowledgements.count() > 0:
                            self.stdout.write(self.style.SUCCESS(
                                f'   ✅ Ознакомлений перенесено: {acknowledgements.count()}'
                            ))
                    else:
                        # Dry-run: просто показываем что будет сделано
                        self.stdout.write(f'   ➡️ Будет создан DocumentV2')
                        self.stdout.write(f'      - departments: {old_doc.departments.count()}')
                        self.stdout.write(f'      - recipients: {old_doc.recipients.count()}')
                        self.stdout.write(f'      - acknowledgements: {old_doc.acknowledgements.count()}')
                        documents_migrated += 1
                        acknowledgements_migrated += old_doc.acknowledgements.count()
                
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'   ❌ Ошибка: {e}'))
                    errors += 1
                    if not dry_run:
                        raise  # В транзакции — откатываем все
            
            # Если dry-run — откатываем транзакцию
            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING('\n⚠️ Транзакция откачена (dry-run mode)'))
        
        # Финальный отчет
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('📊 Результаты миграции:'))
        self.stdout.write(f'   📁 Документов мигрировано: {documents_migrated} / {total}')
        self.stdout.write(f'   ✅ Ознакомлений мигрировано: {acknowledgements_migrated}')
        if errors > 0:
            self.stdout.write(self.style.ERROR(f'   ❌ Ошибок: {errors}'))
        else:
            self.stdout.write(self.style.SUCCESS('   ✅ Ошибок нет!'))
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS('\n✅ Миграция завершена успешно!'))
            self.stdout.write('\n⚠️ Следующие шаги:')
            self.stdout.write('   1. Проверьте мигрированные данные в админке')
            self.stdout.write('   2. Обновите views.py для работы с DocumentV2')
            self.stdout.write('   3. Обновите admin.py для использования filer widgets')
            self.stdout.write('   4. После проверки удалите старые модели Document и DocumentAcknowledgement')
        else:
            self.stdout.write(self.style.WARNING('\n⚠️ Это был DRY-RUN. Запустите без --dry-run для реальной миграции.'))
