"""
Тесты для статических файлов (CSS/JS)

Проверяют:
1. Валидность структуры CSS файлов
2. Корректность ES6 модулей JavaScript
3. Наличие обязательных файлов
4. Отсутствие синтаксических ошибок
"""

from pathlib import Path
from django.test import TestCase
from django.conf import settings


class StaticFilesStructureTest(TestCase):
    """Тесты структуры статических файлов"""
    
    def setUp(self):
        self.static_root = Path(settings.BASE_DIR) / 'static'
        self.css_root = self.static_root / 'css'
        self.js_root = self.static_root / 'js'
    
    def test_css_directories_exist(self):
        """Проверка существования CSS директорий"""
        self.assertTrue(
            self.css_root.exists(),
            "CSS директория должна существовать"
        )
        self.assertTrue(
            (self.css_root / 'components').exists(),
            "CSS components директория должна существовать"
        )
        self.assertTrue(
            (self.css_root / 'pages').exists(),
            "CSS pages директория должна существовать"
        )
    
    def test_js_directories_exist(self):
        """Проверка существования JS директорий"""
        self.assertTrue(
            self.js_root.exists(),
            "JS директория должна существовать"
        )
        self.assertTrue(
            (self.js_root / 'utils').exists(),
            "JS utils директория должна существовать"
        )
        self.assertTrue(
            (self.js_root / 'components').exists(),
            "JS components директория должна существовать"
        )
    
    def test_index_files_exist(self):
        """Проверка существования index файлов"""
        self.assertTrue(
            (self.css_root / 'components' / 'index.css').exists(),
            "CSS components/index.css должен существовать"
        )
        self.assertTrue(
            (self.js_root / 'utils' / 'index.js').exists(),
            "JS utils/index.js должен существовать"
        )
        self.assertTrue(
            (self.js_root / 'components' / 'index.js').exists(),
            "JS components/index.js должен существовать"
        )
    
    def test_variables_css_exists(self):
        """Проверка существования variables.css"""
        variables_file = self.css_root / 'variables.css'
        self.assertTrue(
            variables_file.exists(),
            "variables.css должен существовать"
        )
        
        # Проверка содержания основных переменных
        content = variables_file.read_text(encoding='utf-8')
        required_vars = [
            '--navbar-height',
            '--sidebar-width',
            '--feed-radius',
            '--shadow-md',
            '--transition-base'
        ]
        for var in required_vars:
            self.assertIn(
                var,
                content,
                f"Переменная {var} должна быть определена в variables.css"
            )


class CSSFilesValidityTest(TestCase):
    """Тесты валидности CSS файлов"""
    
    def setUp(self):
        self.css_root = Path(settings.BASE_DIR) / 'static' / 'css'
    
    def test_css_files_syntax(self):
        """Базовая проверка синтаксиса CSS файлов"""
        css_files = list(self.css_root.rglob('*.css'))
        
        for css_file in css_files:
            with self.subTest(file=css_file.name):
                content = css_file.read_text(encoding='utf-8')
                
                # Проверка парности фигурных скобок
                open_braces = content.count('{')
                close_braces = content.count('}')
                self.assertEqual(
                    open_braces,
                    close_braces,
                    f"{css_file.name}: несбалансированные фигурные скобки"
                )
                
                # Проверка что нет незакрытых комментариев
                # Простая проверка: /* должно быть равно */
                open_comments = content.count('/*')
                close_comments = content.count('*/')
                self.assertEqual(
                    open_comments,
                    close_comments,
                    f"{css_file.name}: незакрытые комментарии"
                )
    
    def test_css_files_encoding(self):
        """Проверка кодировки CSS файлов (UTF-8)"""
        css_files = list(self.css_root.rglob('*.css'))
        
        for css_file in css_files:
            with self.subTest(file=css_file.name):
                try:
                    css_file.read_text(encoding='utf-8')
                except UnicodeDecodeError:
                    msg = f"{css_file.name}: неверная кодировка (не UTF-8)"
                    self.fail(msg)


class JSFilesValidityTest(TestCase):
    """Тесты валидности JavaScript файлов"""
    
    def setUp(self):
        self.js_root = Path(settings.BASE_DIR) / 'static' / 'js'
    
    def test_js_files_are_modules(self):
        """Проверка что JS файлы используют ES6 модули"""
        js_files = list(self.js_root.rglob('*.js'))
        
        for js_file in js_files:
            with self.subTest(file=js_file.name):
                content = js_file.read_text(encoding='utf-8')
                
                # Проверка что файл содержит export (ES6 модуль)
                self.assertTrue(
                    'export' in content,
                    f"{js_file.name}: должен содержать export для ES6 модуля"
                )
    
    def test_js_files_syntax_basic(self):
        """Базовая проверка синтаксиса JS файлов"""
        js_files = list(self.js_root.rglob('*.js'))
        
        for js_file in js_files:
            with self.subTest(file=js_file.name):
                content = js_file.read_text(encoding='utf-8')
                
                # Проверка парности фигурных скобок
                open_braces = content.count('{')
                close_braces = content.count('}')
                self.assertEqual(
                    open_braces,
                    close_braces,
                    f"{js_file.name}: несбалансированные фигурные скобки"
                )
                
                # Проверка парности круглых скобок
                open_parens = content.count('(')
                close_parens = content.count(')')
                self.assertEqual(
                    open_parens,
                    close_parens,
                    f"{js_file.name}: несбалансированные круглые скобки"
                )
                
                # Проверка парности квадратных скобок
                open_brackets = content.count('[')
                close_brackets = content.count(']')
                self.assertEqual(
                    open_brackets,
                    close_brackets,
                    f"{js_file.name}: несбалансированные квадратные скобки"
                )
    
    def test_js_files_encoding(self):
        """Проверка кодировки JS файлов (UTF-8)"""
        js_files = list(self.js_root.rglob('*.js'))
        
        for js_file in js_files:
            with self.subTest(file=js_file.name):
                try:
                    js_file.read_text(encoding='utf-8')
                except UnicodeDecodeError:
                    self.fail(f"{js_file.name}: неверная кодировка (не UTF-8)")


class IndexFilesTest(TestCase):
    """Тесты для index файлов"""
    
    def test_css_index_imports(self):
        """Проверка что CSS index.css готов к импорту компонентов"""
        index_file = (
            Path(settings.BASE_DIR) / 'static' / 'css' /
            'components' / 'index.css'
        )
        content = index_file.read_text(encoding='utf-8')
        
        # Проверка что есть комментарии о подключении
        self.assertIn(
            '@import',
            content,
            "index.css должен содержать примеры @import"
        )
    
    def test_js_utils_index_exports(self):
        """Проверка что JS utils/index.js готов к экспорту утилит"""
        index_file = (
            Path(settings.BASE_DIR) / 'static' / 'js' /
            'utils' / 'index.js'
        )
        content = index_file.read_text(encoding='utf-8')
        
        # Проверка что есть export
        self.assertIn(
            'export',
            content,
            "utils/index.js должен содержать export"
        )
    
    def test_js_components_index_exports(self):
        """Проверка что JS components/index.js готов к экспорту"""
        index_file = (
            Path(settings.BASE_DIR) / 'static' / 'js' /
            'components' / 'index.js'
        )
        content = index_file.read_text(encoding='utf-8')
        
        # Проверка что есть export
        self.assertIn(
            'export',
            content,
            "components/index.js должен содержать export"
        )
