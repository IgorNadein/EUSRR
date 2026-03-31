"""
Monkey patch для django-scheduler: исправление бага с byweekday.

ПРОБЛЕМА:
---------
Когда событие создается в день, который входит в byweekday,
django-scheduler заменяет весь массив byweekday на только этот день.

ПРИМЕР БАГА:
- Создаем событие в пятницу (weekday = 4)
- Выбираем byweekday = [1, 4] (вторник и пятница)
- django-scheduler видит: 4 in [1, 4] = True
- Результат: event_params['byweekday'] = [4] вместо [1, 4]
- События создаются только в пятницу, вторник игнорируется

КОД БАГА (schedule/models/events.py, строки 375-378):
    if sp == rule_params[param] or (
        hasattr(rule_params[param], "__iter__") and sp in rule_params[param]
    ):
        event_params[param] = [sp]  # ← БАГ!

РЕШЕНИЕ:
--------
Переопределяем Event._event_params() с исправленной логикой для byweekday.
Используем ленивый импорт чтобы избежать проблем с порядком загрузки Django.
"""
import logging

logger = logging.getLogger(__name__)


def create_patched_method():
    """Создаёт пропатченный метод с ленивым импортом констант."""
    # Ленивый импорт - только при создании метода
    from schedule.models.events import freq_dict_order, param_dict_order

    def patched_event_params(self):
        """
        Исправленная версия Event._event_params().

        Для byweekday с несколькими днями НЕ заменяем массив,
        если день начала входит в него.
        """
        freq_order = freq_dict_order[self.rule.frequency]
        rule_params = self.event_rule_params
        start_params = self.event_start_params
        event_params = {}

        if len(rule_params) == 0:
            return event_params

        for param in rule_params:
            if (
                param in param_dict_order
                and param_dict_order[param] > freq_order
                and param in start_params
            ):
                sp = start_params[param]

                # ИСПРАВЛЕНИЕ: Для byweekday не заменяем массив
                if (param == 'byweekday' and
                        hasattr(rule_params[param], "__iter__")):
                    event_params[param] = rule_params[param]
                elif (sp == rule_params[param] or
                      (hasattr(rule_params[param], "__iter__") and
                       sp in rule_params[param])):
                    event_params[param] = [sp]
                else:
                    event_params[param] = rule_params[param]
            else:
                event_params[param] = rule_params[param]

        return event_params

    return patched_event_params


# Флаг для предотвращения повторного применения патча
_patch_applied = False


def apply_patch():
    """Применяет патч к django-scheduler Event модели."""
    global _patch_applied

    # Если патч уже применён, пропускаем
    if _patch_applied:
        return True

    try:
        # Ленивый импорт - только при вызове apply_patch()
        from schedule.models import Event

        print("=" * 80)
        print("✅ ПРИМЕНЕНИЕ ПАТЧА django-scheduler")

        # Создаём и применяем пропатченный метод
        patched_method = create_patched_method()
        Event._event_params = patched_method

        print(
            f"   Патч применён: Event._event_params = "
            f"{patched_method.__name__}"
        )
        print("=" * 80)

        _patch_applied = True
        return True
    except Exception as e:
        print("=" * 80)
        print(f"❌ ОШИБКА применения патча: {e}")
        logger.error(f"Ошибка применения патча: {e}", exc_info=True)
        print("=" * 80)
        return False
