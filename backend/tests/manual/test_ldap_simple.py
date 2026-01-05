#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки функции normalize_avatar_to_jpeg (LDAP).
Упрощённая версия без эмодзи для Windows консоли.

Использование:
    python test_ldap_simple.py <путь_к_файлу>
"""

import os
import sys
from pathlib import Path

# Добавляем путь к модулям Django
sys.path.insert(0, str(Path(__file__).parent))

# Настраиваем Django перед импортом
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
import django
django.setup()

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow не установлен. Установите: pip install Pillow")
    sys.exit(1)

from employees.ldap.utils.image_utils import normalize_avatar_to_jpeg


def get_image_info(image_path):
    """Получить информацию об изображении."""
    try:
        img = Image.open(image_path)
        size = os.path.getsize(image_path)
        
        # EXIF ориентация
        orientation_code = None
        orientation_name = "No EXIF"
        try:
            exif = img.getexif()
            if exif:
                orientation_code = exif.get(0x0112)
                orientation_names = {
                    1: "Normal", 3: "Rotated 180", 
                    6: "Rotated 90 CW", 8: "Rotated 270 CW"
                }
                orientation_name = orientation_names.get(orientation_code, f"Code {orientation_code}")
        except:
            pass
        
        return {
            'size': size,
            'size_kb': size / 1024,
            'dimensions': img.size,
            'mode': img.mode,
            'format': img.format,
            'orientation_code': orientation_code,
            'orientation_name': orientation_name
        }
    except Exception as e:
        return {'error': str(e)}


def test_ldap_compression(input_path):
    """Тестировать LDAP-сжатие одного файла."""
    print("\n" + "="*70)
    print(f"LDAP Image Compression Test: {os.path.basename(input_path)}")
    print("="*70)
    
    # Информация ДО
    print("\nBEFORE processing:")
    info_before = get_image_info(input_path)
    if 'error' in info_before:
        print(f"  ERROR: {info_before['error']}")
        return False
    
    print(f"  Size: {info_before['size_kb']:.2f} KB")
    print(f"  Resolution: {info_before['dimensions'][0]}x{info_before['dimensions'][1]}")
    print(f"  Mode: {info_before['mode']}, Format: {info_before['format']}")
    print(f"  EXIF Orientation: {info_before['orientation_name']}")
    
    # Обработка
    try:
        with open(input_path, 'rb') as f:
            original_data = f.read()
        
        print("\nProcessing with normalize_avatar_to_jpeg(size_px=384, max_kb=100)...")
        print("  HIGH QUALITY: progressive JPEG, 4:4:4 subsampling, quality 75-98")
        compressed_data = normalize_avatar_to_jpeg(
            original_data, size_px=384, max_kb=100
        )
        
        # Сохранение
        output_path = input_path.replace('.', '_ldap.')
        if not output_path.endswith('.jpg'):
            output_path = os.path.splitext(output_path)[0] + '.jpg'
            
        with open(output_path, 'wb') as f:
            f.write(compressed_data)
        
        print(f"  Saved to: {output_path}")
        
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Информация ПОСЛЕ
    print("\nAFTER processing (LDAP format):")
    info_after = get_image_info(output_path)
    if 'error' in info_after:
        print(f"  ERROR: {info_after['error']}")
        return False
    
    print(f"  Size: {info_after['size_kb']:.2f} KB")
    print(f"  Resolution: {info_after['dimensions'][0]}x{info_after['dimensions'][1]}")
    print(f"  Mode: {info_after['mode']}, Format: {info_after['format']}")
    print(f"  EXIF Orientation: {info_after['orientation_name']}")
    
    # Проверка лимитов
    size_ok = info_after['size_kb'] <= 100
    print(f"\nLDAP Compliance Check:")
    print(f"  [{'OK' if size_ok else 'FAIL'}] File size: {info_after['size_kb']:.2f} KB (limit: 100 KB)")
    
    # Статистика
    size_reduction = ((info_before['size'] - info_after['size']) / info_before['size']) * 100
    
    print(f"\nStatistics:")
    print(f"  Size reduction: {size_reduction:.1f}%")
    print(f"  Before: {info_before['dimensions'][0]}x{info_before['dimensions'][1]} ({info_before['size_kb']:.2f} KB)")
    print(f"  After:  {info_after['dimensions'][0]}x{info_after['dimensions'][1]} ({info_after['size_kb']:.2f} KB)")
    
    # Проверка ориентации
    if info_before['orientation_code'] and info_before['orientation_code'] != 1:
        if info_after['orientation_code'] is None or info_after['orientation_code'] == 1:
            print(f"  [OK] Orientation fixed automatically!")
            print(f"       Was: {info_before['orientation_name']}")
            print(f"       Now: Normal (rotated in pixels)")
        else:
            print(f"  [WARN] EXIF orientation preserved: {info_after['orientation_name']}")
    
    print("="*70)
    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_ldap_simple.py <image_file>")
        print("\nExample:")
        print("  python test_ldap_simple.py photo.jpg")
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    if not os.path.exists(input_path):
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)
    
    if not os.path.isfile(input_path):
        print(f"ERROR: Not a file: {input_path}")
        sys.exit(1)
    
    try:
        success = test_ldap_compression(input_path)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
