import io
import random

from PIL import Image

from employees.ldap.utils.image_utils import normalize_avatar_to_jpeg


def _noisy_png(size: int = 768) -> bytes:
    pixels = random.Random(42).randbytes(size * size * 3)
    image = Image.frombytes("RGB", (size, size), pixels)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_normalize_avatar_enforces_ldap_byte_limit():
    result = normalize_avatar_to_jpeg(_noisy_png(), size_px=384, max_kb=100)

    assert len(result) <= 100 * 1024

    image = Image.open(io.BytesIO(result))
    assert image.format == "JPEG"
    assert image.width <= 384
    assert image.height <= 384


def test_normalize_avatar_rejects_invalid_output_limit():
    try:
        normalize_avatar_to_jpeg(b"image", max_kb=0)
    except ValueError as exc:
        assert "лимит размера" in str(exc)
    else:
        raise AssertionError("Ожидалась ошибка для нулевого лимита")
