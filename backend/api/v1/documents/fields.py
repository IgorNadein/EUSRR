# api/v1/documents/fields.py
"""
Кастомные serializer fields для работы с django-filer.
"""

from rest_framework import serializers
from django.core.files.uploadedfile import UploadedFile
from filer.models import File as FilerFile
import logging

logger = logging.getLogger(__name__)


class FilerFileField(serializers.Field):
    """
    Serializer field для работы с django-filer FilerFileField.
    
    При чтении (GET):
        - Возвращает URL файла из filer.File.url
    
    При записи (POST/PUT/PATCH):
        - Принимает UploadedFile
        - Создает filer.File объект
        - Возвращает filer.File instance для присвоения в модель
    """
    
    def to_representation(self, value):
        """
        Преобразует filer.File в URL для API response.
        
        Args:
            value: filer.File instance или None
            
        Returns:
            str: Полный URL файла или None
        """
        if value is None:
            return None
        
        if isinstance(value, FilerFile):
            if not value.url:
                return None
            
            # Получаем request из контекста для построения абсолютного URL
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(value.url)
            
            # Fallback: возвращаем относительный URL
            return value.url
        
        return None
    
    def to_internal_value(self, data):
        """
        Преобразует UploadedFile в filer.File instance.
        
        Args:
            data: UploadedFile из request
            
        Returns:
            FilerFile: Созданный filer.File объект
            
        Raises:
            serializers.ValidationError: При ошибках валидации
        """
        if data is None:
            return None
        
        if not isinstance(data, UploadedFile):
            raise serializers.ValidationError(
                "Ожидается файл для загрузки."
            )
        
        # Проверка размера файла
        from django.conf import settings
        from django.template.defaultfilters import filesizeformat
        
        limit = getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", None)
        if limit:
            size = getattr(data, "size", None)
            if size is None:
                raise serializers.ValidationError(
                    "Невозможно определить размер файла"
                )
            if int(size) > int(limit):
                human = filesizeformat(limit)
                raise serializers.ValidationError(
                    f"Файл слишком большой: > {human}."
                )
        
        # Получаем пользователя из контекста
        request = self.context.get('request')
        owner = getattr(request, 'user', None) if request else None
        
        try:
            # Создаем filer.File объект
            # is_public=True делает файл доступным без авторизации
            filer_file = FilerFile.objects.create(
                file=data,
                original_filename=data.name,
                name=data.name,
                owner=owner,
                is_public=True  # Делаем файл публичным для доступа с frontend
            )
            
            logger.info(
                f"[FilerFileField] Created filer.File id={filer_file.id} "
                f"name={data.name} owner={owner.id if owner else None} is_public=True"
            )
            
            return filer_file
            
        except Exception as e:
            logger.error(
                f"[FilerFileField] Error creating filer.File: {e}",
                exc_info=True
            )
            raise serializers.ValidationError(
                f"Ошибка при создании файла: {str(e)}"
            )
