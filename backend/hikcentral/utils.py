import base64
from PIL import Image
from io import BytesIO
import random
import string


def gen_person_code(instance):
    import re
    base = str(instance.phone_number or instance.email or instance.pk)
    code = re.sub(r'\W+', '', base)[:16]

    # Проверяем уникальность, если не уникален — добавляем символы в конец
    from .models import HikPerson
    existing = (
        HikPerson.objects.using('hikcentral')
        .filter(person_code=code)
        .exists()
    )
    orig_code = code
    while existing:
        # Укорачиваем до 12 символов и дописываем случайные 4 символа
        code = (
            orig_code[:12] + ''.join(random.choices(string.ascii_letters + string.digits, k=4)))[:16]
        existing = (
            HikPerson.objects.using('hikcentral')
            .filter(person_code=code)
            .exists()
        )
    return code


def compress_image_to_base64(image_field, target_size_kb=200):
    """Сжимает изображение до размера (примерно) target_size_kb и возвращает base64-строку."""
    if not image_field:
        return ''
    image = Image.open(image_field)
    output = BytesIO()
    quality = 90
    # Сжимать до ~200КБ
    while True:
        output.seek(0)
        image.save(output, format='JPEG', quality=quality)
        size_kb = output.tell() / 1024
        if size_kb <= target_size_kb or quality <= 20:
            break
        quality -= 10
    output.seek(0)
    img_b64 = base64.b64encode(output.read()).decode('utf-8')
    return img_b64
