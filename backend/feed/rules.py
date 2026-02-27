"""
django-rules: декларативные правила доступа для feed (лента новостей)

Правила используются для проверки permissions на уровне объектов.
https://github.com/dfunckt/django-rules
"""

import rules


# -----------------------------------------------------------------------------
# ПРЕДИКАТЫ (predicates)
# -----------------------------------------------------------------------------

@rules.predicate
def is_superuser(user):
    """Суперпользователь имеет все права"""
    return user.is_superuser


@rules.predicate
def is_post_author(user, post):
    """Пользователь является автором поста"""
    if post is None:
        return False
    
    return post.author == user or post.created_by == user


@rules.predicate
def can_publish_posts(user):
    """
    Пользователь может публиковать посты в ленте.
    Адаптируйте под вашу логику (по должности, группе и т.д.)
    """
    if not hasattr(user, 'position'):
        return False
    
    position_name = getattr(user.position, 'name', '').lower()
    
    # Руководители, PR-менеджеры, секретари могут публиковать
    return any(keyword in position_name for keyword in [
        'руководитель', 'начальник', 'директор', 'секретарь', 
        'pr', 'маркетинг', 'коммуникац'
    ])


@rules.predicate
def can_moderate_posts(user):
    """Пользователь может модерировать посты (удалять чужие, редактировать)"""
    return can_publish_posts(user) or is_superuser(user)


@rules.predicate
def is_public_post(user, post):
    """Пост является публичным (доступен всем)"""
    if post is None:
        return False
    
    return getattr(post, 'is_public', True)


@rules.predicate
def is_department_post(user, post):
    """Пост относится к отделу пользователя"""
    if post is None or not hasattr(user, 'department'):
        return False
    
    if hasattr(post, 'department'):
        return post.department == user.department
    
    if hasattr(post, 'target_departments'):
        return user.department in post.target_departments.all()
    
    return False


@rules.predicate
def is_comment_author(user, comment):
    """Пользователь является автором комментария"""
    if comment is None:
        return False
    
    return comment.author == user or comment.created_by == user


@rules.predicate
def can_access_comment_post(user, comment):
    """Пользователь имеет доступ к посту, где находится комментарий"""
    if comment is None or not hasattr(comment, 'post'):
        return False
    
    post = comment.post
    return is_public_post(user, post) or is_department_post(user, post)


@rules.predicate
def is_post_pinned(user, post):
    """Пост закреплён (может видеть любой сотрудник)"""
    if post is None:
        return False
    
    return getattr(post, 'is_pinned', False)


# -----------------------------------------------------------------------------
# ПРАВИЛА (rules)
# -----------------------------------------------------------------------------

# Просмотр поста
rules.add_rule(
    'feed.view_post',
    is_superuser | is_public_post | is_department_post | is_post_pinned | 
    is_post_author  # Автор всегда видит свой пост, даже если он не опубликован
)

# Создание поста
rules.add_rule(
    'feed.create_post',
    is_superuser | can_publish_posts
)

# Изменение поста
rules.add_rule(
    'feed.change_post',
    is_superuser | is_post_author | can_moderate_posts
)

# Удаление поста
rules.add_rule(
    'feed.delete_post',
    is_superuser | is_post_author | can_moderate_posts
)

# Публикация поста (изменение статуса draft → published)
rules.add_rule(
    'feed.publish_post',
    is_superuser | (is_post_author & can_publish_posts) | can_moderate_posts
)

# Закрепление поста
rules.add_rule(
    'feed.pin_post',
    is_superuser | can_moderate_posts
)

# Добавление комментария к посту
rules.add_rule(
    'feed.comment_post',
    rules.is_authenticated  # Любой авторизованный может комментировать
)

# Просмотр комментария
rules.add_rule(
    'feed.view_comment',
    is_superuser | can_access_comment_post
)

# Изменение комментария
rules.add_rule(
    'feed.change_comment',
    is_superuser | is_comment_author
)

# Удаление комментария
rules.add_rule(
    'feed.delete_comment',
    is_superuser | is_comment_author | can_moderate_posts
)

# Лайк/реакция на пост
rules.add_rule(
    'feed.react_to_post',
    rules.is_authenticated  # Любой авторизованный может ставить реакции
)

# Просмотр черновиков (draft posts)
rules.add_rule(
    'feed.view_drafts',
    is_superuser | can_publish_posts
)

# Просмотр статистики по постам
rules.add_rule(
    'feed.view_statistics',
    is_superuser | can_publish_posts
)


# -----------------------------------------------------------------------------
# ИСПОЛЬЗОВАНИЕ В КОДЕ
# -----------------------------------------------------------------------------

"""
# В views:
from django.core.exceptions import PermissionDenied
import rules

def post_detail(request, pk):
    post = get_object_or_404(Post, pk=pk)
    
    if not rules.test_rule('feed.view_post', request.user, post):
        raise PermissionDenied("У вас нет доступа к этому посту")
    
    comments = post.comments.all()
    return render(request, 'feed/post_detail.html', {
        'post': post,
        'comments': comments
    })


def post_create(request):
    if not rules.test_rule('feed.create_post', request.user, None):
        raise PermissionDenied("У вас нет прав на создание постов")
    
    if request.method == 'POST':
        post = Post.objects.create(
            author=request.user,
            title=request.POST.get('title'),
            content=request.POST.get('content'),
            status='draft'
        )
        return redirect('feed:post_detail', pk=post.pk)
    
    return render(request, 'feed/post_create.html')


def post_publish(request, pk):
    post = get_object_or_404(Post, pk=pk)
    
    if not rules.test_rule('feed.publish_post', request.user, post):
        return JsonResponse({'error': 'Нет прав на публикацию'}, status=403)
    
    post.status = 'published'
    post.published_at = timezone.now()
    post.save()
    
    return JsonResponse({'success': True})


def add_comment(request, post_pk):
    post = get_object_or_404(Post, pk=post_pk)
    
    if not rules.test_rule('feed.comment_post', request.user, None):
        return JsonResponse({'error': 'Нет прав на комментирование'}, status=403)
    
    comment = Comment.objects.create(
        post=post,
        author=request.user,
        text=request.POST.get('text')
    )
    
    return JsonResponse({'comment_id': comment.pk})


# В templates:
{% load rules %}

{# Список постов #}
{% for post in posts %}
    {% has_rule 'feed.view_post' user post as can_view %}
    {% if can_view %}
        <div class="post card mb-3">
            <div class="card-body">
                <h3>{{ post.title }}</h3>
                <p>{{ post.content|truncatewords:50 }}</p>
                <p class="text-muted">Автор: {{ post.author }}, {{ post.created_at|date:"d.m.Y H:i" }}</p>
                
                <a href="{% url 'feed:post_detail' post.pk %}" class="btn btn-primary">
                    Читать далее
                </a>
                
                {% has_rule 'feed.change_post' user post as can_edit %}
                {% if can_edit %}
                    <a href="{% url 'feed:post_edit' post.pk %}" class="btn btn-secondary">
                        Редактировать
                    </a>
                {% endif %}
                
                {% has_rule 'feed.delete_post' user post as can_delete %}
                {% if can_delete %}
                    <form method="post" action="{% url 'feed:post_delete' post.pk %}" 
                          style="display:inline" onsubmit="return confirm('Удалить пост?')">
                        {% csrf_token %}
                        <button type="submit" class="btn btn-danger">Удалить</button>
                    </form>
                {% endif %}
                
                {% has_rule 'feed.pin_post' user post as can_pin %}
                {% if can_pin and not post.is_pinned %}
                    <form method="post" action="{% url 'feed:post_pin' post.pk %}" style="display:inline">
                        {% csrf_token %}
                        <button type="submit" class="btn btn-warning">Закрепить</button>
                    </form>
                {% endif %}
            </div>
        </div>
    {% endif %}
{% endfor %}

{# Создание поста #}
{% has_rule 'feed.create_post' user None as can_create %}
{% if can_create %}
    <a href="{% url 'feed:post_create' %}" class="btn btn-success mb-3">
        Создать пост
    </a>
{% endif %}

{# Комментарии #}
{% has_rule 'feed.comment_post' user None as can_comment %}
{% if can_comment %}
    <form method="post" action="{% url 'feed:add_comment' post.pk %}">
        {% csrf_token %}
        <textarea name="text" class="form-control mb-2" placeholder="Ваш комментарий..."></textarea>
        <button type="submit" class="btn btn-primary">Отправить</button>
    </form>
{% endif %}


# В DRF permissions:
from rest_framework import permissions
import rules

class PostPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == 'POST':
            return rules.test_rule('feed.create_post', request.user, None)
        return True
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return rules.test_rule('feed.view_post', request.user, obj)
        elif request.method in ['PUT', 'PATCH']:
            return rules.test_rule('feed.change_post', request.user, obj)
        elif request.method == 'DELETE':
            return rules.test_rule('feed.delete_post', request.user, obj)
        return False


class CommentPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == 'POST':
            return rules.test_rule('feed.comment_post', request.user, None)
        return True
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return rules.test_rule('feed.view_comment', request.user, obj)
        elif request.method in ['PUT', 'PATCH']:
            return rules.test_rule('feed.change_comment', request.user, obj)
        elif request.method == 'DELETE':
            return rules.test_rule('feed.delete_comment', request.user, obj)
        return False


# Фильтрация QuerySet (только доступные посты):
from django.db.models import Q

def get_accessible_posts(user):
    return Post.objects.filter(
        Q(status='published') & (  # Только опубликованные И (публичные ИЛИ для отдела)
            Q(is_public=True) |
            Q(department=user.department) |
            Q(target_departments=user.department)
        ) |
        Q(author=user)  # + собственные посты (включая черновики)
    ).distinct().order_by('-created_at')


# API endpoint для лайков:
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def like_post(request, pk):
    post = get_object_or_404(Post, pk=pk)
    
    if not rules.test_rule('feed.react_to_post', request.user, None):
        return Response({'error': 'Permission denied'}, status=403)
    
    like, created = PostLike.objects.get_or_create(post=post, user=request.user)
    
    if not created:
        like.delete()
        return Response({'liked': False, 'likes_count': post.likes.count()})
    
    return Response({'liked': True, 'likes_count': post.likes.count()})
"""
