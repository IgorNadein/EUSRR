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
    if not hasattr(user, "position"):
        return False

    position_name = getattr(user.position, "name", "").lower()

    # Руководители, PR-менеджеры, секретари могут публиковать
    return any(
        keyword in position_name
        for keyword in [
            "руководитель",
            "начальник",
            "директор",
            "секретарь",
            "pr",
            "маркетинг",
            "коммуникац",
        ]
    )


@rules.predicate
def can_moderate_posts(user):
    """Пользователь может модерировать посты (удалять чужие, редактировать)"""
    return can_publish_posts(user) or is_superuser(user)


@rules.predicate
def is_public_post(user, post):
    """Пост является публичным (доступен всем)"""
    if post is None:
        return False

    return getattr(post, "is_public", True)


@rules.predicate
def is_department_post(user, post):
    """Пост относится к отделу пользователя"""
    if post is None or not hasattr(user, "department"):
        return False

    if hasattr(post, "department"):
        return post.department == user.department

    if hasattr(post, "target_departments"):
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
    if comment is None or not hasattr(comment, "post"):
        return False

    post = comment.post
    return is_public_post(user, post) or is_department_post(user, post)


@rules.predicate
def is_post_pinned(user, post):
    """Пост закреплён (может видеть любой сотрудник)"""
    if post is None:
        return False

    return getattr(post, "is_pinned", False)


# -----------------------------------------------------------------------------
# ПРАВИЛА (rules)
# -----------------------------------------------------------------------------

# Просмотр поста
rules.add_rule(
    "feed.view_post",
    is_superuser
    | is_public_post
    | is_department_post
    | is_post_pinned
    # Автор всегда видит свой пост, даже если он не опубликован.
    | is_post_author,
)

# Создание поста
rules.add_rule("feed.create_post", is_superuser | can_publish_posts)

# Изменение поста
rules.add_rule(
    "feed.change_post", is_superuser | is_post_author | can_moderate_posts
)

# Удаление поста
rules.add_rule(
    "feed.delete_post", is_superuser | is_post_author | can_moderate_posts
)

# Публикация поста (изменение статуса draft → published)
rules.add_rule(
    "feed.publish_post",
    is_superuser | (is_post_author & can_publish_posts) | can_moderate_posts,
)

# Закрепление поста
rules.add_rule("feed.pin_post", is_superuser | can_moderate_posts)

# Добавление комментария к посту
rules.add_rule(
    "feed.comment_post",
    rules.is_authenticated,  # Любой авторизованный может комментировать
)

# Просмотр комментария
rules.add_rule("feed.view_comment", is_superuser | can_access_comment_post)

# Изменение комментария
rules.add_rule("feed.change_comment", is_superuser | is_comment_author)

# Удаление комментария
rules.add_rule(
    "feed.delete_comment", is_superuser | is_comment_author | can_moderate_posts
)

# Лайк/реакция на пост
rules.add_rule(
    "feed.react_to_post",
    rules.is_authenticated,  # Любой авторизованный может ставить реакции
)

# Просмотр черновиков (draft posts)
rules.add_rule("feed.view_drafts", is_superuser | can_publish_posts)

# Просмотр статистики по постам
rules.add_rule("feed.view_statistics", is_superuser | can_publish_posts)


# Примеры использования перенесены в проектную документацию.
