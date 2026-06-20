"""LDAP ORM models for guest Active Directory accounts.

Guest LDAP accounts are separate from employees:
- LdapSyncState.model is always ``guest``.
- employeeNumber stores ``Guest.id`` as a string.
- userAccountControl always remains disabled; access state is represented by
  OU placement under LDAP_GUESTS_ACTIVE_BASE/LDAP_GUESTS_DEACTIVATED_BASE.
"""

import datetime as _dt
import secrets
import string
from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone as _dj_tz
from ldap3 import SUBTREE
from ldapdb.models import Model as LdapModel
from ldapdb.models.fields import CharField, DateTimeField, IntegerField, ListField

from employees.ldap.infrastructure.connections import _ldap
from employees.ldap.mixins import LdapSyncStateMixin, ModifyDnMixin
from employees.ldap.repositories.ldap_repository import ensure_container_exists
from employees.ldap.services.constants import UserAccountControl
from employees.ldap.services.user_password_service import UserPasswordService
from employees.ldap.utils.ldap_utils import cn_candidates
from employees.ldap.utils.text_utils import esc_filter, esc_rdn


class _UtcCompat(_dt.tzinfo):
    def localize(self, dt):
        return dt.replace(tzinfo=_dt.timezone.utc)

    def normalize(self, dt):
        return dt.replace(tzinfo=_dt.timezone.utc)

    def utcoffset(self, dt):
        return _dt.timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return _dt.timedelta(0)

    def __repr__(self):
        return "UTC"


if not hasattr(_dj_tz, "utc") or not all(
    hasattr(_dj_tz.utc, attr) for attr in ("localize", "normalize")
):
    _dj_tz.utc = _UtcCompat()


def get_guests_base():
    return getattr(settings, "LDAP_GUESTS_BASE", "OU=Guests,DC=eusrr,DC=local")


@dataclass(frozen=True)
class LdapGuestSyncResult:
    dn: str
    sam_account_name: str
    user_principal_name: str
    user_account_control: int


class LdapGuestUser(LdapSyncStateMixin, ModifyDnMixin, LdapModel):
    """LDAP ORM model for guest AD users.

    Creation still uses ldap3 internally because django-ldapdb cannot create a
    user with dynamic DN and CN collision handling. The low-level details are
    kept behind class methods so GuestLdapService can stay workflow-focused.
    """

    _sync_model_name = "guest"
    _sync_pk_field = "employee_number"

    base_dn = get_guests_base()
    object_classes = ["top", "person", "organizationalPerson", "user"]
    rdn_attributes = ["cn"]

    cn = CharField(db_column="cn")
    sam_account_name = CharField(db_column="sAMAccountName")
    user_principal_name = CharField(db_column="userPrincipalName")

    given_name = CharField(db_column="givenName", blank=True)
    sn = CharField(db_column="sn")
    display_name = CharField(db_column="displayName")
    mail = CharField(db_column="mail", blank=True)
    telephone_number = CharField(db_column="telephoneNumber", blank=True)

    employee_number = CharField(db_column="employeeNumber", blank=True)
    description = CharField(db_column="description", blank=True)
    user_account_control = IntegerField(db_column="userAccountControl")

    member_of = ListField(db_column="memberOf", blank=True)
    when_created = DateTimeField(db_column="whenCreated")
    when_changed = DateTimeField(db_column="whenChanged")

    class Meta:
        managed = False

    def __str__(self):
        return f"{self.display_name} ({self.sam_account_name})"

    @classmethod
    def guest_bases(cls) -> tuple[str, str]:
        base = getattr(settings, "LDAP_GUESTS_BASE", "")
        active = getattr(settings, "LDAP_GUESTS_ACTIVE_BASE", "")
        deactivated = getattr(settings, "LDAP_GUESTS_DEACTIVATED_BASE", "")
        if not active and base:
            active = f"OU=Active,{base}"
        if not deactivated and base:
            deactivated = f"OU=Deactivated,{base}"
        return active, deactivated

    @classmethod
    def target_base(cls, in_active_ou: bool) -> str:
        active_base, deactivated_base = cls.guest_bases()
        target_base = active_base if in_active_ou else deactivated_base
        if not target_base:
            raise RuntimeError("Целевой LDAP контейнер гостей не задан.")
        return target_base

    @staticmethod
    def sam_for_guest(guest) -> str:
        return f"g{guest.id}"

    @staticmethod
    def upn_for_guest(guest) -> str:
        suffix = getattr(settings, "LDAP_UPN_SUFFIX", "") or "guest.local"
        return f"g{guest.id}@{suffix}"

    @staticmethod
    def display_name_for_guest(guest) -> str:
        return guest.full_name or f"Guest {guest.id}"

    @staticmethod
    def description_for_guest(guest) -> str:
        return f"Guest account for {guest.organization}".strip()

    @staticmethod
    def random_guest_password() -> str:
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
        return "".join(secrets.choice(alphabet) for _ in range(24))

    @classmethod
    def _guest_attrs(cls, guest) -> dict:
        display_name = cls.display_name_for_guest(guest)
        attrs = {
            "cn": display_name,
            "sAMAccountName": cls.sam_for_guest(guest),
            "userPrincipalName": cls.upn_for_guest(guest),
            "userAccountControl": UserAccountControl.DISABLED,
            "givenName": guest.first_name or None,
            "sn": guest.last_name or ".",
            "displayName": display_name,
            "mail": guest.email or None,
            "telephoneNumber": guest.phone or None,
            "employeeNumber": str(guest.id),
            "description": cls.description_for_guest(guest),
        }
        return {k: v for k, v in attrs.items() if v not in (None, "", [])}

    @classmethod
    def _sync_result(cls, dn: str, guest) -> LdapGuestSyncResult:
        return LdapGuestSyncResult(
            dn=str(dn),
            sam_account_name=cls.sam_for_guest(guest),
            user_principal_name=cls.upn_for_guest(guest),
            user_account_control=int(UserAccountControl.DISABLED),
        )

    @classmethod
    def _ensure_unique_employee_number(cls, conn, guest, current_dn: str = "") -> None:
        base = getattr(settings, "LDAP_BASE_DN", "") or getattr(
            settings,
            "LDAP_GUESTS_BASE",
            "",
        )
        if not base:
            return
        conn.search(
            search_base=base,
            search_filter=f"(employeeNumber={esc_filter(str(guest.id))})",
            search_scope=SUBTREE,
            attributes=["distinguishedName"],
            size_limit=2,
        )
        for entry in conn.entries:
            dn = str(getattr(entry, "entry_dn", ""))
            if dn and dn.lower() != (current_dn or "").lower():
                raise RuntimeError(
                    f"employeeNumber {guest.id} already exists in LDAP: {dn}"
                )

    @classmethod
    def create_for_guest(cls, guest, in_active_ou: bool) -> LdapGuestSyncResult:
        base_dn = cls.target_base(in_active_ou)
        with _ldap() as conn:
            ensure_container_exists(conn, base_dn)
            cls._ensure_unique_employee_number(conn, guest)
            attrs = cls._guest_attrs(guest)
            display_name = cls.display_name_for_guest(guest)
            safe_cn = cls.sam_for_guest(guest)
            dn = None
            for cn_text in cn_candidates(display_name, safe_cn):
                dn_try = f"CN={esc_rdn(cn_text)},{base_dn}"
                if conn.add(dn_try, cls.object_classes, attrs):
                    dn = dn_try
                    break
            if not dn:
                raise RuntimeError(f"LDAP add guest failed: {conn.result}")
            UserPasswordService().set_password(
                conn,
                dn,
                cls.random_guest_password(),
            )
        return cls._sync_result(dn, guest)

    @classmethod
    def sync_existing_for_guest(
        cls,
        guest,
        dn: str,
        in_active_ou: bool,
    ) -> LdapGuestSyncResult:
        target_base = cls.target_base(in_active_ou)
        with _ldap() as conn:
            ensure_container_exists(conn, target_base)
            cls._ensure_unique_employee_number(conn, guest, dn)

        ldap_guest = cls.objects.get(dn=dn)
        ldap_guest.move_to(target_base)
        ldap_guest.apply_guest(guest)
        ldap_guest.save()
        return cls._sync_result(str(ldap_guest.dn), guest)

    def apply_guest(self, guest) -> None:
        self.sam_account_name = self.sam_for_guest(guest)
        self.user_principal_name = self.upn_for_guest(guest)
        self.given_name = guest.first_name or ""
        self.sn = guest.last_name or "."
        self.display_name = self.display_name_for_guest(guest)
        self.mail = guest.email or ""
        self.telephone_number = guest.phone or ""
        self.employee_number = str(guest.id)
        self.description = self.description_for_guest(guest)
        self.user_account_control = UserAccountControl.DISABLED
