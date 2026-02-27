# documents/tests_v2.py
"""
Тесты для моделей DocumentV2 и DocumentAcknowledgementV2
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from filer.models import File as FilerFile
from documents.models_v2 import DocumentV2, DocumentAcknowledgementV2
from employees.models import Department
import rules

User = get_user_model()


class DocumentV2ModelTest(TestCase):
    """Тесты для модели DocumentV2"""
    
    def setUp(self):
        """Создание тестовых данных"""
        self.user = User.objects.create_user(
            phone_number='+79999999999',
            email='test1@example.com',
            first_name='Тест',
            last_name='Тестов',
            is_active=True
        )
        
        # Создаем тестовый файл через filer
        test_file = SimpleUploadedFile(
            "test_document.txt",
            b"Test content",
            content_type="text/plain"
        )
        
        self.filer_file = FilerFile.objects.create(
            file=test_file,
            original_filename="test_document.txt",
            name="Test Document",
            owner=self.user
        )
    
    def test_create_document_v2(self):
        """Создание документа с filer файлом"""
        document = DocumentV2.objects.create(
            title="Тестовый документ",
            file=self.filer_file,
            description="Описание тестового документа",
            uploaded_by=self.user,
            sent_to_all=True
        )
        
        self.assertEqual(document.title, "Тестовый документ")
        self.assertEqual(document.file, self.filer_file)
        self.assertEqual(document.uploaded_by, self.user)
        self.assertTrue(document.sent_to_all)
        self.assertIsNotNone(document.uploaded_at)
    
    def test_file_properties(self):
        """Проверка свойств файла (размер, расширение)"""
        document = DocumentV2.objects.create(
            title="Тестовый документ",
            file=self.filer_file,
            uploaded_by=self.user
        )
        
        self.assertGreater(document.file_size, 0)
        self.assertEqual(document.file_extension, 'txt')
    
    def test_sent_to_all(self):
        """Документ с sent_to_all=True"""
        document = DocumentV2.objects.create(
            title="Документ для всех",
            file=self.filer_file,
            uploaded_by=self.user,
            sent_to_all=True
        )
        
        self.assertTrue(document.sent_to_all)
        self.assertEqual(document.departments.count(), 0)
        self.assertEqual(document.recipients.count(), 0)
    
    def test_department_recipients(self):
        """Документ для конкретных отделов"""
        department = Department.objects.create(
            name="Тестовый отдел"
        )
        
        document = DocumentV2.objects.create(
            title="Документ для отдела",
            file=self.filer_file,
            uploaded_by=self.user,
            sent_to_all=False
        )
        document.departments.add(department)
        
        self.assertFalse(document.sent_to_all)
        self.assertEqual(document.departments.count(), 1)
        self.assertIn(department, document.departments.all())
    
    def test_individual_recipients(self):
        """Документ для конкретных получателей"""
        recipient = User.objects.create_user(
            phone_number='+79999999998',
            email='recipient@example.com',
            first_name='Получатель',
            last_name='Тестовый',
            is_active=True
        )
        
        document = DocumentV2.objects.create(
            title="Документ для получателя",
            file=self.filer_file,
            uploaded_by=self.user,
            sent_to_all=False
        )
        document.recipients.add(recipient)
        
        self.assertFalse(document.sent_to_all)
        self.assertEqual(document.recipients.count(), 1)
        self.assertIn(recipient, document.recipients.all())


class DocumentAcknowledgementV2ModelTest(TestCase):
    """Тесты для модели DocumentAcknowledgementV2"""
    
    def setUp(self):
        """Создание тестовых данных"""
        self.user = User.objects.create_user(
            phone_number='+79999999999',
            email='test@example.com',
            first_name='Тест',
            last_name='Тестов',
            is_active=True
        )
        
        test_file = SimpleUploadedFile(
            "test_document.txt",
            b"Test content",
            content_type="text/plain"
        )
        
        filer_file = FilerFile.objects.create(
            file=test_file,
            original_filename="test_document.txt",
            name="Test Document",
            owner=self.user
        )
        
        self.document = DocumentV2.objects.create(
            title="Тестовый документ",
            file=filer_file,
            uploaded_by=self.user,
            sent_to_all=True
        )
    
    def test_create_acknowledgement(self):
        """Создание ознакомления с документом"""
        ack = DocumentAcknowledgementV2.objects.create(
            document=self.document,
            user=self.user
        )
        
        self.assertEqual(ack.document, self.document)
        self.assertEqual(ack.user, self.user)
        self.assertIsNotNone(ack.acknowledged_at)
    
    def test_unique_acknowledgement(self):
        """Один пользователь может ознакомиться только один раз"""
        DocumentAcknowledgementV2.objects.create(
            document=self.document,
            user=self.user
        )
        
        # Попытка создать второе ознакомление должна вызвать ошибку
        with self.assertRaises(Exception):
            DocumentAcknowledgementV2.objects.create(
                document=self.document,
                user=self.user
            )
    
    def test_acknowledgement_count(self):
        """Подсчет ознакомлений"""
        user2 = User.objects.create_user(
            phone_number='+79999999998',
            email='test2@example.com',
            first_name='Тест2',
            last_name='Тестов2',
            is_active=True
        )
        
        DocumentAcknowledgementV2.objects.create(
            document=self.document,
            user=self.user
        )
        DocumentAcknowledgementV2.objects.create(
            document=self.document,
            user=user2
        )
        
        self.assertEqual(self.document.acknowledgements.count(), 2)


class DocumentV2RulesTest(TestCase):
    """Тесты для правил доступа django-rules"""
    
    def setUp(self):
        """Создание тестовых данных"""
        self.owner = User.objects.create_user(
            phone_number='+79999999999',
            email='owner@example.com',
            first_name='Владелец',
            last_name='Документа',
            is_active=True
        )
        
        self.other_user = User.objects.create_user(
            phone_number='+79999999998',
            email='other@example.com',
            first_name='Другой',
            last_name='Пользователь',
            is_active=True
        )
        
        test_file = SimpleUploadedFile(
            "test_document.txt",
            b"Test content",
            content_type="text/plain"
        )
        
        filer_file = FilerFile.objects.create(
            file=test_file,
            original_filename="test_document.txt",
            name="Test Document",
            owner=self.owner
        )
        
        self.document = DocumentV2.objects.create(
            title="Тестовый документ",
            file=filer_file,
            uploaded_by=self.owner,
            sent_to_all=False  # Не для всех
        )
    
    def test_owner_can_view(self):
        """Владелец может просматривать свой документ"""
        self.assertTrue(
            rules.test_rule('documents.view_documentv2', self.owner, self.document)
        )
    
    def test_other_user_cannot_view(self):
        """Другой пользователь не может просматривать чужой документ (если не в списке)"""
        self.assertFalse(
            rules.test_rule('documents.view_documentv2', self.other_user, self.document)
        )
    
    def test_sent_to_all_allows_view(self):
        """Документ с sent_to_all=True доступен всем активным пользователям"""
        self.document.sent_to_all = True
        self.document.save()
        
        self.assertTrue(
            rules.test_rule('documents.view_documentv2', self.other_user, self.document)
        )
    
    def test_recipient_can_view(self):
        """Получатель из списка может просматривать документ"""
        self.document.recipients.add(self.other_user)
        
        self.assertTrue(
            rules.test_rule('documents.view_documentv2', self.other_user, self.document)
        )
    
    def test_owner_can_edit(self):
        """Владелец может редактировать свой документ"""
        self.assertTrue(
            rules.test_rule('documents.change_documentv2', self.owner, self.document)
        )
    
    def test_other_user_cannot_edit(self):
        """Другой пользователь не может редактировать чужой документ"""
        self.assertFalse(
            rules.test_rule('documents.change_documentv2', self.other_user, self.document)
        )
    
    def test_owner_can_delete(self):
        """Владелец может удалять свой документ"""
        self.assertTrue(
            rules.test_rule('documents.delete_documentv2', self.owner, self.document)
        )
    
    def test_other_user_cannot_delete(self):
        """Другой пользователь не может удалять чужой документ"""
        self.assertFalse(
            rules.test_rule('documents.delete_documentv2', self.other_user, self.document)
        )
