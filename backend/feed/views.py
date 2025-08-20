from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import BooleanField, Count, Exists, F, OuterRef, Prefetch, Value
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from employees.models import Department, Employee, EmployeeDepartment
from .constants import TYPE_COMPANY, TYPE_DEPARTMENT, TYPE_EMPLOYEE
from .forms import CommentForm, PostForm
from .models import Comment, Post, PostLike


# ---------- Общие утилиты ----------

def _feed_queryset(base_qs, user):
    """
    Базовый queryset для ленты:
      - is_liked: отмечено ли текущим пользователем
      - comments_count: количество комментариев
      - last_comment_list: последний комментарий (to_attr)
    """
    if user.is_authenticated:
        is_liked_expr = Exists(PostLike.objects.filter(post=OuterRef("pk"), user=user))
    else:
        is_liked_expr = Value(False, output_field=BooleanField())

    last_comment_qs = (
        Comment.objects.select_related("author")
        .order_by("-created_at")[:1]
    )

    return (
        base_qs
        .select_related("author", "department")
        .annotate(
            is_liked=is_liked_expr,
            comments_count=Count("comments"),
        )
        .prefetch_related(
            Prefetch("comments", queryset=last_comment_qs, to_attr="last_comment_list")
        )
        .order_by("-pinned", "-created_at")
    )


def is_department_head(user, department: Department) -> bool:
    return bool(user and (user.is_staff or (department and department.head_id == user.id)))


def can_edit_post(user, post: Post) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    if post.type == TYPE_COMPANY:
        return False  # только staff
    if post.type == TYPE_DEPARTMENT:
        return post.author_id == user.id or is_department_head(user, post.department)
    return post.author_id == user.id  # личная публикация


def back_url_for_post(post: Post, user) -> str:
    if post.type == TYPE_COMPANY:
        return reverse("feed:feed_list")
    if post.type == TYPE_DEPARTMENT and post.department_id:
        return reverse("employees:department_detail", args=[post.department_id])
    return reverse(
        "feed:employee_feed",
        args=[user.pk if user and user.is_authenticated else post.author_id],
    )


# ---------- Ленты ----------

def feed_list(request):
    """
    Лента компании (доступна анонимам).
    Возвращаем posts с аннотациями (is_liked, comments_count, last_comment_list).
    """
    posts = _feed_queryset(Post.objects.filter(type=TYPE_COMPANY), request.user)

    # «Новые сотрудники»: верхние 10% активных, но минимум 1 (как было)
    active_employees = sorted(
        (emp for emp in Employee.objects.all() if emp.is_actually_active),
        key=lambda e: e.created_at,
        reverse=True,
    )
    new_count = max(1, int(len(active_employees) * 0.1))
    new_employees = Employee.objects.get_active()[:new_count]

    return render(
        request,
        "feed/feed_list.html",
        {"posts": posts, "new_employees": new_employees},
    )


@login_required
def department_feed(request, pk):
    """Историческая страница ленты отдела (основная — employees:department_detail)."""
    department = get_object_or_404(Department, pk=pk)
    posts = _feed_queryset(
        Post.objects.filter(type=TYPE_DEPARTMENT, department=department),
        request.user,
    )
    emp_links = (
        EmployeeDepartment.objects.filter(department=department, is_active=True)
        .select_related("employee")
        .order_by("employee__last_name", "employee__first_name")
    )
    return render(
        request,
        "feed/feed_list.html",
        {
            "department": department,
            "posts": posts,
            "new_employees": getattr(department, "new_employees", []),
            "emp_links": emp_links,
        },
    )


@login_required
def employee_feed(request, pk):
    """Лента конкретного сотрудника."""
    employee = get_object_or_404(Employee, pk=pk)
    posts = _feed_queryset(
        Post.objects.filter(type=TYPE_EMPLOYEE, author=employee),
        request.user,
    )
    return render(
        request,
        "feed/feed_list.html",
        {"employee": employee, "posts": posts},
    )


# ---------- Детальная + комментарии ----------

@login_required
def post_detail(request, pk):
    post = get_object_or_404(Post, pk=pk)
    comments = post.comments.select_related("author")

    if request.method == "POST":
        # инлайн-форма из ленты также постится сюда
        text = request.POST.get("text")
        if text:
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.author = request.user
                comment.post = post
                comment.save()
                messages.success(request, "Комментарий добавлен!")
                next_url = request.POST.get("next")
                if next_url:
                    return redirect(next_url)
                return redirect("feed:post_detail", pk=pk)
        else:
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.author = request.user
                comment.post = post
                comment.save()
                messages.success(request, "Комментарий добавлен!")
                return redirect("feed:post_detail", pk=pk)
    else:
        comment_form = CommentForm()

    return render(
        request,
        "feed/post_detail.html",
        {"post": post, "comments": comments, "comment_form": comment_form},
    )


@login_required
def comment_update(request, pk):
    """Редактирование комментария (автор или staff)."""
    comment = get_object_or_404(Comment, pk=pk)
    if not (request.user.is_staff or comment.author_id == request.user.id):
        messages.error(request, "У вас нет прав для редактирования этого комментария.")
        return redirect("feed:post_detail", pk=comment.post_id)

    if request.method == "POST":
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            messages.success(request, "Комментарий обновлён.")
            return redirect(f"{reverse('feed:post_detail', args=[comment.post_id])}#c{comment.pk}")
    else:
        form = CommentForm(instance=comment)

    return render(
        request,
        "feed/comment_form.html",
        {"form": form, "comment": comment, "post": comment.post},
    )


@login_required
def comment_delete(request, pk):
    """Удаление комментария (автор или staff; подтверждение через GET-страницу)."""
    comment = get_object_or_404(Comment, pk=pk)
    if not (request.user.is_staff or comment.author_id == request.user.id):
        messages.error(request, "У вас нет прав для удаления этого комментария.")
        return redirect("feed:post_detail", pk=comment.post_id)

    if request.method == "POST":
        post_id = comment.post_id
        comment.delete()
        messages.success(request, "Комментарий удалён.")
        return redirect("feed:post_detail", pk=post_id)

    return render(
        request,
        "feed/comment_confirm_delete.html",
        {"comment": comment, "post": comment.post},
    )


# ---------- Создание/редактирование/удаление поста ----------

@login_required
def post_create(request):
    """
    Универсальная форма создания поста.
      ?department=<id>  -> пост отдела
      ?type=company     -> новость компании
      ?type=employee    -> личная публикация
    По умолчанию — company.
    """
    dept_id = request.GET.get("department")
    force_type = request.GET.get("type")
    department = get_object_or_404(Department, pk=dept_id) if dept_id else None

    if department:
        context_type = TYPE_DEPARTMENT
    elif force_type in {TYPE_COMPANY, TYPE_EMPLOYEE}:
        context_type = force_type
    else:
        context_type = TYPE_COMPANY

    cancel_url = (
        request.GET.get("next")
        or (reverse("employees:department_detail", args=[department.pk]) if department else None)
        or (reverse("feed:feed_list") if context_type == TYPE_COMPANY else reverse("feed:employee_feed", args=[request.user.pk]))
    )

    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user

            if context_type == TYPE_DEPARTMENT:
                post.type = TYPE_DEPARTMENT
                post.department = department
            elif context_type == TYPE_COMPANY:
                post.type = TYPE_COMPANY
                post.department = None
            else:
                post.type = TYPE_EMPLOYEE
                post.department = None

            if post.type == TYPE_DEPARTMENT and not post.department:
                messages.error(request, "Для новостей отдела отдел обязателен.")
                return render(
                    request,
                    "feed/post_form.html",
                    {"form": form, "context_type": context_type, "department": department, "cancel_url": cancel_url},
                )

            post.save()
            messages.success(request, "Публикация создана!")
            return redirect(back_url_for_post(post, request.user))
    else:
        initial = {}
        if context_type == TYPE_DEPARTMENT:
            initial.update({"type": TYPE_DEPARTMENT, "department": department})
        elif context_type == TYPE_COMPANY:
            initial.update({"type": TYPE_COMPANY, "department": None})
        else:
            initial.update({"type": TYPE_EMPLOYEE})

        form = PostForm(initial=initial)

        # прячем лишние поля
        if "type" in form.fields:
            form.fields["type"].initial = initial["type"]
            form.fields["type"].widget = forms.HiddenInput()
        if context_type == TYPE_DEPARTMENT and "department" in form.fields:
            form.fields["department"].initial = department.pk
            form.fields["department"].widget = forms.HiddenInput()
        else:
            form.fields.pop("department", None)

    return render(
        request,
        "feed/post_form.html",
        {"form": form, "context_type": context_type, "department": department, "cancel_url": cancel_url},
    )


@login_required
def post_update(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if not can_edit_post(request.user, post):
        messages.error(request, "Нет прав на редактирование этой публикации.")
        return redirect("feed:post_detail", pk=pk)

    cancel_url = request.GET.get("next") or back_url_for_post(post, request.user)

    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            edited = form.save(commit=False)
            edited.type = post.type
            edited.department = post.department
            edited.author = post.author
            edited.save()
            messages.success(request, "Публикация обновлена!")
            return redirect(back_url_for_post(post, request.user))
    else:
        form = PostForm(instance=post)
        if "type" in form.fields:
            form.fields["type"].widget = forms.HiddenInput()
        if "department" in form.fields:
            form.fields["department"].widget = forms.HiddenInput()

    context_type = post.type
    department = post.department if post.type == TYPE_DEPARTMENT else None
    return render(
        request,
        "feed/post_form.html",
        {"form": form, "context_type": context_type, "department": department, "cancel_url": cancel_url},
    )


@login_required
def post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if not can_edit_post(request.user, post):
        messages.error(request, "Нет прав на удаление этой публикации.")
        return redirect("feed:post_detail", pk=pk)

    cancel_url = request.GET.get("next") or back_url_for_post(post, request.user)

    if request.method == "POST":
        back_url = back_url_for_post(post, request.user)
        post.delete()
        messages.success(request, "Публикация удалена.")
        return redirect(back_url)

    return render(
        request,
        "feed/post_confirm_delete.html",
        {"post": post, "cancel_url": cancel_url},
    )


@login_required
def pin_post(request, pk):
    post = get_object_or_404(Post, pk=pk)

    if post.type == TYPE_COMPANY and not request.user.is_staff:
        messages.error(request, "Только администратор может закреплять новости компании.")
        return redirect("feed:post_detail", pk=pk)

    if post.type == TYPE_DEPARTMENT and not is_department_head(request.user, post.department):
        messages.error(request, "Только руководитель отдела может закреплять новости отдела.")
        return redirect("feed:post_detail", pk=pk)

    post.pinned = not post.pinned
    post.save()
    messages.success(request, "Новость закреплена!" if post.pinned else "Новость откреплена!")
    return redirect(back_url_for_post(post, request.user))


# ---------- Лайки ----------

@login_required
def toggle_like(request, pk):
    """
    Переключение лайка. При AJAX/Fetch отдаёт JSON, иначе редиректит «назад».
    Счётчик поддерживаем атомарно через F().
    """
    if request.method != "POST":
        return redirect("feed:post_detail", pk=pk)

    post = get_object_or_404(Post, pk=pk)

    with transaction.atomic():
        like, created = PostLike.objects.select_for_update().get_or_create(
            post=post, user=request.user
        )
        if created:
            Post.objects.filter(pk=post.pk).update(likes_count=F("likes_count") + 1)
            is_liked = True
        else:
            like.delete()
            Post.objects.filter(pk=post.pk, likes_count__gt=0).update(
                likes_count=F("likes_count") - 1
            )
            is_liked = False

    post.refresh_from_db(fields=["likes_count"])

    wants_json = (
        "application/json" in request.headers.get("Accept", "")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )
    if wants_json:
        return JsonResponse(
            {"ok": True, "post_id": post.pk, "is_liked": is_liked, "likes": post.likes_count}
        )

    next_url = (
        request.POST.get("next")
        or request.META.get("HTTP_REFERER")
        or reverse("feed:post_detail", args=[post.pk])
    )
    return HttpResponseRedirect(next_url)
