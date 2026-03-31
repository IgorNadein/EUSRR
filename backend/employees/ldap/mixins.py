"""Миксины для расширения функциональности django-ldapdb ORM моделей.

Этот модуль предоставляет дополнительные возможности для LDAP моделей,
которые не поддерживаются django-ldapdb из коробки.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ModifyDnMixin:
    """Миксин для поддержки перемещения LDAP объектов между OU через modify_dn.

    django-ldapdb не поддерживает перемещение объектов между OU из-за того,
    что метод connection.rename_s() не передаёт параметр newsuperior.

    Этот миксин добавляет эту функциональность, отслеживая изменения base_dn
    и выполняя low-level modify_dn операцию перед стандартным save().

    Usage:
        class LdapUser(ModifyDnMixin, LdapModel):
            # ... поля модели
            pass

        # Использование:
        user = LdapUser.objects.get(cn="User")
        user.base_dn = "OU=Dismissed,OU=company,DC=robotail,DC=local"
        user.save()  # Автоматически выполнит modify_dn!

    Attributes:
        _original_base_dn (str): Оригинальный base_dn при загрузке объекта.
            Используется для определения, нужно ли перемещение.
    """

    def __init__(self, *args, **kwargs):
        """Инициализация миксина с сохранением оригинального base_dn."""
        super().__init__(*args, **kwargs)
        # Сохраняем оригинальный base_dn для отслеживания изменений
        self._original_base_dn = getattr(self, "base_dn", None)
        # Сохраняем оригинальное значение RDN-атрибута (cn/ou)
        self._original_rdn_value = self._get_rdn_value()

    def _get_rdn_value(self):
        """Возвращает текущее значение RDN-атрибута (cn или ou)."""
        rdn_attrs = getattr(self, "rdn_attributes", [])
        for field in self._meta.fields:
            if field.db_column and field.db_column in rdn_attrs:
                return getattr(self, field.name, None)
        return None

    def _set_rdn_value(self, value):
        """Устанавливает значение RDN-атрибута."""
        rdn_attrs = getattr(self, "rdn_attributes", [])
        for field in self._meta.fields:
            if field.db_column and field.db_column in rdn_attrs:
                setattr(self, field.name, value)
                return

    def build_rdn(self):
        """Build RDN — исправление бага ldapdb 1.5.1.

        ldapdb's build_rdn() проверяет field.primary_key AND field.db_column,
        но поле 'dn' имеет primary_key=True и db_column=None,
        а 'cn'/'ou' — наоборот. Ни одно поле не подходит → всегда Exception.

        Исправление: для существующих объектов извлекаем RDN из текущего DN,
        для новых — строим из rdn_attributes.
        """
        # Существующий объект — извлекаем RDN из DN (сохраняет регистр CN/OU)
        if self.dn and "," in self.dn:
            return self.dn.split(",", 1)[0]

        # Новый объект — строим из rdn_attributes
        rdn_attrs = getattr(self, "rdn_attributes", [])
        for field in self._meta.fields:
            if field.db_column and field.db_column in rdn_attrs:
                value = getattr(self, field.name)
                if value:
                    return "%s=%s" % (field.db_column, value)
        raise Exception("Could not build Distinguished Name")

    def save(self, *args, **kwargs):
        """Переопределённый save с поддержкой modify_dn.

        Обрабатывает два случая:
        1. Изменение base_dn → перемещение между OU (modify_dn с newsuperior)
        2. Изменение RDN-атрибута (cn/ou) → переименование (modify_dn)

        AD запрещает менять RDN-атрибут через modify_s, только через rename.
        Поэтому: откатываем RDN к старому значению → save() → rename.
        """
        from .infrastructure.connections import _ldap

        is_existing = hasattr(self, "_saved_dn") and self._saved_dn

        # --- 1) Перемещение между OU (base_dn изменился) ---
        current_base_dn = getattr(self, "base_dn", None)
        needs_move = (
            is_existing
            and self._original_base_dn
            and current_base_dn
            and current_base_dn != self._original_base_dn
        )

        if needs_move:
            self.move_to(current_base_dn)

        # --- 2) RDN-атрибут (cn/ou) изменился ---
        new_rdn_value = self._get_rdn_value()
        old_rdn_value = getattr(self, "_original_rdn_value", None)
        needs_rename = (
            is_existing
            and old_rdn_value
            and new_rdn_value
            and new_rdn_value != old_rdn_value
        )

        if needs_rename:
            # Откатываем RDN к старому значению перед save(),
            # иначе ldapdb включит cn в modlist → AD отклонит
            self._set_rdn_value(old_rdn_value)

        # --- 3) Стандартный save (атрибуты, кроме RDN) ---
        result = super().save(*args, **kwargs)

        # --- 4) Выполняем rename если RDN изменился ---
        if needs_rename:
            from .utils.text_utils import esc_rdn

            rdn_attrs = getattr(self, "rdn_attributes", ["cn"])
            rdn_attr_name = rdn_attrs[0]  # 'cn' или 'ou'
            new_rdn = f"{rdn_attr_name.upper()}={esc_rdn(new_rdn_value)}"

            old_dn = self.dn
            dn_parts = old_dn.split(",", 1)
            container_dn = dn_parts[1] if len(dn_parts) == 2 else ""

            with _ldap() as conn:
                success = conn.modify_dn(old_dn, new_rdn)
                if success:
                    new_dn = f"{new_rdn},{container_dn}"
                    self.dn = new_dn
                    self._saved_dn = new_dn
                    self._set_rdn_value(new_rdn_value)
                    self._original_rdn_value = new_rdn_value
                    logger.info(f"ModifyDnMixin: Renamed {old_dn} → {new_dn}")
                else:
                    logger.warning(
                        f"ModifyDnMixin: Failed to rename "
                        f"{old_dn} → {new_rdn}: {conn.result}"
                    )
                    # Восстанавливаем новое значение в объекте
                    self._set_rdn_value(new_rdn_value)

        return result

    def move_to(self, new_base_dn):
        """Переместить объект в другую OU без обновления атрибутов.

        Выполняет LDAP modify_dn с newsuperior. НЕ вызывает super().save(),
        поэтому не пытается записать системные атрибуты (whenChanged и др.),
        которые AD обновляет автоматически при перемещении.

        Args:
            new_base_dn: Новый base DN (целевая OU).
                Пример: "OU=Dismissed,OU=company,DC=robotail,DC=local"

        Raises:
            RuntimeError: Если modify_dn не удался.
            ValueError: Если объект ещё не сохранён в LDAP.
        """
        from .infrastructure.connections import _ldap

        if not hasattr(self, "_saved_dn") or not self._saved_dn:
            raise ValueError(
                "Cannot move an object that hasn't been saved to LDAP yet"
            )

        old_dn = self._saved_dn
        new_rdn = self.build_rdn()
        new_dn = f"{new_rdn},{new_base_dn}"

        with _ldap() as conn:
            success = conn.modify_dn(
                old_dn,
                new_rdn,
                new_superior=new_base_dn,
            )
            if not success:
                raise RuntimeError(conn.result)
            logger.info(f"ModifyDnMixin.move_to: {old_dn} → {new_dn}")

        self._saved_dn = new_dn
        self.dn = new_dn
        self.base_dn = new_base_dn
        self._original_base_dn = new_base_dn

    @classmethod
    def from_db(cls, db, field_names, values):
        """Сохраняет оригинальные значения при загрузке объекта из БД."""
        instance = super().from_db(db, field_names, values)
        instance._original_base_dn = getattr(instance, "base_dn", None)
        instance._original_rdn_value = instance._get_rdn_value()
        return instance


class LdapSyncStateMixin:
    """Миксин для автоматического управления LdapSyncState при операциях с LDAP.

    Автоматически обновляет LdapSyncState при создании/обновлении/удалении
    LDAP объектов, отслеживая изменения DN и другие метаданные.

    Usage:
        class LdapUser(LdapSyncStateMixin, ModifyDnMixin, LdapModel):
            # Указываем, какая Django модель соответствует этой LDAP модели
            _sync_model_name = 'employee'
            _sync_pk_field = 'employee_number'  # Поле LDAP с Django PK

            employee_number = CharField(db_column='employeeNumber')
            # ... остальные поля

    Attributes:
        _sync_model_name (str): Имя модели для LdapSyncState.model
        _sync_pk_field (str): Имя поля, содержащего Django PK
    """

    _sync_model_name: Optional[str] = None
    _sync_pk_field: Optional[str] = None

    def save(self, *args, **kwargs):
        """Save с автоматическим обновлением LdapSyncState."""
        result = super().save(*args, **kwargs)

        # Обновляем LdapSyncState если настроен
        if self._sync_model_name and self._sync_pk_field:
            self._update_sync_state()

        return result

    def delete(self, *args, **kwargs):
        """Delete с автоматическим удалением LdapSyncState."""
        result = super().delete(*args, **kwargs)

        # Удаляем LdapSyncState если настроен
        if self._sync_model_name and self._sync_pk_field:
            self._delete_sync_state()

        return result

    def _update_sync_state(self):
        """Обновляет или создаёт запись LdapSyncState для этого объекта."""
        from employees.models import LdapSyncState
        from django.utils import timezone

        # Получаем Django PK из LDAP атрибута
        django_pk = getattr(self, self._sync_pk_field, None)
        if not django_pk:
            logger.warning(
                f"LdapSyncStateMixin: No {self._sync_pk_field} set, "
                f"skipping sync state update for {self.dn}"
            )
            return

        # Обновляем состояние
        state, created = LdapSyncState.objects.get_or_create(
            model=self._sync_model_name, object_pk=str(django_pk)
        )

        state.touch(
            ldap_dn=str(self.dn),
            sync_dir="ldap",
            last_ldap_modify_ts=timezone.now(),
        )

        action = "Created" if created else "Updated"
        logger.debug(
            f"LdapSyncStateMixin: {action} sync state for "
            f"{self._sync_model_name}#{django_pk} DN={self.dn}"
        )

    def _delete_sync_state(self):
        """Удаляет запись LdapSyncState для этого объекта."""
        from employees.models import LdapSyncState

        django_pk = getattr(self, self._sync_pk_field, None)
        if not django_pk:
            return

        deleted_count, _ = LdapSyncState.objects.filter(
            model=self._sync_model_name, object_pk=str(django_pk)
        ).delete()

        if deleted_count:
            logger.debug(
                f"LdapSyncStateMixin: Deleted sync state for "
                f"{self._sync_model_name}#{django_pk}"
            )


__all__ = [
    "ModifyDnMixin",
    "LdapSyncStateMixin",
]
