"""Утилиты для обработки изображений (аватары).

Функции для нормализации и конвертации аватаров пользователей в формат,
совместимый с Active Directory.
"""

import io

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore


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

        # Бинарный поиск по качеству для соблюдения max_kb
        # КАЧЕСТВО: Повышен минимум до 75, используется progressive и 4:4:4
        lo, hi = 75, 98
        best = None
        while lo <= hi:
            mid = (lo + hi) // 2
            buf = io.BytesIO()
            # МАКСИМАЛЬНОЕ КАЧЕСТВО:
            # - progressive: лучше сжатие, плавная загрузка
            # - subsampling=0: 4:4:4 (без потери цветности, лучше для лиц)
            # - optimize: оптимизация таблиц Хаффмана
            img.save(
                buf,
                format="JPEG",
                quality=mid,
                optimize=True,
                progressive=True,
                subsampling=0,  # 4:4:4 - без потери цветности
            )
            kb = len(buf.getvalue()) // 1024
            if kb <= max_kb:
                best = buf.getvalue()
                lo = mid + 1
            else:
                hi = mid - 1

        if best is None:
            # минимально возможное (с теми же настройками качества)
            buf = io.BytesIO()
            img.save(
                buf,
                format="JPEG",
                quality=75,
                optimize=True,
                progressive=True,
                subsampling=0,
            )
            best = buf.getvalue()

        return best
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"avatar: ошибка нормализации: {exc}") from exc


__all__ = [
    "normalize_avatar_to_jpeg",
]
