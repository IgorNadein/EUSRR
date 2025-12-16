"""Утилиты для обработки изображений.

Функции для сжатия и оптимизации изображений при загрузке.
"""

import io

try:
    from PIL import Image
except ImportError:
    Image = None


def compress_image(
    data: bytes,
    *,
    max_width: int = 512,
    max_height: int = 512,
    max_kb: int = 500,
    quality: int = 85,
    format: str = "JPEG",
) -> bytes:
    """Сжимает изображение с сохранением пропорций.

    Функция оптимизирована для аватаров, которые будут использоваться
    в системах распознавания лиц. Размер 512x512 обеспечивает достаточное
    качество для нейросетей при разумном размере файла.

    ВАЖНО: Автоматически применяет EXIF-ориентацию перед обработкой.
    Это предотвращает "переворачивание" фотографий, сделанных на телефоны
    в портретной или перевёрнутой ориентации.

    Args:
        data: Входные данные изображения (любой формат, поддерживаемый PIL)
        max_width: Максимальная ширина в пикселях (по умолчанию 512)
        max_height: Максимальная высота в пикселях (по умолчанию 512)
        max_kb: Максимальный размер файла в килобайтах (по умолчанию 500)
        quality: Начальное качество JPEG (по умолчанию 85)
        format: Формат выходного файла (по умолчанию JPEG)

    Returns:
        bytes: Сжатые данные изображения с правильной ориентацией

    Raises:
        RuntimeError: Если Pillow не установлен или ошибка обработки
        ValueError: Если входные данные пусты
    """
    if not data:
        raise ValueError("Пустые данные изображения")

    if Image is None:
        raise RuntimeError(
            "Pillow не установлен. Выполните: pip install Pillow"
        )

    try:
        # Открываем изображение
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

        # Изменяем размер с сохранением пропорций
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

        # Бинарный поиск по качеству для соблюдения max_kb
        lo, hi = 50, quality
        best = None

        while lo <= hi:
            mid = (lo + hi) // 2
            buf = io.BytesIO()
            img.save(buf, format=format, quality=mid, optimize=True)
            size_kb = len(buf.getvalue()) / 1024

            if size_kb <= max_kb:
                best = buf.getvalue()
                lo = mid + 1
            else:
                hi = mid - 1

        # Если не удалось уложиться в лимит, используем минимальное качество
        if best is None:
            buf = io.BytesIO()
            img.save(buf, format=format, quality=50, optimize=True)
            best = buf.getvalue()

        return best

    except Exception as exc:
        raise RuntimeError(f"Ошибка обработки изображения: {exc}") from exc


def compress_avatar(data: bytes) -> bytes:
    """Сжимает аватар пользователя с оптимальными параметрами.

    Специализированная версия compress_image для аватаров:
    - Размер 512x512 (достаточно для распознавания лиц)
    - Максимум 500KB (баланс между качеством и размером)
    - Качество 85 (хорошее качество для лиц)

    Args:
        data: Входные данные изображения

    Returns:
        bytes: Сжатые данные аватара
    """
    return compress_image(
        data,
        max_width=512,
        max_height=512,
        max_kb=500,
        quality=85,
    )


__all__ = ["compress_image", "compress_avatar"]
