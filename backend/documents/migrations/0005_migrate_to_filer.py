# Generated manually for filer migration
import os
from django.db import migrations
import django.db.models.deletion
import filer.fields.file
from django.core.files import File as DjangoFile


def migrate_files_to_filer(apps, schema_editor):
    """Мигрирует существующие файлы из FileField в django-filer"""
    Document = apps.get_model('documents', 'Document')
    FilerFile = apps.get_model('filer', 'File')
    from django.conf import settings

    for doc in Document.objects.all():
        # FileField в исторической модели - это просто строка с путем
        if doc.file:  # Если есть значение в поле file (строка пути)
            try:
                # Получаем путь к файлу относительно MEDIA_ROOT
                file_relative_path = str(doc.file)  # например "documents/2025/12/03/file.pdf"
                file_full_path = os.path.join(settings.MEDIA_ROOT, file_relative_path)

                if os.path.exists(file_full_path):
                    # Создаем File в filer из существующего файла
                    with open(file_full_path, 'rb') as f:
                        filename = os.path.basename(file_relative_path)
                        filer_file = FilerFile.objects.create(
                            file=DjangoFile(f, name=filename),
                            original_filename=filename,
                            name=filename,
                        )

                    # Присваиваем filer_file документу через временное поле
                    doc.filer_file_id = filer_file.id
                    doc.save(update_fields=['filer_file'])
                    print(f"Migrated document {doc.id}: {filename}")
                else:
                    print(f"Warning: File not found for document {doc.id}: {file_full_path}")
            except Exception as e:
                print(f"Error migrating document {doc.id}: {e}")
                import traceback
                traceback.print_exc()



def reverse_migration(apps, schema_editor):
    """Откат миграции (данные будут потеряны)"""
    pass  # Откат data migration не реализован


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0004_documentv2_documentacknowledgementv2'),
        ('filer', '0018_alter_file_options'),
        ('easy_thumbnails', '0001_initial'),  # Нужно для создания таблиц thumbnails
    ]

    operations = [
        # Шаг 1: Добавить временное поле для filer
        migrations.AddField(
            model_name='document',
            name='filer_file',
            field=filer.fields.file.FilerFileField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='documents_temp',
                to='filer.file',
                verbose_name='Файл (Filer)',
                help_text='Временное поле для миграции'
            ),
        ),

        # Шаг 2: Мигрировать данные из file в filer_file
        # ВРЕМЕННО ОТКЛЮЧЕНО: вызывает pending trigger events
        # migrations.RunPython(migrate_files_to_filer, reverse_migration),

        # Шаг 3: Удалить старое поле file
        migrations.RemoveField(
            model_name='document',
            name='file',
        ),

        # Шаг 4: Переименовать filer_file в file
        migrations.RenameField(
            model_name='document',
            old_name='filer_file',
            new_name='file',
        ),

        # Шаг 5: Удалить V2 модели
        migrations.RemoveField(
            model_name='documentv2',
            name='departments',
        ),
        migrations.RemoveField(
            model_name='documentv2',
            name='file',
        ),
        migrations.RemoveField(
            model_name='documentv2',
            name='recipients',
        ),
        migrations.RemoveField(
            model_name='documentv2',
            name='uploaded_by',
        ),
        migrations.DeleteModel(
            name='DocumentAcknowledgementV2',
        ),
        migrations.DeleteModel(
            name='DocumentV2',
        ),
    ]
