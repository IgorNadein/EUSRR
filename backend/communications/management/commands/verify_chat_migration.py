"""
Команда для проверки корректности миграции модели Chat.

Использование:
    python manage.py verify_chat_migration
    
Проверяет:
1. Миграцию department FK → context_object GFK
2. Миграцию is_main Boolean → flags['is_primary'] JSON
3. Переименование include_all_employees → include_all_users
"""

from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from communications.models import Chat


class Command(BaseCommand):
    help = 'Verify Chat migration: old fields → new fields'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information for each chat',
        )

    def handle(self, *args, **options):
        verbose = options.get('verbose', False)
        
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.HTTP_INFO("ПРОВЕРКА МИГРАЦИИ МОДЕЛИ CHAT"))
        self.stdout.write("=" * 70 + "\n")
        
        errors = []
        warnings = []
        
        # ===== 1. Проверка department → context_object =====
        self.stdout.write(self.style.HTTP_INFO(
            "1. Проверка миграции department → context_object..."
        ))
        
        # Проверяем наличие старого поля (может быть удалено)
        has_department_field = hasattr(Chat, 'department')
        
        if has_department_field:
            from employees.models import Department
            dept_ct = ContentType.objects.get_for_model(Department)
            chats_with_dept = Chat.objects.filter(department__isnull=False)
            count_dept = chats_with_dept.count()
            
            self.stdout.write(f"   Найдено чатов с department: {count_dept}")
            
            for chat in chats_with_dept:
                # Проверяем что context заполнен
                if not chat.context_object_id:
                    errors.append(
                        f"Chat #{chat.id}: есть department но context_object_id is NULL"
                    )
                elif chat.context_object_id != chat.department_id:
                    errors.append(
                        f"Chat #{chat.id}: context_object_id ({chat.context_object_id}) "
                        f"!= department_id ({chat.department_id})"
                    )
                elif chat.context_content_type_id != dept_ct.id:
                    errors.append(
                        f"Chat #{chat.id}: context_content_type не Department"
                    )
                elif verbose:
                    self.stdout.write(
                        f"   ✓ Chat #{chat.id}: department={chat.department_id} "
                        f"→ context={chat.context_object_id}"
                    )
            
            if not errors and count_dept > 0:
                self.stdout.write(self.style.SUCCESS(
                    f"   ✓ Все {count_dept} чатов с department мигрированы корректно"
                ))
            elif count_dept == 0:
                self.stdout.write(self.style.WARNING(
                    "   ⚠ Чатов с department не найдено"
                ))
        else:
            # Поле department удалено - проверяем только context
            chats_with_context = Chat.objects.filter(
                context_content_type__isnull=False,
                context_object_id__isnull=False
            ).count()
            self.stdout.write(self.style.SUCCESS(
                f"   ✓ Поле 'department' удалено, чатов с context: {chats_with_context}"
            ))
        
        # ===== 2. Проверка is_main → flags['is_primary'] =====
        self.stdout.write("\n" + self.style.HTTP_INFO(
            "2. Проверка миграции is_main → flags['is_primary']..."
        ))
        
        has_is_main_field = hasattr(Chat, 'is_main')
        
        if has_is_main_field:
            main_chats = Chat.objects.filter(is_main=True)
            count_main = main_chats.count()
            
            self.stdout.write(f"   Найдено главных чатов (is_main=True): {count_main}")
            
            for chat in main_chats:
                flags_primary = chat.flags.get('is_primary') if chat.flags else False
                
                if not flags_primary:
                    errors.append(
                        f"Chat #{chat.id}: is_main=True но flags['is_primary'] не установлен"
                    )
                elif verbose:
                    self.stdout.write(
                        f"   ✓ Chat #{chat.id}: is_main=True → flags['is_primary']=True"
                    )
            
            if not errors and count_main > 0:
                self.stdout.write(self.style.SUCCESS(
                    f"   ✓ Все {count_main} главных чатов мигрированы в flags корректно"
                ))
            elif count_main == 0:
                self.stdout.write(self.style.WARNING(
                    "   ⚠ Главных чатов не найдено"
                ))
        else:
            # Поле is_main удалено - проверяем только flags
            chats_with_primary = Chat.objects.filter(
                flags__is_primary=True
            ).count()
            self.stdout.write(self.style.SUCCESS(
                f"   ✓ Поле 'is_main' удалено, чатов с flags.is_primary: {chats_with_primary}"
            ))
        
        # ===== 3. Проверка include_all_users =====
        self.stdout.write("\n" + self.style.HTTP_INFO(
            "3. Проверка поля include_all_users..."
        ))
        
        has_old_field = hasattr(Chat, 'include_all_employees')
        has_new_field = hasattr(Chat, 'include_all_users')
        
        if has_old_field and not has_new_field:
            warnings.append("Поле 'include_all_employees' еще не переименовано")
            count = Chat.objects.filter(include_all_employees=True).count()
            self.stdout.write(self.style.WARNING(
                f"   ⚠ Старое поле 'include_all_employees' существует, чатов: {count}"
            ))
        elif has_new_field:
            count = Chat.objects.filter(include_all_users=True).count()
            self.stdout.write(self.style.SUCCESS(
                f"   ✓ Поле 'include_all_users' существует, чатов использующих: {count}"
            ))
        else:
            errors.append("Ни 'include_all_employees' ни 'include_all_users' не найдены!")
        
        # ===== 4. Общая статистика =====
        self.stdout.write("\n" + self.style.HTTP_INFO("4. Общая статистика..."))
        
        total = Chat.objects.count()
        with_context = Chat.objects.filter(
            context_content_type__isnull=False
        ).count()
        with_flags_primary = Chat.objects.filter(
            flags__is_primary=True
        ).count()
        
        self.stdout.write(f"   Всего чатов: {total}")
        self.stdout.write(f"   С context_object: {with_context}")
        self.stdout.write(f"   С flags.is_primary: {with_flags_primary}")
        
        # ===== ИТОГОВЫЙ ОТЧЕТ =====
        self.stdout.write("\n" + "=" * 70)
        
        if errors:
            self.stdout.write(self.style.ERROR(f"❌ ОШИБОК: {len(errors)}"))
            for error in errors:
                self.stdout.write(self.style.ERROR(f"  • {error}"))
            result_code = 1
        else:
            self.stdout.write(self.style.SUCCESS("✅ ОШИБОК НЕ ОБНАРУЖЕНО"))
            result_code = 0
        
        if warnings:
            self.stdout.write("\n" + self.style.WARNING(f"⚠️  ПРЕДУПРЕЖДЕНИЙ: {len(warnings)}"))
            for warning in warnings:
                self.stdout.write(self.style.WARNING(f"  • {warning}"))
        
        self.stdout.write("=" * 70 + "\n")
        
        if result_code == 0:
            self.stdout.write(self.style.SUCCESS(
                "✅ Миграция выполнена корректно! Данные не потеряны."
            ))
        else:
            self.stdout.write(self.style.ERROR(
                "❌ Обнаружены проблемы при миграции. Проверьте ошибки выше."
            ))
        
        return result_code
