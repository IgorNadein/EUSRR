from pathlib import Path
from typing import List, Tuple
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

try:
    from PIL import Image
except Exception as exc:  # pragma: no cover
    raise ImportError("Установите pillow: pip install Pillow") from exc


class Command(BaseCommand):
    """Генерирует набор иконок (favicons, apple-touch) из исходного logo.png."""

    help = (
        "Сгенерировать иконки из settings.BRAND_LOGO "
        "(static/img/logo.png по умолчанию)."
    )

    def add_arguments(self, parser) -> None:
        """Парсит аргументы команды.

        Args:
            parser: Аргумент-парсер Django management.
        """
        parser.add_argument(
            "--src", default=None, help="Путь в static к исходному PNG"
        )
        parser.add_argument(
            "--out-dir", default="img", help="Каталог внутри static для вывода"
        )

    def handle(self, *args, **opts) -> None:
        """Основная логика генерации.

        Raises:
            CommandError: Если исходного файла нет или он не PNG.
        """
        static_dir = Path(settings.BASE_DIR) / "static"
        out_dir = static_dir / opts["out_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)

        src_rel = opts["src"] or getattr(settings, "BRAND_LOGO", "img/logo.png")
        src_path = static_dir / src_rel

        if not src_path.exists():
            raise CommandError(f"Исходный файл не найден: {src_path}")
        if src_path.suffix.lower() != ".png":
            raise CommandError(
                "Ожидается PNG. При необходимости сконвертируйте логотип в PNG."
            )

        sizes: List[Tuple[str, int]] = [
            ("favicon-32.png", 32),
            ("apple-touch-icon.png", 180),
            ("logo-192.png", 192),
            ("logo-512.png", 512),
        ]

        with Image.open(src_path).convert("RGBA") as im:
            for name, sz in sizes:
                dst = out_dir / name
                im.resize((sz, sz), Image.LANCZOS).save(dst, format="PNG")
                self.stdout.write(
                    self.style.SUCCESS(f"✔ {dst.relative_to(static_dir)}")
                )
