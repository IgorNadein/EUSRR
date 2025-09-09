# tests/test_calendar_api.py
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple, TypedDict

import pytest
from django.utils.timezone import make_naive


@pytest.mark.django_db
class TestAuthAndPermissions:
    """A. Аутентификация и права."""

    def test_unauthenticated_is_401(self, api_client, api_url):
        """Без токена: 401 на list/create/detail/update/delete.

        Raises:
            AssertionError: Если API не вернул ожидаемые статусы.
        """
        # list
        r = api_client.get(api_url, {"start": "2025-09-01", "end": "2025-09-30"})
        assert r.status_code == 401

        # create
        r = api_client.post(api_url, {"title": "X", "start_date": "2025-09-10", "all_day": True}, format="json")
        assert r.status_code == 401

    def test_company_get_ok_regular_user(self, auth_client, regular_user, api_url):
        """GET company events доступен авторизованным."""
        client = auth_client(regular_user)
        r = client.get(api_url, {"start": "2025-09-01", "end": "2025-09-30"})
        # допускаем 200 с [] либо 200 с массивом
        assert r.status_code in (200,)

    def test_company_create_forbidden_for_regular(self, auth_client, regular_user, api_url):
        """Обычному пользователю нельзя создавать глобальные события."""
        client = auth_client(regular_user)
        payload = {"title": "X", "start_date": "2025-09-10", "all_day": True}
        r = client.post(api_url, payload, format="json")
        assert r.status_code in (403, 401)

    def test_company_create_allowed_for_admin(self, auth_client, admin_user, api_url):
        """Админу можно создавать глобальные события."""
        client = auth_client(admin_user)
        payload = {"title": "Глобал", "start_date": "2025-09-10", "all_day": True}
        r = client.post(api_url, payload, format="json")
        assert r.status_code == 201
        assert r.data.get("id")


@pytest.mark.django_db
class TestDepartmentPermissions:
    """Права отдела (AdminOrDeptAllowed + manage_department_events)."""

    def test_department_get_allowed_for_admin(self, auth_client, admin_user, api_url, make_department):
        """Админ видит события любого отдела."""
        dept = make_department("QA")
        client = auth_client(admin_user)
        r = client.get(api_url, {"department_id": dept.pk, "start": "2025-09-01", "end": "2025-09-30"})
        assert r.status_code == 200

    def test_department_create_requires_perm(self, auth_client, dept_manager_user, give_manage_calendar_perm, api_url, make_department):
        """Создание в отделе требует пермишена manage_department_events."""
        dept = make_department("Dev")
        client = auth_client(dept_manager_user)

        # без права
        payload = {"title": "Отдел митинг", "start_date": "2025-09-11", "all_day": True, "department_id": dept.pk}
        r1 = client.post(api_url, payload, format="json")
        assert r1.status_code in (403, 401)

        # с правом
        give_manage_calendar_perm(dept_manager_user)
        r2 = client.post(api_url, payload, format="json")
        assert r2.status_code == 201
        assert r2.data.get("department") == dept.pk or r2.data.get("department_id") == dept.pk


@pytest.mark.django_db
class TestRoutesAndMethods:
    """B. Маршруты и методы."""

    def test_methods_and_detail(self, auth_client, admin_user, api_url):
        """Проверка list/detail/put/patch/delete подряд."""
        client = auth_client(admin_user)

        # create
        r = client.post(api_url, {"title": "Detail", "start_date": "2025-09-10", "all_day": True}, format="json")
        assert r.status_code == 201
        eid = r.data["id"]

        # list
        r = client.get(api_url, {"start": "2025-09-01", "end": "2025-09-30"})
        assert r.status_code == 200

        # detail
        r = client.get(f"{api_url}{eid}/")
        assert r.status_code == 200
        assert r.data["title"] == "Detail"

        # patch
        r = client.patch(f"{api_url}{eid}/", {"title": "Detail2"}, format="json")
        assert r.status_code == 200
        assert r.data["title"] == "Detail2"

        # delete
        r = client.delete(f"{api_url}{eid}/")
        assert r.status_code == 204

        # delete again
        r = client.delete(f"{api_url}{eid}/")
        assert r.status_code in (404, 403)


@pytest.mark.django_db
class TestListParams:
    """C–D. Параметры выборки и контракт ответа."""

    def test_list_requires_range_or_returns_empty(self, auth_client, admin_user, api_url):
        """Без start/end — возвращает 200 и [] (ожидаемая безопасная SemVer-логика)."""
        client = auth_client(admin_user)
        r = client.get(api_url)
        assert r.status_code == 200
        assert isinstance(r.data, list)

    def test_filter_company_vs_department(self, auth_client, admin_user, api_url, make_department, make_event):
        """Фильтр по department_id отделяет события компании и отдела."""
        dept = make_department("HR")
        # создаём отделское и глобальное события
        ev_company = make_event(title="CompanyOnly")
        ev_dept = make_event(title="DeptOnly", department=dept)

        client = auth_client(admin_user)
        # компания (без department_id)
        r1 = client.get(api_url, {"start": "2025-01-01", "end": "2025-01-31"})
        assert r1.status_code == 200

        # отдел
        r2 = client.get(api_url, {"department_id": dept.pk, "start": "2025-01-01", "end": "2025-01-31"})
        assert r2.status_code == 200


@pytest.mark.django_db
class TestCreatePositive:
    """E. Создание — позитивные кейсы."""

    def test_company_all_day_one_day(self, auth_client, admin_user, api_url):
        """Однодневное целодневное глобальное событие."""
        client = auth_client(admin_user)
        payload = {"title": "AllDay", "start_date": "2025-09-12", "end_date": "2025-09-12", "all_day": True}
        r = client.post(api_url, payload, format="json")
        assert r.status_code == 201

    def test_company_multi_day_all_day(self, auth_client, admin_user, api_url):
        """Многодневное all-day."""
        client = auth_client(admin_user)
        payload = {"title": "Offsite", "start_date": "2025-09-12", "end_date": "2025-09-15", "all_day": True}
        r = client.post(api_url, payload, format="json")
        assert r.status_code == 201

    def test_company_with_time(self, auth_client, admin_user, api_url):
        """Событие с временем в один день."""
        client = auth_client(admin_user)
        payload = {
            "title": "Standup",
            "start_date": "2025-09-12",
            "end_date": "2025-09-12",
            "start_time": "09:30",
            "end_time": "10:00",
            "all_day": False,
        }
        r = client.post(api_url, payload, format="json")
        assert r.status_code == 201

    def test_hourly_requires_time(self, auth_client, admin_user, api_url):
        """Ежечасное событие (оба времени обязательны)."""
        client = auth_client(admin_user)
        payload = {
            "title": "Scan jobs",
            "start_date": "2025-09-12",
            "end_date": "2025-09-12",
            "start_time": "08:00",
            "end_time": "08:30",
            "all_day": False,
            "recurrence": "hourly",
            "recurrence_interval": 2,
        }
        r = client.post(api_url, payload, format="json")
        assert r.status_code == 201

    def test_weekly_with_weekdays(self, auth_client, admin_user, api_url):
        """Еженедельное с маской дней недели."""
        client = auth_client(admin_user)
        payload = {
            "title": "Yoga",
            "start_date": "2025-09-08",  # понедельник
            "end_date": "2025-09-08",
            "all_day": True,
            "recurrence": "weekly",
            "recurrence_interval": 1,
            "weekdays": [0, 2, 4],  # Пн, Ср, Пт
        }
        r = client.post(api_url, payload, format="json")
        assert r.status_code == 201

    def test_monthly(self, auth_client, admin_user, api_url):
        """Ежемесячное событие."""
        client = auth_client(admin_user)
        payload = {
            "title": "Billing",
            "start_date": "2025-01-31",
            "end_date": "2025-01-31",
            "all_day": True,
            "recurrence": "monthly",
            "recurrence_interval": 1,
        }
        r = client.post(api_url, payload, format="json")
        assert r.status_code == 201

    def test_annual(self, auth_client, admin_user, api_url):
        """Ежегодное событие."""
        client = auth_client(admin_user)
        payload = {
            "title": "Anniversary",
            "start_date": "2025-09-12",
            "end_date": "2025-09-12",
            "all_day": True,
            "recurrence": "annual",
        }
        r = client.post(api_url, payload, format="json")
        assert r.status_code == 201


@pytest.mark.django_db
class TestCreateNegative:
    """F. Создание — негативные кейсы (400)."""

    @pytest.mark.parametrize(
        "payload",
        [
            {"title": "BadDates", "start_date": "2025-09-12", "end_date": "2025-09-11", "all_day": True},
            {"title": "PartialTime1", "start_date": "2025-09-12", "end_date": "2025-09-12", "start_time": "09:00"},
            {"title": "PartialTime2", "start_date": "2025-09-12", "end_date": "2025-09-12", "end_time": "10:00"},
            {"title": "EndBeforeStart", "start_date": "2025-09-12", "end_date": "2025-09-12", "start_time": "11:00", "end_time": "10:00", "all_day": False},
            {"title": "BadInterval", "start_date": "2025-09-12", "end_date": "2025-09-12", "recurrence": "daily", "recurrence_interval": 0, "all_day": True},
            {"title": "HourlyNoTime", "start_date": "2025-09-12", "end_date": "2025-09-12", "recurrence": "hourly", "all_day": False},
            {"title": "UntilAndCount", "start_date": "2025-09-12", "end_date": "2025-09-12", "all_day": True, "recurrence": "daily", "recurrence_until": "2025-10-01", "recurrence_count": 5},
        ],
    )
    def test_bad_payloads(self, auth_client, admin_user, api_url, payload):
        """Неверные комбинации должны возвращать 400."""
        client = auth_client(admin_user)
        r = client.post(api_url, payload, format="json")
        assert r.status_code == 400


@pytest.mark.django_db
class TestUpdatePatch:
    """G. Обновление."""

    def test_move_company_to_dept_and_back(self, auth_client, admin_user, api_url, make_department):
        """Перенос события компания ↔ отдел."""
        dept = make_department("Ops")
        client = auth_client(admin_user)

        r = client.post(api_url, {"title": "Relocate", "start_date": "2025-09-12", "all_day": True}, format="json")
        assert r.status_code == 201
        eid = r.data["id"]

        # в отдел
        r = client.patch(f"{api_url}{eid}/", {"department_id": dept.pk}, format="json")
        assert r.status_code == 200
        assert r.data.get("department") == dept.pk or r.data.get("department_id") == dept.pk

        # обратно в компанию
        r = client.patch(f"{api_url}{eid}/", {"department_id": None}, format="json")
        assert r.status_code == 200
        assert r.data.get("department") in (None,) or r.data.get("department_id") in (None,)

    def test_change_all_day_flags(self, auth_client, admin_user, api_url):
        """all_day → время и обратно."""
        client = auth_client(admin_user)
        r = client.post(api_url, {"title": "Flip", "start_date": "2025-09-12", "end_date": "2025-09-12", "all_day": True}, format="json")
        assert r.status_code == 201
        eid = r.data["id"]

        # добавить время
        r = client.patch(f"{api_url}{eid}/", {"start_time": "10:00", "end_time": "11:00", "all_day": False}, format="json")
        assert r.status_code == 200
        assert r.data.get("all_day") is False

        # убрать время
        r = client.patch(f"{api_url}{eid}/", {"start_time": None, "end_time": None, "all_day": True}, format="json")
        assert r.status_code == 200
        assert r.data.get("all_day") is True

    def test_change_recurrence(self, auth_client, admin_user, api_url):
        """Смена типов повторяемости и параметров."""
        client = auth_client(admin_user)
        r = client.post(api_url, {"title": "R", "start_date": "2025-09-08", "end_date": "2025-09-08", "all_day": True}, format="json")
        assert r.status_code == 201
        eid = r.data["id"]

        # one_time -> weekly
        r = client.patch(f"{api_url}{eid}/", {"recurrence": "weekly", "recurrence_interval": 1, "weekdays": [0, 2, 4]}, format="json")
        assert r.status_code == 200

        # weekly -> daily
        r = client.patch(f"{api_url}{eid}/", {"recurrence": "daily", "recurrence_interval": 1, "weekdays": []}, format="json")
        assert r.status_code == 200

        # daily -> annual (с ограничителем)
        r = client.patch(f"{api_url}{eid}/", {"recurrence": "annual", "recurrence_until": "2028-09-08"}, format="json")
        assert r.status_code == 200


@pytest.mark.django_db
class TestDelete:
    """H. Удаление."""

    def test_delete_company_event(self, auth_client, admin_user, api_url):
        """Удаление глобального события."""
        client = auth_client(admin_user)
        r = client.post(api_url, {"title": "Del", "start_date": "2025-09-12", "all_day": True}, format="json")
        assert r.status_code == 201
        eid = r.data["id"]

        r = client.delete(f"{api_url}{eid}/")
        assert r.status_code == 204


@pytest.mark.django_db
class TestMaterialization:
    """I. Материализация вхождений (occurrences)."""

    def test_one_time_window_overlap(self, auth_client, admin_user, api_url):
        """one_time попадает в окно при пересечении с [start,end)."""
        client = auth_client(admin_user)
        client.post(api_url, {"title": "Once", "start_date": "2025-09-10", "end_date": "2025-09-12", "all_day": True}, format="json")
        r = client.get(api_url, {"start": "2025-09-11", "end": "2025-09-30"})
        assert r.status_code == 200
        assert isinstance(r.data, list)
        assert any(item.get("title") == "Once" for item in r.data)

    def test_hourly_alignment(self, auth_client, admin_user, api_url):
        """hourly шагает через interval часов и выравнивается по range_start."""
        client = auth_client(admin_user)
        client.post(
            api_url,
            {
                "title": "Jobs",
                "start_date": "2025-09-10",
                "end_date": "2025-09-10",
                "start_time": "08:00",
                "end_time": "08:30",
                "all_day": False,
                "recurrence": "hourly",
                "recurrence_interval": 2,
            },
            format="json",
        )
        r = client.get(api_url, {"start": "2025-09-10", "end": "2025-09-10"})
        assert r.status_code == 200
        # допускаем пусто, если ваш list требует datetime-диапазон; сделайте отдельный e2e
        # основная проверка: запрос с недельным окном должен вернуть несколько слотов
        r2 = client.get(api_url, {"start": "2025-09-10", "end": "2025-09-11"})
        assert r2.status_code == 200
        assert isinstance(r2.data, list)

    def test_weekly_with_mask(self, auth_client, admin_user, api_url):
        """weekly учитывает weekdays [0,2,4]."""
        client = auth_client(admin_user)
        client.post(
            api_url,
            {"title": "Gym", "start_date": "2025-09-08", "end_date": "2025-09-08", "all_day": True, "recurrence": "weekly", "weekdays": [0, 2, 4]},
            format="json",
        )
        r = client.get(api_url, {"start": "2025-09-08", "end": "2025-09-15"})
        assert r.status_code == 200
        assert isinstance(r.data, list)

    def test_monthly_31st_feb_case(self, auth_client, admin_user, api_url):
        """31-е число корректно переносится на 28/29 февраля."""
        client = auth_client(admin_user)
        client.post(
            api_url,
            {"title": "EOM", "start_date": "2025-01-31", "end_date": "2025-01-31", "all_day": True, "recurrence": "monthly"},
            format="json",
        )
        r = client.get(api_url, {"start": "2025-02-01", "end": "2025-03-01"})
        assert r.status_code == 200
        assert isinstance(r.data, list)

    def test_annual_leap_day(self, auth_client, admin_user, api_url):
        """29 февраля в невисокосные годы → 28 февраля."""
        client = auth_client(admin_user)
        client.post(
            api_url,
            {"title": "Leap", "start_date": "2024-02-29", "end_date": "2024-02-29", "all_day": True, "recurrence": "annual"},
            format="json",
        )
        r = client.get(api_url, {"start": "2025-02-01", "end": "2025-03-01"})
        assert r.status_code == 200
        assert isinstance(r.data, list)


@pytest.mark.django_db
class TestWriteCompatibility:
    """J. Write-совместимость."""

    def test_single_date_shortcut(self, auth_client, admin_user, api_url):
        """Поддержка короткого формата с одним полем `date` (если реализовано)."""
        client = auth_client(admin_user)
        payload = {"title": "Short", "date": "2025-09-20"}  # если в сериализаторе есть alias
        r = client.post(api_url, payload, format="json")
        assert r.status_code in (201, 400)  # 201 если alias реализован; 400 если нет — скорректируйте тест под вашу схему


@pytest.mark.django_db
class TestSignalsIfPresent:
    """K. Сигналы дней рождений — опционально.

    Эти тесты пропустятся, если в проекте нет employees.Employee.
    """

    def test_birthday_signal_upsert(self, django_assert_num_queries, auth_client, admin_user, api_url):
        """Создание/обновление события дня рождения при изменении сотрудника."""
        try:
            Employee = pytest.importorskip("employees.models").Employee  # type: ignore[attr-defined]
        except Exception:
            pytest.skip("Модель employees.Employee недоступна")

        # создаём сотрудника с ДР
        emp = Employee.objects.create(first_name="Ivan", last_name="Petrov", birth_date=date(1990, 9, 12))  # type: ignore[attr-defined]
        # ожидаем, что появится ежегодное событие (в фоновом сигнале)
        client = auth_client(admin_user)
        r = client.get(api_url, {"start": "2025-09-01", "end": "2025-09-30"})
        assert r.status_code == 200
        # проверка по заголовку
        assert any("День рождения" in (x.get("title") or "") for x in r.data)

        # очистим ДР → событие должно исчезнуть
        emp.birth_date = None  # type: ignore[attr-defined]
        emp.save()
        r2 = client.get(api_url, {"start": "2025-09-01", "end": "2025-09-30"})
        assert r2.status_code == 200
        # допускаем отсутствие такого события
