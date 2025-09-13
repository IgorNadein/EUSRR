# documents/urls.py
from django.urls import path
from .views import DocumentView, acknowledge_document

app_name = 'documents'

urlpatterns = [
    path('', DocumentView.as_view(), name='document_list'),
    path('ack/<int:pk>/', acknowledge_document, name='acknowledge'),
]
