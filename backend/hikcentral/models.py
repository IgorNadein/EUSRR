# hikcentral/models.py

from django.db import models


class HikPerson(models.Model):
    id = models.AutoField(primary_key=True)
    person_group_id = models.IntegerField(blank=True, null=True)
    person_type = models.IntegerField(blank=True, null=True)
    # важно! Уникальный ID от 1 до 16 символов (цифры/буквы)
    person_code = models.CharField(max_length=16, unique=True)
    given_name = models.CharField(max_length=255, blank=True, null=True)
    family_name = models.CharField(max_length=255, blank=True, null=True)
    full_name = models.CharField(max_length=255, blank=True, null=True)
    gender = models.IntegerField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=32, blank=True, null=True)
    photo_url = models.CharField(
        max_length=512, blank=True, null=True, default="")
    photo_index = models.IntegerField(blank=True, null=True)
    small_photo_url = models.CharField(max_length=512, blank=True, null=True)
    start_valid_date = models.DateTimeField(blank=True, null=True)
    end_valid_date = models.DateTimeField(blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    update_time = models.DateTimeField(blank=True, null=True)
    create_time = models.DateTimeField(blank=True, null=True)
    is_deleted = models.IntegerField(default=0)
    object_guid = models.CharField(max_length=64, blank=True, null=True)
    person_from = models.IntegerField(blank=True, null=True)
    rdn = models.CharField(max_length=255, blank=True, null=True)
    dn = models.CharField(max_length=255, blank=True, null=True)
    usn_changed = models.BigIntegerField(blank=True, null=True)
    start_time_differ = models.IntegerField(blank=True, null=True)
    end_time_differ = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'person'
        app_label = 'hikcentral'
        managed = False   # очень важно! — Django не управляет этой таблицей

    def __str__(self):
        return self.full_name or self.person_code


class HikPersonHeadPic(models.Model):
    id = models.AutoField(primary_key=True)
    person = models.ForeignKey(
        HikPerson,
        db_column='person_id',
        on_delete=models.CASCADE,
        related_name='head_pics'
    )
    standard_head_portrait = models.TextField(
        blank=True, null=True)     # основное фото (base64-строка)
    thumbnail_head_portrait = models.TextField(
        blank=True, null=True)    # миниатюра (base64)
    deepmode_head_portrait = models.TextField(blank=True, null=True)
    identi_photo = models.TextField(blank=True, null=True)
    create_time = models.DateTimeField(blank=True, null=True)
    update_time = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'person_head_pic'
        app_label = 'hikcentral'
        managed = False

    def __str__(self):
        return f"Photo for person_id={self.person_id}"
