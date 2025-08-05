# backend\feed\views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Post, Comment
from .forms import PostForm, CommentForm
from employees.models import Department, Employee


def feed_list(request):
    posts = Post.objects.filter(type='company').order_by(
        '-pinned', '-created_at')
    active_employees = sorted(
        [emp for emp in Employee.objects.all() if emp.is_actually_active],
        key=lambda e: e.created_at,
        reverse=True
    )
    new_count = max(1, int(len(active_employees) * 0.1))
    new_employees = Employee.get_active()[:new_count]
    return render(request, 'feed/feed_list.html', {
        'posts': posts,
        'new_employees': new_employees,
    })


@login_required
def department_feed(request, pk):
    department = get_object_or_404(Department, pk=pk)
    posts = Post.objects.filter(type='department', department=department).order_by(
        '-pinned', '-created_at')
    new_employees = department.employees.filter(
        employee__actions__action__in=['hired', 'rehired', 'transferred']
    ).distinct().order_by('-employee__created_at')[:5]
    return render(request, 'feed/department_feed.html', {
        'department': department,
        'posts': posts,
        'new_employees': new_employees,
    })


@login_required
def employee_feed(request, pk):
    """Публикации конкретного сотрудника"""
    employee = get_object_or_404(Employee, pk=pk)
    posts = Post.objects.filter(author=employee).order_by('-created_at')
    return render(request, 'feed/employee_feed.html', {'employee': employee, 'posts': posts})


@login_required
def post_detail(request, pk):
    """Детальная страница публикации с комментариями"""
    post = get_object_or_404(Post, pk=pk)
    comments = post.comments.select_related('author')
    if request.method == 'POST':
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.author = request.user
            comment.post = post
            comment.save()
            messages.success(request, "Комментарий добавлен!")
            return redirect('feed:post_detail', pk=pk)
    else:
        comment_form = CommentForm()
    return render(request, 'feed/post_detail.html', {
        'post': post,
        'comments': comments,
        'comment_form': comment_form
    })


@login_required
def post_create(request):
    """Создание новой публикации"""
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            if post.type == 'department' and not post.department:
                messages.error(request, "Для новостей отдела выберите отдел.")
                return render(request, 'feed/post_form.html', {'form': form})
            post.save()
            messages.success(request, "Публикация создана!")
            # Перенаправление по типу публикации
            if post.type == 'company':
                return redirect('feed:feed_list')
            elif post.type == 'department':
                return redirect('feed:department_feed', pk=post.department.pk)
            else:
                return redirect('feed:employee_feed', pk=request.user.pk)
    else:
        form = PostForm()
    return render(request, 'feed/post_form.html', {'form': form})


def is_department_head(user, department):
    return user.is_staff or (department.head == user)


@login_required
def pin_post(request, pk):
    post = get_object_or_404(Post, pk=pk)
    # Главные новости: только staff
    if post.type == 'company' and not request.user.is_staff:
        messages.error(
            request, "Только администратор может закреплять новости компании.")
        return redirect('feed:post_detail', pk=pk)
    # Новости отдела: только начальник отдела
    if post.type == 'department' and not is_department_head(request.user, post.department):
        messages.error(
            request, "Только руководитель отдела может закреплять новости отдела.")
        return redirect('feed:post_detail', pk=pk)
    post.pinned = not post.pinned
    post.save()
    action = "Закреплено" if post.pinned else "Откреплено"
    messages.success(request, f"Новость {action}!")
    # редирект по типу поста
    if post.type == 'company':
        return redirect('feed:feed_list')
    elif post.type == 'department':
        return redirect('feed:department_feed', pk=post.department.pk)
    else:
        return redirect('feed:employee_feed', pk=post.author.pk)
