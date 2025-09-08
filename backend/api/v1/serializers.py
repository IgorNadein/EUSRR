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
        # Принимаем None/пустое
        if data in (None, "", b""):
            return super().to_internal_value(data)

        if isinstance(data, str):
            # Срезаем префикс data:image/...;base64, если есть
            if data.startswith("data:image"):
                try:
                    _, data = data.split(";base64,", 1)
                except ValueError:
                    raise serializers.ValidationError("Некорректный формат data URI.")
            try:
                decoded = base64.b64decode(data)
            except (TypeError, ValueError, binascii.Error):
                raise serializers.ValidationError("Невалидный base64.")

            ext, _ = self._detect_ext_mime(decoded)
            file = ContentFile(decoded, name=f"upload.{ext}")
            return super().to_internal_value(file)

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
