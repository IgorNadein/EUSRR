import base64
import binascii
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image
from rest_framework import serializers


class Base64ImageField(serializers.ImageField):
    """
    Двухстороннее поле:
    - input: принимает строку base64 или data URI (data:image/...;base64,xxxx)
    - output: возвращает data URI (data:image/...;base64,xxxx)
    Совместимо с Python 3.13 (без imghdr).
    """

    default_ext = "jpg"

    def _detect_ext_mime(self, content: bytes) -> tuple[str, str]:
        """Определяем расширение и MIME через Pillow."""
        try:
            im = Image.open(BytesIO(content))
            fmt = (im.format or "").upper()
            ext_map = {
                "JPEG": "jpg",
                "JPG": "jpg",
                "PNG": "png",
                "WEBP": "webp",
                "GIF": "gif",
                "BMP": "bmp",
                "TIFF": "tiff",
                "ICO": "ico",
            }
            ext = ext_map.get(fmt, self.default_ext)
            mime = Image.MIME.get(fmt, "image/jpeg")
            return ext, mime
        except Exception:
            return self.default_ext, "image/jpeg"

    def to_internal_value(self, data):
        import logging
        logger = logging.getLogger(__name__)

        logger.info("[Base64ImageField] to_internal_value вызван:")
        logger.info(f"  - data type: {type(data).__name__}")
        logger.info(f"  - data repr: {repr(data)[:200]}")
        logger.info(f"  - data is None: {data is None}")
        logger.info(f"  - data == '': {data == ''}")
        logger.info(f"  - data == b'': {data == b''}")

        # Принимаем None/пустое
        if data in (None, "", b""):
            logger.info(
                "[Base64ImageField] Пустое значение, передаем в parent"
            )
            return super().to_internal_value(data)

        if isinstance(data, str):
            logger.info(
                f"[Base64ImageField] Обрабатываем строку, "
                f"length: {len(data)}"
            )

            # Срезаем префикс data:image/...;base64, если есть
            if data.startswith("data:image"):
                logger.info(
                    "[Base64ImageField] Найден data URI префикс"
                )
                try:
                    _, data = data.split(";base64,", 1)
                    logger.info(
                        f"[Base64ImageField] Префикс обрезан, "
                        f"осталось: {len(data)} символов"
                    )
                except ValueError:
                    logger.error(
                        "[Base64ImageField] Некорректный формат data URI"
                    )
                    raise serializers.ValidationError(
                        "Некорректный формат data URI."
                    )

            try:
                logger.info("[Base64ImageField] Декодируем base64...")
                decoded = base64.b64decode(data)
                logger.info(
                    f"[Base64ImageField] Base64 декодирован, "
                    f"размер: {len(decoded)} байт"
                )
            except (TypeError, ValueError, binascii.Error) as e:
                logger.error(
                    f"[Base64ImageField] Ошибка декодирования "
                    f"base64: {e}"
                )
                raise serializers.ValidationError("Невалидный base64.")

            logger.info(
                "[Base64ImageField] Определяем формат изображения..."
            )
            ext, _ = self._detect_ext_mime(decoded)
            logger.info(f"[Base64ImageField] Формат определен: {ext}")

            file = ContentFile(decoded, name=f"upload.{ext}")
            logger.info(
                "[Base64ImageField] ContentFile создан, "
                "передаем в parent ImageField"
            )

            result = super().to_internal_value(file)
            logger.info(
                f"[Base64ImageField] Parent validation passed, "
                f"result type: {type(result)}"
            )
            return result

        # Если это не строка (например, InMemoryUploadedFile)
        logger.info(
            "[Base64ImageField] Не строка, передаем в parent as-is"
        )

        # КРИТИЧНО: проверяем, не пустой ли файл
        if hasattr(data, 'size') and data.size == 0:
            logger.warning(
                "[Base64ImageField] Пустой файл (size=0), "
                "возвращаем None"
            )
            return None

        if hasattr(data, 'read'):
            # Проверяем содержимое файла
            try:
                content = data.read()
                if hasattr(data, 'seek'):
                    data.seek(0)
                if not content or len(content) == 0:
                    logger.warning(
                        "[Base64ImageField] Файл пустой (len=0), "
                        "возвращаем None"
                    )
                    return None
            except Exception as e:
                logger.error(
                    f"[Base64ImageField] Ошибка чтения файла: {e}"
                )

        result = super().to_internal_value(data)
        logger.info(
            f"[Base64ImageField] Parent validation passed, "
            f"result type: {type(result)}"
        )
        return result

        return super().to_internal_value(data)

    def to_representation(self, value):
        if not value:
            return ""
        # Получаем байты
        try:
            file_obj = getattr(value, "file", None) or value
            content = file_obj.read()
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)
        except Exception:
            try:
                with open(value.path, "rb") as f:
                    content = f.read()
            except Exception:
                return ""

        b64 = base64.b64encode(content).decode("ascii")
        _, mime = self._detect_ext_mime(content)
        return f"data:{mime};base64,{b64}"
