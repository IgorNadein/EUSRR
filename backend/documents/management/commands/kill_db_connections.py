"""
Management команда для завершения всех соединений с базой данных
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings


class Command(BaseCommand):
    help = 'Завершает все активные соединения с базой данных (кроме текущего)'

    def handle(self, *args, **options):
        self.stdout.write('Завершение всех соединений с базой данных...')
        
        try:
            db_name = settings.DATABASES['default']['NAME']
            
            with connection.cursor() as cursor:
                # Получаем список всех активных соединений
                cursor.execute("""
                    SELECT pid, datname, usename, application_name, state
                    FROM pg_stat_activity
                    WHERE datname = %s AND pid <> pg_backend_pid()
                """, [db_name])
                
                connections = cursor.fetchall()
                
                if connections:
                    self.stdout.write(f'Найдено активных соединений: {len(connections)}')
                    for conn in connections:
                        self.stdout.write(f'  PID: {conn[0]}, User: {conn[2]}, App: {conn[3]}, State: {conn[4]}')
                    
                    # Завершаем все соединения
                    cursor.execute("""
                        SELECT pg_terminate_backend(pg_stat_activity.pid)
                        FROM pg_stat_activity
                        WHERE pg_stat_activity.datname = %s
                        AND pid <> pg_backend_pid()
                    """, [db_name])
                    
                    self.stdout.write(self.style.SUCCESS(f'\n✓ Завершено соединений: {len(connections)}'))
                else:
                    self.stdout.write(self.style.WARNING('Нет активных соединений кроме текущего'))
                
            self.stdout.write(self.style.SUCCESS('\nТеперь можно запустить: python manage.py migrate'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Ошибка: {e}'))
            raise
