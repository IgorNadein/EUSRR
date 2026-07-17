"""Утилиты для обработки изображений (аватары).

Функции для нормализации и конвертации аватаров пользователей в формат,
совместимый с Active Directory.
"""

import io

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore


def _encode_jpeg(image, quality: int) -> bytes:
    """Кодирует JPEG, обходя ограничения буфера libjpeg для сложных фото."""
    options = {
        "format": "JPEG",
        "quality": quality,
        "subsampling": 0,
    }

    buffer = io.BytesIO()
    try:
        image.save(
            buffer,
            optimize=True,
            progressive=True,
            **options,
        )
    except OSError:
        # Некоторые сборки libjpeg не могут оптимизировать высокоэнтропийное
        # изображение через BytesIO. Обычный JPEG остаётся совместимым с AD.
        buffer = io.BytesIO()
        image.save(
            buffer,
            optimize=False,
            progressive=False,
            **options,
        )
    return buffer.getvalue()


def _best_jpeg_within_limit(
    image,
    *,
    min_quality: int,
    max_quality: int,
    max_bytes: int,
) -> bytes | None:
    """Возвращает JPEG максимального качества в заданном лимите."""
    best = None
    low, high = min_quality, max_quality

    while low <= high:
        quality = (low + high) // 2
        encoded = _encode_jpeg(image, quality)
        if len(encoded) <= max_bytes:
            best = encoded
            low = quality + 1
        else:
            high = quality - 1

    return best


def normalize_avatar_to_jpeg(
    data: bytes, *, size_px: int = 384, max_kb: int = 100
) -> bytes:
    """Нормализует аватар в JPEG нужного размера и лимита.

    ВАЖНО: Автоматически применяет EXIF-ориентацию перед обработкой.
    Это предотвращает "переворачивание" фотографий, сделанных на телефоны
    в портретной или перевёрнутой ориентации.

    КАЧЕСТВО: Использует высокое разрешение (384px), progressive JPEG
    и 4:4:4 subsampling для максимального качества лиц в пределах 100KB.

    Args:
        data (bytes): Входной образ (PNG/JPEG/...).
        size_px (int): Максимальный размер изображения (по умолчанию 384).
            Пропорции сохраняются, итоговое изображение может быть меньше.
        max_kb (int): Максимальный размер файла в килобайтах
            (ограничение AD ~100 KB).

    Returns:
        bytes: JPEG-данные, соответствующие ограничениям,
            с правильной ориентацией.

    Raises:
        RuntimeError: Если Pillow недоступен или не удалось обработать
            изображение.
        ValueError: Если вход пустой.
    """
    if not data:
        raise ValueError("avatar: пустые данные")
    if size_px <= 0:
        raise ValueError("avatar: размер изображения должен быть положительным")
    if max_kb <= 0:
        raise ValueError("avatar: лимит размера должен быть положительным")
    if Image is None:
        raise RuntimeError(
            "Pillow не установлен. Установите 'Pillow' для обработки аватаров."
        )

    try:
        img = Image.open(io.BytesIO(data))

        # ИСПРАВЛЕНИЕ: Применяем EXIF-ориентацию перед обработкой
        # Это предотвращает "поворот" фотографий с телефонов
        try:
            # Получаем EXIF данные
            exif = img.getexif()
            # Тег 274 = Orientation
            orientation = exif.get(0x0112) if exif else None

            if orientation:
                # Применяем поворот согласно EXIF
                if orientation == 3:
                    img = img.rotate(180, expand=True)
                elif orientation == 6:
                    img = img.rotate(270, expand=True)
                elif orientation == 8:
                    img = img.rotate(90, expand=True)
        except (AttributeError, KeyError, IndexError):
            # Если EXIF недоступен или повреждён - продолжаем без ротации
            pass

        # Конвертируем в RGB (для JPEG)
        if img.mode in ("RGBA", "LA", "P"):
            # Создаем белый фон для прозрачных изображений
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            mask = img.split()[-1] if img.mode == "RGBA" else None
            background.paste(img, mask=mask)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # УЛУЧШЕНИЕ: Используем thumbnail для сохранения пропорций
        # вместо resize, который растягивает изображение
        img.thumbnail((size_px, size_px), Image.Resampling.LANCZOS)

        max_bytes = max_kb * 1024
        working = img

        # Сначала сохраняем высокое качество. Если сложное изображение не
        # помещается, уменьшаем разрешение, не нарушая жёсткий лимит LDAP.
        while True:
            best = _best_jpeg_within_limit(
                working,
                min_quality=75,
                max_quality=98,
                max_bytes=max_bytes,
            )
            if best is not None:
                return best

            if max(working.size) <= 64:
                break

            next_size = tuple(max(1, int(side * 0.85)) for side in working.size)
            working = working.resize(next_size, Image.Resampling.LANCZOS)

        # Аварийный диапазон качества нужен только для нетипично маленького
        # лимита или высокоэнтропийного изображения.
        while True:
            best = _best_jpeg_within_limit(
                working,
                min_quality=20,
                max_quality=74,
                max_bytes=max_bytes,
            )
            if best is not None:
                return best

            if max(working.size) <= 1:
                raise RuntimeError(
                    "avatar: невозможно уложить JPEG в заданный лимит"
                )

            next_size = tuple(max(1, int(side * 0.75)) for side in working.size)
            working = working.resize(next_size, Image.Resampling.LANCZOS)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"avatar: ошибка нормализации: {exc}") from exc


__all__ = [
    "normalize_avatar_to_jpeg",
]
