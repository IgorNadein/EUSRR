from __future__ import annotations

import os
from typing import Any, Iterable, Optional

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.timezone import now
from employees.models import Department, Employee, EmployeeDepartment
from ldap3 import ALL, ALL_ATTRIBUTES, SUBTREE, Connection, Server

# Берём ваши утилиты нормализации телефона и имя поля телефона
try:
    from eusrr_backend.auth_backends import PHONE_FIELD  # type: ignore
    from eusrr_backend.auth_backends import _normalize_phone
except Exception:  # pragma: no cover

    def _normalize_phone(raw: str) -> Optional[str]:
        return str(raw).strip() if raw else None

    PHONE_FIELD = None


class Command(BaseCommand):
    """Синхронизация сотрудников (и отделов) из LDAP.

    Алгоритм:
        1) Соединяемся с LDAP, выполняем paged search по базе и фильтрам.
        2) Для каждой записи забираем атрибуты (email/ФИО/телефон/отдел).
        3) Сопоставляем с локальной БД:
            - по email (nocase), иначе по телефону (E.164, если есть поле).
        4) Создаём или обновляем Employee; отдел обновляем при наличии.
        5) (опц.) Деактивируем локальных, которых не нашли.

    Запуск:
        python manage.py sync_ldap --dry-run
        python manage.py sync_ldap --deactivate-missing
        python manage.py sync_ldap --filter "(|(departmentNumber=IT)(departmentNumber=HR))"

    Требуемые настройки:
        LDAP_URI, LDAP_USER_BASE, LDAP_USER_FILTER (либо передайте --filter)
        LDAP_BIND_DN/LDAP_BIND_PASSWORD (если требуется bind DN)
        LDAP_ATTR_MAIL, LDAP_ATTR_GIVENNAME, LDAP_ATTR_SN, LDAP_ATTR_PHONE
        LDAP_DEPT_ATTR (если нужен отдел)

    Raises:
        CommandError: при фатальных ошибках соединения/настроек.
    """

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Не писать в БД, только показать план синка.",
        )
        parser.add_argument(
            "--deactivate-missing",
            action="store_true",
            help="Деактивировать локальных сотрудников, отсутствующих в текущей выборке LDAP.",
        )
        parser.add_argument(
            "--filter",
            dest="filter",
            help="Переопределить LDAP фильтр (иначе возьмём LDAP_USER_FILTER + LDAP_ACTIVE_FILTER из настроек).",
        )
        parser.add_argument(
            "--base",
            dest="base",
            help="Переопределить LDAP base DN (иначе LDAP_USER_BASE).",
        )
        parser.add_argument(
            "--page-size",
            type=int,
            default=500,
            help="Размер страницы LDAP-поиска (по умолчанию 500).",
        )

    def handle(self, *args, **opts) -> None:
        """Точка входа команды.

        Args:
            *args: Не используются.
            **opts: Аргументы командной строки.

        Raises:
            CommandError: При неверной конфигурации или ошибке подключения.
        """
        dry_run: bool = bool(opts.get("dry_run"))
        deactivate_missing: bool = bool(opts.get("deactivate_missing"))
        page_size: int = int(opts.get("page_size") or 500)

        server_uri = os.getenv("LDAP_URI") or getattr(settings, "LDAP_URI", None)
        user_base = (
            opts.get("base")
            or os.getenv("LDAP_USER_BASE")
            or getattr(settings, "LDAP_USER_BASE", None)
        )
        filt = (
            opts.get("filter")
            or os.getenv("LDAP_USER_FILTER")
            or getattr(settings, "LDAP_USER_FILTER", "(uid=*)")
        )
        active_extra = os.getenv("LDAP_ACTIVE_FILTER") or getattr(
            settings, "LDAP_ACTIVE_FILTER", ""
        )

        if not server_uri or not user_base:
            raise CommandError("Не заданы LDAP_URI/LDAP_USER_BASE.")

        search_filter = self._combine_filters(filt, active_extra)

        self.stdout.write(
            self.style.NOTICE(
                f"[LDAP] base={user_base} filter={search_filter} page={page_size} dry={dry_run}"
            )
        )

        server = Server(server_uri, get_info=ALL)
        bind_dn = os.getenv("LDAP_BIND_DN") or getattr(settings, "LDAP_BIND_DN", "")
        bind_pw = os.getenv("LDAP_BIND_PASSWORD") or getattr(
            settings, "LDAP_BIND_PASSWORD", ""
        )

        try:
            conn = (
                Connection(server, user=bind_dn, password=bind_pw, auto_bind=True)
                if (bind_dn or bind_pw)
                else Connection(server, auto_bind=True)
            )
        except Exception as exc:
            raise CommandError(f"Не удалось подключиться к LDAP: {exc}") from exc

        entries = self._paged_search(
            conn, user_base, search_filter, page_size=page_size
        )
        self.stdout.write(self.style.NOTICE(f"[LDAP] получено записей: {len(entries)}"))

        if dry_run:
            self._simulate(entries)
            self.stdout.write(self.style.SUCCESS("[LDAP] сухой прогон завершён"))
            return

        with transaction.atomic():
            created, updated, seen_ids = self._sync(entries)
            if deactivate_missing and hasattr(Employee, "is_active"):
                qs = Employee.objects.filter(is_active=True).exclude(pk__in=seen_ids)
                if getattr(settings, "LDAP_DEACTIVATE_PROTECT_SUPERUSER", True):
                    qs = qs.exclude(is_superuser=True)
                deactivated = qs.update(is_active=False)
                self.stdout.write(
                    self.style.WARNING(
                        f"[LDAP] деактивировано отсутствующих: {deactivated}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"[LDAP] синк завершён: создано={created}, обновлено={updated}, всего_обработано={len(seen_ids)}"
            )
        )

    # ---------- helpers ----------

    @staticmethod
    def _combine_filters(main: str, extra: str) -> str:
        """Комбинирует два LDAP-фильтра AND-ом.

        Args:
            main (str): Основной фильтр (например, '(uid=*)').
            extra (str): Дополнительный фильтр (например, фильтр активности).

        Returns:
            str: Комбинированный фильтр.

        Raises:
            ValueError: Не бросает; пустые фильтры аккуратно обрабатываются.
        """
        m = (main or "").strip()
        e = (extra or "").strip()
        if m and e:
            # оба фильтра уже обрамлены скобками — просто «склеим»
            return f"(&{m}{e})"
        return m or e

    def _paged_search(
        self, conn: Connection, base: str, flt: str, *, page_size: int = 500
    ) -> list[Any]:
        """Выполняет постраничный поиск в LDAP.

        Args:
            conn (Connection): Открытое соединение ldap3.
            base (str): База поиска (DN).
            flt (str): LDAP-фильтр.
            page_size (int): Размер страницы.

        Returns:
            list[Any]: Список ldap3 entries.

        Raises:
            CommandError: При ошибке поиска.
        """
        results: list[Any] = []
        try:
            cookie = None
            while True:
                conn.search(
                    search_base=base,
                    search_filter=flt,
                    search_scope=SUBTREE,
                    attributes=ALL_ATTRIBUTES,
                    paged_size=page_size,
                    paged_cookie=cookie,
                )
                results.extend(conn.entries or [])
                cookie = (
                    conn.result.get("controls", {})
                    .get("1.2.840.113556.1.4.319", {})
                    .get("value", {})
                    .get("cookie")
                )
                if not cookie:
                    break
        except Exception as exc:
            raise CommandError(f"Ошибка LDAP-поиска: {exc}") from exc
        finally:
            try:
                conn.unbind()
            except Exception:
                pass
        return results

    @staticmethod
    def _attr(entry: Any, name: str) -> Optional[str]:
        """Возвращает строковое значение атрибута ldap3 Entry.

        Args:
            entry (Any): LDAP запись.
            name (str): Имя атрибута.

        Returns:
            Optional[str]: Значение или None.

        Raises:
            Ничего не бросает.
        """
        try:
            val = getattr(entry, name, None)
            raw = getattr(val, "value", None)
            if raw is None:
                return None
            if isinstance(raw, (list, tuple)):
                return str(raw[0]).strip() if raw else None
            return str(raw).strip()
        except Exception:
            return None

    def _simulate(self, entries: list[Any]) -> None:
        """Сухой прогон: показывает, кого создадим/обновим.

        Args:
            entries (list[Any]): Список записей LDAP.

        Raises:
            Ничего не бросает.
        """
        created = updated = skipped = 0
        for e in entries:
            email = (
                self._attr(
                    e,
                    os.getenv(
                        "LDAP_ATTR_MAIL", getattr(settings, "LDAP_ATTR_MAIL", "mail")
                    ),
                )
                or ""
            ).lower()
            given = (
                self._attr(
                    e,
                    os.getenv(
                        "LDAP_ATTR_GIVENNAME",
                        getattr(settings, "LDAP_ATTR_GIVENNAME", "givenName"),
                    ),
                )
                or ""
            )
            sn = (
                self._attr(
                    e,
                    os.getenv("LDAP_ATTR_SN", getattr(settings, "LDAP_ATTR_SN", "sn")),
                )
                or ""
            )
            phone_raw = self._attr(
                e,
                os.getenv(
                    "LDAP_ATTR_PHONE",
                    getattr(settings, "LDAP_ATTR_PHONE", "telephoneNumber"),
                ),
            )
            phone = _normalize_phone(phone_raw) if phone_raw else None

            user = None
            if email:
                user = Employee.objects.filter(email__iexact=email).first()
            if user is None and PHONE_FIELD and phone:
                user = Employee.objects.filter(**{PHONE_FIELD: phone}).first()

            if user:
                updated += 1
                self.stdout.write(f"[=] update {email or phone} → ({given} {sn})")
            else:
                # проверим, сможем ли создать (обязательные поля)
                can_create = bool(email or (PHONE_FIELD and phone))
                if can_create:
                    created += 1
                    self.stdout.write(f"[+] create {email or phone} → ({given} {sn})")
                else:
                    skipped += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"[~] skip (нет достаточных данных) DN={getattr(e, 'entry_dn', '')}"
                        )
                    )
        self.stdout.write(
            self.style.NOTICE(
                f"План: создать={created}, обновить={updated}, пропустить={skipped}"
            )
        )

    def _sync(self, entries: list[Any]) -> tuple[int, int, set[int]]:
        """Синхронизирует LDAP-записи в БД.

        Args:
            entries (list[Any]): Записи ldap3 Entry.

        Returns:
            tuple[int, int, set[int]]: Кол-во созданных, кол-во обновлённых, множество pk локальных пользователей, обработанных в этой выборке.

        Raises:
            ValueError: Не выбрасывается наружу — неконсистентные записи пропускаются.
        """
        created = updated = 0
        seen_ids: set[int] = set()

        for e in entries:
            mail_attr = os.getenv(
                "LDAP_ATTR_MAIL", getattr(settings, "LDAP_ATTR_MAIL", "mail")
            )
            given_attr = os.getenv(
                "LDAP_ATTR_GIVENNAME",
                getattr(settings, "LDAP_ATTR_GIVENNAME", "givenName"),
            )
            sn_attr = os.getenv("LDAP_ATTR_SN", getattr(settings, "LDAP_ATTR_SN", "sn"))
            phone_attr = os.getenv(
                "LDAP_ATTR_PHONE",
                getattr(settings, "LDAP_ATTR_PHONE", "telephoneNumber"),
            )
            dept_attr = os.getenv("LDAP_DEPT_ATTR")  # может быть пустым

            email = (self._attr(e, mail_attr) or "").lower()
            first_name = self._attr(e, given_attr) or ""
            last_name = self._attr(e, sn_attr) or ""
            phone_raw = self._attr(e, phone_attr)
            phone = _normalize_phone(phone_raw) if phone_raw else None



            # Ищем локального
            user: Optional[Employee] = None
            if email:
                user = Employee.objects.filter(email__iexact=email).first()
            if user is None and PHONE_FIELD and phone:
                user = Employee.objects.filter(**{PHONE_FIELD: phone}).first()

            # Если нет — проверим, сможем ли создать (обязательные поля)
            if user is None:
                if not (email or (PHONE_FIELD and phone)):
                    # не можем выполнить инварианты модели
                    self.stdout.write(
                        self.style.WARNING(
                            f"[~] skip create: нет email/телефона DN={getattr(e, 'entry_dn', '')}"
                        )
                    )
                    continue
                payload: dict[str, Any] = {}
                if hasattr(Employee, "email") and email:
                    payload["email"] = email
                if PHONE_FIELD and phone:
                    payload[PHONE_FIELD] = phone
                if hasattr(Employee, "first_name"):
                    payload["first_name"] = first_name
                if hasattr(Employee, "last_name"):
                    payload["last_name"] = last_name
                user = Employee(**payload)
                # LDAP-пользователям пароль локально не нужен
                if hasattr(user, "set_unusable_password"):
                    user.set_unusable_password()
                user.save()
                created += 1
            else:
                changed = False
                fields: list[str] = []
                if hasattr(user, "first_name") and user.first_name != first_name:
                    user.first_name = first_name
                    changed = True
                    fields.append("first_name")
                if hasattr(user, "last_name") and user.last_name != last_name:
                    user.last_name = last_name
                    changed = True
                    fields.append("last_name")
                if (
                    email
                    and hasattr(user, "email")
                    and (user.email or "").lower() != email
                ):
                    user.email = email
                    changed = True
                    fields.append("email")
                if PHONE_FIELD and phone and getattr(user, PHONE_FIELD, None) != phone:
                    setattr(user, PHONE_FIELD, phone)
                    changed = True
                    fields.append(PHONE_FIELD)
                if changed:
                    user.save(update_fields=list(set(fields)))
                    updated += 1

            # Отдел (если есть Department и LDAP_DEPT_ATTR)
            if Department and dept_attr:
                dept_val = self._attr(e, dept_attr)
                if dept_val:
                    self._assign_department(user, dept_val, e)
            if getattr(settings, "LDAP_SYNC_GROUPS", False):
                ldap_vals = self._multi_attr(e, getattr(settings, "LDAP_GROUP_ATTR", "memberOf"))
                mapping = (getattr(settings, "LDAP_GROUP_MAP", {}) or {})
                norm_map = {k.lower(): v.strip() for k, v in mapping.items() if v and k}
                wanted_names = {norm_map[v.lower()] for v in ldap_vals if v and v.lower() in norm_map}
                if wanted_names:
                    existing = set(user.groups.values_list("name", flat=True))
                    missing = [Group.objects.get_or_create(name=n)[0] for n in (wanted_names - existing)]
                    if getattr(settings, "LDAP_GROUPS_EXCLUSIVE", False):
                        # точный состав (создаём все требуемые)
                        all_needed = [Group.objects.get_or_create(name=n)[0] for n in wanted_names]
                        user.groups.set(all_needed)
                    elif missing:
                        user.groups.add(*missing)

            # помечаем обработанного пользователя
            seen_ids.add(user.pk)
            return created, updated, seen_ids

    def _assign_department(self, user: Employee, raw: str | Iterable[str], entry: Any | None = None) -> None:
        """Привязывает сотрудника к отделу(ам) на основе значения из LDAP.

        В вашем проекте:
        • Отдел — модель employees.models.Department с уникальным полем name.
        • Принадлежность — через employees.models.EmployeeDepartment (FK),
            а НЕ прямое поле у Employee.

        Поддержка форматов:
        1) Простое имя (например, "IT" или "Бухгалтерия") → name=raw.
        2) DN-строки (например, "CN=John,OU=IT,OU=RU,DC=example,DC=com"):
            извлекаем ближайший к записи OU (или, если OU нет, пробуем CN).
        3) Многозначные атрибуты/строки с разделителями — можно передать
            Iterable[str] или строку с разделителями ",", ";", "|".

        Логика привязки:
        • Создаём/находим Department(name=<извлечённое имя>).
        • Создаём/активируем EmployeeDepartment (is_active=True),
            если даты отсутствуют — проставляем date_from=today.
        • НИЧЕГО не деактивируем: синк не «вытесняет» другие отделы.

        Args:
            user (Employee): Сотрудник для привязки.
            raw (str | Iterable[str]): Значение(я) из LDAP (deptNumber/department/OU/DN).

        Raises:
            ValueError: Если user не задан.
        """
        import re
        from typing import Iterable as _Iter

        from django.utils import timezone

        if user is None:
            raise ValueError("user is required")

        # Универсальный нормализатор входа → список «имён отделов»
        def _to_names(val: str | _Iter[str]) -> list[str]:
            def _from_dn(s: str) -> str | None:
                # Ищем OU=... (самый ближний к записи); если нет — пробуем CN=...
                m = re.search(r"(?i)\bou=([^,]+)", s)
                if m:
                    return m.group(1).strip()
                m = re.search(r"(?i)\bcn=([^,]+)", s)
                if m:
                    return m.group(1).strip()
                return None

            out: list[str] = []
            parts: list[str]
            if isinstance(val, str):
                # если многозначное значение пришло одной строкой
                parts = re.split(r"[;,|]", val)
            else:
                parts = list(val)

            for p in parts:
                s = (p or "").strip()
                if not s:
                    continue
                # DN → извлекаем OU/CN; иначе берём как есть
                name = _from_dn(s) if ("=" in s and "," in s) else s
                if name:
                    out.append(name)
            # Убираем дубликаты, сохраняя порядок
            seen = set()
            uniq = []
            for n in out:
                if n not in seen:
                    uniq.append(n)
                    seen.add(n)
            return uniq

        names = _to_names(raw)
        if not names:
            return  # нечего привязывать

        today = timezone.now().date()

        for name in names:
            try:
                dept, _ = Department.objects.get_or_create(name=name)
            except Exception:
                # если вдруг уникальность нарушена или имя «битое» — пропускаем
                continue

            # Создаём/активируем линк сотрудника к отделу
            link, created = EmployeeDepartment.objects.get_or_create(
                employee_id=user.id,
                department_id=dept.id,
                defaults={"is_active": True, "date_from": today},
            )
            if not created:
                updates: dict[str, object] = {}
                if not getattr(link, "is_active", True):
                    updates["is_active"] = True
                if not getattr(link, "date_from", None):
                    updates["date_from"] = today
                if updates:
                    EmployeeDepartment.objects.filter(pk=link.pk).update(**updates)
            role_attr = os.getenv("LDAP_DEPT_ROLE_ATTR")
            if role_attr and entry is not None:
                role_name = (self._attr(entry, role_attr) or "").strip()
                if role_name:
                    from employees.models import DepartmentRole  # локальный импорт
                    role, _ = DepartmentRole.objects.get_or_create(
                        department=dept,
                        name=role_name,
                        defaults={"description": "", "is_active": True},
                    )
                    if link.role_id != role.id:
                        EmployeeDepartment.objects.filter(pk=link.pk).update(role=role)

    def _multi_attr(self, entry, name: str) -> list[str]:
        try:
            val = getattr(entry, name, None)
            raw = getattr(val, "values", None)
            if not raw:
                return []
            return [str(x).strip() for x in raw if str(x).strip()]
        except Exception:
            return []
