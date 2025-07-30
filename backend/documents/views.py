from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.views.generic import ListView
from .models import Document, DocumentAcknowledgement


class DocumentListView(LoginRequiredMixin, ListView):
    model = Document
    template_name = 'documents/document_list.html'
    context_object_name = 'documents'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        return (
            Document.objects
            .filter(Q(sent_to_all=True) | Q(recipients=user))
            .distinct()
            .order_by('-uploaded_at')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        # получаем id документов, с которыми пользователь уже ознакомился
        acked = DocumentAcknowledgement.objects.filter(user=user) \
                                               .values_list('document_id', flat=True)
        ctx['acked_ids'] = set(acked)
        return ctx

from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required


@login_required
def acknowledge_document(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    DocumentAcknowledgement.objects.get_or_create(document=doc, user=request.user)
    return redirect('documents:document_list')
