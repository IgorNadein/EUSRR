# Тестовые скрипты для сжатия изображений

Скрипты для проверки функций сжатия аватаров с поддержкой EXIF-ориентации.

## Быстрые тесты (рекомендуется для Windows)

### 1. Тест LDAP-сжатия (384px, 100KB, HIGH QUALITY)
```bash
python test_ldap_simple.py path/to/photo.jpg
```

### 2. Тест обычного сжатия аватаров (512px, 500KB)
```bash
python test_avatar_simple.py path/to/photo.jpg
```

## Интерактивные тесты (с эмодзи, могут не работать в Windows cmd)

### 3. Полный тест LDAP
```bash
python test_ldap_image_compression.py
```

### 4. Полный тест аватаров
```bash
python test_image_compression.py
```

## Что проверяют скрипты

✅ **EXIF ориентация** - фото с телефонов не переворачиваются  
✅ **Сжатие размера** - процент уменьшения файла  
✅ **Разрешение** - размер в пикселях до и после  
✅ **Лимиты** - соответствие ограничениям (100KB для LDAP, 500KB для системы)  

## Примеры вывода

### test_ldap_simple.py:
```
======================================================================
LDAP Image Compression Test: IMG_1234.jpg
======================================================================

BEFORE processing:
  Size: 2453.67 KB
  Resolution: 3024x4032
  Mode: RGB, Format: JPEG
  EXIF Orientation: Rotated 90 CW

Processing with normalize_avatar_to_jpeg(size_px=384, max_kb=100)...
  HIGH QUALITY: progressive JPEG, 4:4:4 subsampling, quality 75-98
  Saved to: IMG_1234_ldap.jpg

AFTER processing (LDAP format):
  Size: 68.45 KB
  Resolution: 288x384
  Mode: RGB, Format: JPEG
  EXIF Orientation: Normal

LDAP Compliance Check:
  [OK] File size: 68.45 KB (limit: 100 KB)

Statistics:
  Size reduction: 97.2%
  Before: 3024x4032 (2453.67 KB)
  After:  288x384 (68.45 KB)
  [OK] Orientation fixed automatically!
       Was: Rotated 90 CW
       Now: Normal (rotated in pixels)
======================================================================
```

## Требования

- Python 3.8+
- Django (настройки проекта)
- Pillow (PIL)

## Примечания

- Скрипты автоматически настраивают Django
- Обработанные файлы сохраняются рядом с оригиналом
- LDAP версия: суффикс `_ldap.jpg`
- Обычная версия: суффикс `_compressed.jpg`
