# documents/urls.py
from django.urls import path
from .views import DocumentListView, acknowledge_document

app_name = 'documents'

urlpatterns = [
    path('', DocumentListView.as_view(), name='document_list'),
    path('ack/<int:pk>/', acknowledge_document, name='acknowledge'),
]
