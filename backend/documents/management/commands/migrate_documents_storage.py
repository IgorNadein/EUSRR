"""
Management команда для миграции файлов документов из старой структуры filer_public/ 
в новую структуру documents/public/ и documents/private/.

Использование:
    python manage.py migrate_documents_storage [--dry-run]

Опции:
    --dry-run    Показать, что будет сделано, но не выполнять действия
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from filer.models import File
from documents.models import Document
import os
import shutil


class Command(BaseCommand):
    help = 'Мигрирует файлы документов из старой структуры в новую'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать план миграции без выполнения',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 Режим DRY-RUN - изменения не будут применены'))
        
        # Получаем все файлы из filer
        files = File.objects.all().select_related('folder')
        total = files.count()
        
        self.stdout.write(f'\n📊 Найдено файлов в filer: {total}')
        
        if total == 0:
            self.stdout.write(self.style.WARNING('Нет файлов для миграции'))
            return
        
        # Статистика
        migrated = 0
        skipped = 0
        errors = 0
        
        for i, file in enumerate(files, 1):
            try:
                old_path = file.file.path if file.file else None
                
                if not old_path or not os.path.exists(old_path):
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠️  [{i}/{total}] Пропущен: {file.original_filename} (файл не найден)')
                    )
                    skipped += 1
                    continue
                
                # Определяем, старая ли структура
                if 'filer_public' in old_path:
                    self.stdout.write(f'  🔄 [{i}/{total}] Миграция: {file.original_filename}')
                    
                    if not dry_run:
                        # Пересохраняем файл - filer автоматически переместит его в новую структуру
                        file.save()
                        
                    new_path = file.file.path if file.file else None
                    
                    if new_path:
                        self.stdout.write(
                            self.style.SUCCESS(f'       ✅ {os.path.basename(old_path)} -> {os.path.relpath(new_path, settings.MEDIA_ROOT)}')
                        )
                    
                    migrated += 1
                else:
                    # Файл уже в новой структуре
                    skipped += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ [{i}/{total}] Ошибка при миграции {file.original_filename}: {e}')
                )
                errors += 1
        
        # Итоги
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS(f'✅ Мигрировано: {migrated}'))
        self.stdout.write(self.style.WARNING(f'⚠️  Пропущено: {skipped}'))
        
        if errors > 0:
            self.stdout.write(self.style.ERROR(f'❌ Ошибок: {errors}'))
        
        self.stdout.write('='*80)
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\n💡 Это был DRY-RUN. Для применения запустите без --dry-run')
            )
        else:
            self.stdout.write('\n💾 Миграция завершена!')
            self.stdout.write('\n📁 Старую папку filer_public/ можно удалить:')
            self.stdout.write(f'   rm -rf {os.path.join(settings.MEDIA_ROOT, "filer_public")}')
