# employees/apps.py
import datetime

from django.apps import AppConfig
from django.conf import settings


def _ensure_ldapdb_timezone_compat():
    """Патч совместимости django-ldapdb 1.5.1 с Django 5.x.

    django-ldapdb использует ``timezone.utc.localize(...)`` (pytz API),
    но Django 5.x удалил ``django.utils.timezone.utc``.
    Пробрасываем обёртку вокруг ``datetime.timezone.utc``
    с методом ``localize``.
    """
    from django.utils import timezone

    if hasattr(timezone, "utc"):
        return

    class _Utc(datetime.tzinfo):
        """Минимальная обёртка, совместимая с pytz-интерфейсом (localize)."""

        ZERO = datetime.timedelta(0)

        def utcoffset(self, dt):
            return self.ZERO

        def tzname(self, dt):
            return "UTC"

        def dst(self, dt):
            return self.ZERO

        def localize(self, dt, is_dst=False):
            return dt.replace(tzinfo=datetime.timezone.utc)

    timezone.utc = _Utc()


class EmployeesConfig(AppConfig):
    name = "employees"

    def ready(self):

        if getattr(settings, "LDAP_WRITE_ENABLED", False):
            _ensure_ldapdb_timezone_compat()
            self._patch_ldapdb_compiler()

    def _patch_ldapdb_compiler(self):
        """Патчит django-ldapdb для поддержки Value выражений.

        Проблема: ldapdb компилятор в results_iter вызывает e[0].field.attname,
        но у полей из Value() выражений (например, от .exists()) нет attname.

        Решение: Патчим results_iter, заменяя прямые обращения к .attname
        на безопасный getattr(..., 'attname', None).
        """
        try:
            from ldapdb.backends.ldap.compiler import SQLCompiler
            from django.db.models import aggregates
            from ldapdb.models.fields import ListField

            original_results_iter = SQLCompiler.results_iter

            def safe_results_iter(
                self,
                results=None,
                tuple_expected=False,
                chunked_fetch=False,
                chunk_size=None,
            ):
                """Обёртка над original results_iter.

                Использует безопасную проверку attname.
                """
                import ldap as ldap_lib

                try:
                    yield from original_results_iter(
                        self,
                        results=results,
                        tuple_expected=tuple_expected,
                        chunked_fetch=chunked_fetch,
                        **(
                            {"chunk_size": chunk_size}
                            if chunk_size is not None
                            else {}
                        ),
                    )
                except ldap_lib.NO_SUCH_OBJECT:
                    # DN не существует — возвращаем пустой результат
                    # (django-ldapdb бросает ldap.NO_SUCH_OBJECT
                    # вместо DoesNotExist)
                    return
                except AttributeError as exc:
                    if "attname" not in str(exc):
                        raise
                    # Fallback: повторяем логику оригинала
                    # с безопасным getattr
                    yield from self._safe_results_iter_fallback()

            def _safe_results_iter_fallback(self):
                """Fallback-итератор с безопасными проверками attname."""
                import ldap as ldap_lib

                lookup = None
                try:
                    from ldapdb.backends.ldap.compiler import query_as_ldap

                    lookup = query_as_ldap(
                        self.query, compiler=self, connection=self.connection
                    )
                except Exception:
                    return

                if lookup is None:
                    return

                if len(self.query.select):
                    fields = [x.field for x in self.query.select]
                else:
                    fields = self.query.model._meta.fields

                attrlist = [x.db_column for x in fields if x.db_column]

                try:
                    vals = self.connection.search_s(
                        base=lookup.base,
                        scope=lookup.scope,
                        filterstr=lookup.filterstr,
                        attrlist=attrlist,
                    )
                except ldap_lib.NO_SUCH_OBJECT:
                    return

                # Слайсинг
                pos = 0
                for dn, attrs in vals:
                    if (self.query.low_mark and pos < self.query.low_mark) or (
                        self.query.high_mark is not None
                        and pos >= self.query.high_mark
                    ):
                        pos += 1
                        continue

                    row = []
                    self.setup_query()
                    for e in self.select:
                        if isinstance(e[0], aggregates.Count):
                            value = 0
                            input_field = e[0].get_source_expressions()[0].field
                            if getattr(input_field, "attname", None) == "dn":
                                value = 1
                            elif hasattr(input_field, "from_ldap"):
                                result = input_field.from_ldap(
                                    attrs.get(input_field.db_column, []),
                                    connection=self.connection,
                                )
                                if result:
                                    value = 1
                                    if isinstance(input_field, ListField):
                                        value = len(result)
                            row.append(value)
                        else:
                            if getattr(e[0].field, "attname", None) == "dn":
                                row.append(dn)
                            elif hasattr(e[0].field, "from_ldap"):
                                row.append(
                                    e[0].field.from_ldap(
                                        attrs.get(e[0].field.db_column, []),
                                        connection=self.connection,
                                    )
                                )
                            else:
                                row.append(None)
                    yield row
                    pos += 1

            SQLCompiler.results_iter = safe_results_iter
            SQLCompiler._safe_results_iter_fallback = (
                _safe_results_iter_fallback
            )

        except ImportError:
            # ldapdb не установлен - это нормально для тестов без LDAP
            pass
