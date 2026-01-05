"""
Конфигурация для manual тестов.
Все тесты в этой директории автоматически помечаются как manual.
"""
import pytest

# Автоматически помечать все тесты в этой директории как manual
pytestmark = pytest.mark.manual
