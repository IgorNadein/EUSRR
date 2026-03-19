# employees/apps.py
from django.apps import AppConfig


class EmployeesConfig(AppConfig):
    name = 'employees'

    def ready(self):
        import employees.signals  # Все сигналы (common, birthday, ldap)
        import employees.rules    # django-rules: регистрация предикатов и правил доступа
        
        # Патч для django-ldapdb: исправление бага с Value(1) в .exists()
        self._patch_ldapdb_compiler()
    
    def _patch_ldapdb_compiler(self):
        """Патчит django-ldapdb для поддержки Value выражений.
        
        Проблема: ldapdb компилятор на строке 246 вызывает e[0].field.attname,
        но у полей из Value() выражений (например, от .exists()) нет attname.
        
        Это приводит к: AttributeError: 'IntegerField' object has no attribute 'attname'
        
        Решение: Патчим results_iter чтобы безопасно проверять наличие attname.
        """
        try:
            from ldapdb.backends.ldap.compiler import SQLCompiler
            from django.db.models import aggregates
            from ldapdb.models.fields import ListField
            
            original_results_iter = SQLCompiler.results_iter
            
            def patched_results_iter(self, *args, **kwargs):
                """Исправленная версия results_iter с поддержкой Value выражений."""
                # Вызываем оригинальный генератор, но оборачиваем в try-catch
                for result in original_results_iter(self, *args, **kwargs):
                    yield result
            
            # Заменяем весь метод для правильной обработки
            import ldap
            from django.db.models.sql.constants import GET_ITERATOR_CHUNK_SIZE
            
            def safe_results_iter(self, results=None, do_slice=True):
                """Безопасная версия results_iter с проверкой attname."""
                if results is None:
                    results = self.execute_sql(
                        result_type='multi', chunked_fetch=False,
                        chunk_size=GET_ITERATOR_CHUNK_SIZE,
                    )
                
                if results is None:
                    return
                
                for dn, attrs in results:
                    row = []
                    self.setup_query()
                    for e in self.select:
                        if isinstance(e[0], aggregates.Count):
                            value = 0
                            input_field = e[0].get_source_expressions()[0].field
                            # Безопасная проверка attname
                            if getattr(input_field, 'attname', None) == 'dn':
                                value = 1
                            elif hasattr(input_field, 'from_ldap'):
                                result = input_field.from_ldap(
                                    attrs.get(input_field.db_column, []),
                                    connection=self.connection)
                                if result:
                                    value = 1
                                    if isinstance(input_field, ListField):
                                        value = len(result)
                            row.append(value)
                        else:
                            # Безопасная проверка attname с getattr
                            if getattr(e[0].field, 'attname', None) == 'dn':
                                row.append(dn)
                            elif hasattr(e[0].field, 'from_ldap'):
                                row.append(e[0].field.from_ldap(
                                    attrs.get(e[0].field.db_column, []),
                                    connection=self.connection))
                            else:
                                row.append(None)
                    
                    yield row
            
            SQLCompiler.results_iter = safe_results_iter
            
        except ImportError:
            # ldapdb не установлен - это нормально для тестов без LDAP
            pass
