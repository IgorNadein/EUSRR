"""
Management команда для очистки и оптимизации аватаров сотрудников.

Функции:
1. Удаление неиспользуемых файлов аватаров
2. Сжатие существующих аватаров до оптимального размера
"""

import os
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from employees.models import Employee
from common.image_utils import compress_avatar


class Command(BaseCommand):
    help = 'Очистка неиспользуемых аватаров и оптимизация существующих'

    def add_arguments(self, parser):
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Сжать существующие аватары',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Удалить неиспользуемые файлы',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без реального выполнения',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        do_compress = options['compress']
        do_cleanup = options['cleanup']

        # Если не указаны опции, делаем всё
        if not do_compress and not do_cleanup:
            do_compress = True
            do_cleanup = True

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    'РЕЖИМ ПРОСМОТРА - изменения не применяются'
                )
            )

        # Получаем все используемые файлы аватаров
        employees = Employee.objects.exclude(avatar='').exclude(avatar=None)
        used_files = set()
        
        for emp in employees:
            if emp.avatar:
                try:
                    used_files.add(os.path.basename(emp.avatar.path))
                except Exception:
                    pass

        self.stdout.write(
            f'Найдено {len(used_files)} используемых аватаров'
        )

        # Очистка неиспользуемых файлов
        if do_cleanup:
            self.stdout.write('\n=== ОЧИСТКА НЕИСПОЛЬЗУЕМЫХ ФАЙЛОВ ===')
            avatar_dir = os.path.join('media', 'users', 'avatars')
            
            if not os.path.exists(avatar_dir):
                self.stdout.write(
                    self.style.WARNING(f'Директория {avatar_dir} не найдена')
                )
            else:
                deleted_count = 0
                freed_mb = 0

                for filename in os.listdir(avatar_dir):
                    filepath = os.path.join(avatar_dir, filename)
                    
                    if not os.path.isfile(filepath):
                        continue
                    
                    if filename not in used_files:
                        size_mb = os.path.getsize(filepath) / (1024 * 1024)
                        freed_mb += size_mb
                        
                        self.stdout.write(
                            f'  Удаление: {filename} ({size_mb:.2f} MB)'
                        )
                        
                        if not dry_run:
                            try:
                                os.remove(filepath)
                                deleted_count += 1
                            except Exception as e:
                                self.stdout.write(
                                    self.style.ERROR(
                                        f'    Ошибка удаления: {e}'
                                    )
                                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nУдалено файлов: {deleted_count}, '
                        f'освобождено: {freed_mb:.2f} MB'
                    )
                )

        # Сжатие существующих аватаров
        if do_compress:
            self.stdout.write('\n=== СЖАТИЕ СУЩЕСТВУЮЩИХ АВАТАРОВ ===')
            compressed_count = 0
            saved_mb = 0

            for emp in employees:
                if not emp.avatar:
                    continue

                try:
                    original_path = emp.avatar.path
                    original_size = os.path.getsize(original_path)
                    
                    # Читаем оригинальный файл
                    with open(original_path, 'rb') as f:
                        original_data = f.read()
                    
                    # Сжимаем
                    compressed_data = compress_avatar(original_data)
                    compressed_size = len(compressed_data)
                    
                    # Проверяем, дало ли сжатие выигрыш
                    if compressed_size < original_size * 0.95:  # минимум 5%
                        size_diff = original_size - compressed_size
                        saved = size_diff / (1024 * 1024)
                        saved_mb += saved
                        
                        self.stdout.write(
                            f'  Сжатие: {emp.get_full_name()} '
                            f'({original_size/1024:.1f}KB → '
                            f'{compressed_size/1024:.1f}KB, '
                            f'экономия {saved*1024:.1f}KB)'
                        )
                        
                        if not dry_run:
                            # Сохраняем сжатый файл
                            filename = os.path.basename(original_path)
                            if not filename.lower().endswith('.jpg'):
                                filename = filename.rsplit('.', 1)[0] + '.jpg'
                            
                            emp.avatar.save(
                                filename,
                                ContentFile(compressed_data),
                                save=True
                            )
                            compressed_count += 1
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'  Ошибка сжатия для {emp.get_full_name()}: {e}'
                        )
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f'\nСжато файлов: {compressed_count}, '
                    f'сэкономлено: {saved_mb:.2f} MB'
                )
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\nДля применения изменений запустите без --dry-run'
                )
            )
