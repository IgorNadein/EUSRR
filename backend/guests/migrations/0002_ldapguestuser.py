import employees.ldap.mixins
import ldapdb.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("guests", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LdapGuestUser",
            fields=[
                (
                    "dn",
                    ldapdb.models.fields.CharField(
                        max_length=200,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("cn", ldapdb.models.fields.CharField(db_column="cn", max_length=200)),
                (
                    "sam_account_name",
                    ldapdb.models.fields.CharField(
                        db_column="sAMAccountName",
                        max_length=200,
                    ),
                ),
                (
                    "user_principal_name",
                    ldapdb.models.fields.CharField(
                        db_column="userPrincipalName",
                        max_length=200,
                    ),
                ),
                (
                    "given_name",
                    ldapdb.models.fields.CharField(
                        blank=True,
                        db_column="givenName",
                        max_length=200,
                    ),
                ),
                ("sn", ldapdb.models.fields.CharField(db_column="sn", max_length=200)),
                (
                    "display_name",
                    ldapdb.models.fields.CharField(
                        db_column="displayName",
                        max_length=200,
                    ),
                ),
                (
                    "mail",
                    ldapdb.models.fields.CharField(
                        blank=True,
                        db_column="mail",
                        max_length=200,
                    ),
                ),
                (
                    "telephone_number",
                    ldapdb.models.fields.CharField(
                        blank=True,
                        db_column="telephoneNumber",
                        max_length=200,
                    ),
                ),
                (
                    "employee_number",
                    ldapdb.models.fields.CharField(
                        blank=True,
                        db_column="employeeNumber",
                        max_length=200,
                    ),
                ),
                (
                    "description",
                    ldapdb.models.fields.CharField(
                        blank=True,
                        db_column="description",
                        max_length=200,
                    ),
                ),
                (
                    "user_account_control",
                    ldapdb.models.fields.IntegerField(
                        db_column="userAccountControl",
                    ),
                ),
                (
                    "member_of",
                    ldapdb.models.fields.ListField(blank=True, db_column="memberOf"),
                ),
                (
                    "when_created",
                    ldapdb.models.fields.DateTimeField(db_column="whenCreated"),
                ),
                (
                    "when_changed",
                    ldapdb.models.fields.DateTimeField(db_column="whenChanged"),
                ),
            ],
            options={
                "managed": False,
            },
            bases=(
                employees.ldap.mixins.LdapSyncStateMixin,
                employees.ldap.mixins.ModifyDnMixin,
                models.Model,
            ),
        ),
    ]
