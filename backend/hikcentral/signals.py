# # backend/hikcentral/signals.py

# from django.db.models.signals import post_save, post_delete
# from django.dispatch import receiver
# from users.models import Employee
# from .models import HikPerson, HikPersonHeadPic
# from django.utils import timezone
# from .utils import gen_person_code, compress_image_to_base64


# @receiver(post_save, sender=Employee)
# def sync_employee_to_hikcentral(sender, instance, created, **kwargs):
#     db = 'hikcentral'

#     # Определяем person_code (уникальный)
#     person_code = gen_person_code(instance)

#     # Проставим даты
#     now = timezone.now()
#     start_valid = now
#     end_valid = now.replace(year=now.year+10)

#     # 1. Создаём/обновляем запись в person
#     person_values = dict(
#         person_group_id=1,
#         person_type=0,
#         person_code=person_code,
#         given_name=instance.first_name,
#         family_name=instance.last_name,
#         full_name=f"{instance.first_name} {instance.last_name}",
#         gender=0,  # по аналогии: 0 - не указан, 1 - муж, 2 - жен
#         email=instance.email,
#         phone_number=str(
#             instance.phone_number) if instance.phone_number else "",
#         photo_url=instance.avatar.url if instance.avatar else "",
#         photo_index=0,
#         small_photo_url=instance.avatar.url if instance.avatar else "",
#         start_valid_date=start_valid,
#         end_valid_date=end_valid,
#         remark='',
#         update_time=now,
#         create_time=now,
#         is_deleted=0,
#         person_from=0,
#         usn_changed=0,
#         start_time_differ=10800,
#         end_time_differ=10800,
#     )

#     # Сохраняем сотрудника в HikCentral
#     person = HikPerson.objects.using(db).create(**person_values)

#     # 2. Картинка (photo/avatar)
#     if instance.avatar:
#         img_b64 = compress_image_to_base64(instance.avatar)
#         HikPersonHeadPic.objects.using(db).create(
#             person_id=person.id,
#             standard_head_portrait=img_b64,
#             thumbnail_head_portrait='',
#             deepmode_head_portrait='',
#             identi_photo='',
#             create_time=now,
#             update_time=now,
#         )


# @receiver(post_delete, sender=Employee)
# def delete_employee_from_hikcentral(sender, instance, **kwargs):
#     db = 'hikcentral'
#     # Найдём всех по имени и почте — или храни person_code в Employee
#     HikPerson.objects.using(db).filter(
#         email=instance.email,
#         full_name=f"{instance.first_name} {instance.last_name}",
#     ).delete()
#     # Не забудь удалить фото
#     # person_ids = list(...)
#     # HikPersonHeadPic.objects.using(db).filter(person_id__in=person_ids).delete()
