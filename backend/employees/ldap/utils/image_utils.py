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
    data: bytes, *, size_px: int = 120, max_kb: int = 100
) -> bytes:
    """Нормализует аватар в JPEG нужного размера и лимита.

    Args:
        data (bytes): Входной образ (PNG/JPEG/...).
        size_px (int): Квадратный размер целевого изображения (по умолчанию 120).
        max_kb (int): Максимальный размер файла в килобайтах
            (ограничение AD ~100 KB).

    Returns:
        bytes: JPEG-данные, соответствующие ограничениям.

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
        img = img.convert("RGB")
        img = img.resize((size_px, size_px))

        # бинарный поиск по качеству для соблюдения max_kb
        lo, hi = 50, 95
        best = None
        while lo <= hi:
            mid = (lo + hi) // 2
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=mid, optimize=True)
            kb = len(buf.getvalue()) // 1024
            if kb <= max_kb:
                best = buf.getvalue()
                lo = mid + 1
            else:
                hi = mid - 1

        if best is None:
            # минимально возможное
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=50, optimize=True)
            best = buf.getvalue()

        return best
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"avatar: ошибка нормализации: {exc}") from exc


__all__ = [
    "normalize_avatar_to_jpeg",
]
