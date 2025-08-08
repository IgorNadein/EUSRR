from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import DetailView, FormView, ListView

from .forms import MessageForm
from .models import Chat, Message


class ChatListView(LoginRequiredMixin, ListView):
    model = Chat
    template_name = "communications/chat_list.html"
    context_object_name = "chats"

    def get_queryset(self):
        user = self.request.user
        # departments — property у Employee
        departments = user.departments.all()
        queryset = (
            Chat.objects.filter(
                models.Q(type="global")
                | models.Q(type="department", department__in=departments)
                | models.Q(type="private", participants=user)
            )
            .distinct()
            .order_by("-created_at")
        )
        return queryset


class ChatDetailView(LoginRequiredMixin, DetailView, FormView):
    model = Chat
    template_name = "communications/chat_detail.html"
    context_object_name = "chat"
    form_class = MessageForm

    def get_success_url(self):
        return reverse("communications:chat_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["messages"] = self.object.messages.select_related("author").order_by(
            "created_at"
        )
        context["form"] = context.get("form", MessageForm())
        # Показываем актуальных участников чата!
        context["participants"] = self.object.get_participants
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            message = form.save(commit=False)
            message.chat = self.object
            message.author = request.user
            message.save()
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form))


def start_private_chat(request, employee_pk):
    from employees.models import Employee

    from .models import Chat

    target = get_object_or_404(Employee, pk=employee_pk)
    user = request.user
    chat = (
        Chat.objects.filter(type="private", participants=user)
        .filter(participants=target)
        .first()
    )
    if not chat:
        chat = Chat.objects.create(type="private")
        chat.participants.add(user, target)
    return redirect("communications:chat_detail", pk=chat.pk)
