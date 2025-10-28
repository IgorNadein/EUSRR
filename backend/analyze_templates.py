#!/usr/bin/env python
"""
Анализ шаблонов: поиск встроенных стилей и скриптов.
Помогает понять масштаб рефакторинга.
"""
import os
import re
from pathlib import Path
from collections import defaultdict

# Путь к шаблонам
TEMPLATES_DIR = Path(__file__).parent / 'templates'


def analyze_template(filepath):
    """Анализирует один шаблон"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        return None
    
    lines = len(content.splitlines())
    
    # Подсчёт тегов
    style_tags = len(re.findall(r'<style[^>]*>', content))
    script_tags = len(re.findall(r'<script[^>]*>', content))
    
    # Размер встроенных стилей и скриптов
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', content, re.DOTALL)
    script_blocks = re.findall(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
    
    style_lines = sum(len(block.splitlines()) for block in style_blocks)
    script_lines = sum(len(block.splitlines()) for block in script_blocks)
    
    # Поиск CSS классов
    css_classes = set(re.findall(r'\.([a-z][a-z0-9\-_]*)\s*{', content, re.IGNORECASE))
    
    # Поиск функций JavaScript
    js_functions = set(re.findall(r'function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(', content))
    
    return {
        'path': str(filepath.relative_to(TEMPLATES_DIR)),
        'total_lines': lines,
        'style_tags': style_tags,
        'script_tags': script_tags,
        'style_lines': style_lines,
        'script_lines': script_lines,
        'css_classes': css_classes,
        'js_functions': js_functions,
        'has_blocks': bool(re.search(r'{%\s*block\s+extra_(css|js)\s*%}', content)),
    }


def main():
    """Главная функция анализа"""
    print("=" * 80)
    print("АНАЛИЗ ШАБЛОНОВ: встроенные стили и скрипты")
    print("=" * 80)
    
    # Находим все HTML файлы
    html_files = list(TEMPLATES_DIR.rglob('*.html'))
    
    results = []
    for filepath in sorted(html_files):
        # Пропускаем backup файлы
        if '.backup' in str(filepath):
            continue
        
        result = analyze_template(filepath)
        if result and (result['style_tags'] > 0 or result['script_tags'] > 0):
            results.append(result)
    
    # Сортируем по количеству встроенного кода
    results.sort(key=lambda x: x['style_lines'] + x['script_lines'], reverse=True)
    
    print(f"\nНайдено {len(results)} шаблонов со встроенными стилями/скриптами\n")
    
    # Таблица результатов
    print(f"{'Файл':<60} {'Строк':<8} {'<style>':<8} {'<script>':<8} {'CSS↓':<8} {'JS↓':<8}")
    print("-" * 110)
    
    total_style_lines = 0
    total_script_lines = 0
    
    for r in results:
        total_style_lines += r['style_lines']
        total_script_lines += r['script_lines']
        
        print(f"{r['path']:<60} "
              f"{r['total_lines']:<8} "
              f"{r['style_tags']:<8} "
              f"{r['script_tags']:<8} "
              f"{r['style_lines']:<8} "
              f"{r['script_lines']:<8}")
    
    print("-" * 110)
    print(f"{'ИТОГО:':<60} "
          f"{'':8} "
          f"{'':8} "
          f"{'':8} "
          f"{total_style_lines:<8} "
          f"{total_script_lines:<8}")
    
    print("\n" + "=" * 80)
    print("АНАЛИЗ ДУБЛИКАТОВ")
    print("=" * 80)
    
    # Анализ повторяющихся CSS классов
    all_classes = defaultdict(list)
    for r in results:
        for cls in r['css_classes']:
            all_classes[cls].append(r['path'])
    
    duplicated_classes = {k: v for k, v in all_classes.items() if len(v) > 1}
    
    if duplicated_classes:
        print(f"\nПовторяющиеся CSS классы ({len(duplicated_classes)}):")
        for cls, files in sorted(duplicated_classes.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
            print(f"  .{cls} → {len(files)} файлов: {', '.join(files[:3])}{' ...' if len(files) > 3 else ''}")
    
    # Анализ повторяющихся JS функций
    all_functions = defaultdict(list)
    for r in results:
        for func in r['js_functions']:
            all_functions[func].append(r['path'])
    
    duplicated_functions = {k: v for k, v in all_functions.items() if len(v) > 1}
    
    if duplicated_functions:
        print(f"\nПовторяющиеся JS функции ({len(duplicated_functions)}):")
        for func, files in sorted(duplicated_functions.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
            print(f"  {func}() → {len(files)} файлов: {', '.join(files[:3])}{' ...' if len(files) > 3 else ''}")
    
    print("\n" + "=" * 80)
    print("РЕКОМЕНДАЦИИ ПО РЕФАКТОРИНГУ")
    print("=" * 80)
    
    # ТОП-5 файлов для рефакторинга
    print("\nТОП-5 файлов с наибольшим количеством встроенного кода:")
    for i, r in enumerate(results[:5], 1):
        total_embedded = r['style_lines'] + r['script_lines']
        percentage = (total_embedded / r['total_lines']) * 100
        print(f"{i}. {r['path']}")
        print(f"   {r['total_lines']} строк всего, {total_embedded} встроенного кода ({percentage:.1f}%)")
        print(f"   {r['style_lines']} строк CSS, {r['script_lines']} строк JS")
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
