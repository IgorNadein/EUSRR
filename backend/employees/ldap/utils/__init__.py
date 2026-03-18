"""Утилиты модуля LDAP.

Вспомогательные функции для работы с LDAP, DN, текстом и изображениями.
"""

# Текстовые утилиты
from .text_utils import translit_to_ascii, esc_filter, esc_rdn

# LDAP утилиты
from .ldap_utils import (
    _first,
    _uac_is_active,
    _paged_search,
    get_attr_str,
    get_guid_str,
    _ldap_pick_phone,
    group_type,
    cn_candidates,
    make_base_login,
    fallback_login_from_email,
    ensure_unique_login,
    build_logins_for_user,
)

# DN утилиты
from .dn_utils import (
    extract_department_from_dn,
    rewrite_dn_suffix,
    _target_department_ou_dn,
    _ensure_user_dn,
    _move_to_department,
)

# Утилиты изображений
from .image_utils import normalize_avatar_to_jpeg

# Утилиты групп (ORM)
from .group_utils_orm import sync_user_groups_by_cns_orm

__all__ = [
    # Текстовые
    "translit_to_ascii",
    "esc_filter",
    "esc_rdn",
    # LDAP
    "_first",
    "_uac_is_active",
    "_paged_search",
    "get_attr_str",
    "get_guid_str",
    "_ldap_pick_phone",
    "group_type",
    "cn_candidates",
    "make_base_login",
    "fallback_login_from_email",
    "ensure_unique_login",
    "build_logins_for_user",
    # DN
    "extract_department_from_dn",
    "rewrite_dn_suffix",
    "_target_department_ou_dn",
    "_ensure_user_dn",
    "_move_to_department",
    # Изображения
    "normalize_avatar_to_jpeg",
    # Группы (ORM)
    "sync_user_groups_by_cns_orm",
]
