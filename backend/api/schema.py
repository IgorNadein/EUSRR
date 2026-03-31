from __future__ import annotations

from typing import Any


TAG_METADATA = {
    "Auth": "Аутентификация, JWT-токены и верификация аккаунта.",
    "Communications": "Чаты, сообщения и опросы корпоративного мессенджера.",
    "Documents": "Документы, папки, теги и связанные действия.",
    "Employees": "Сотрудники, отделы, роли, должности, группы и навыки.",
    "Feed": "Лента новостей и публикации.",
    "Notifications": "Уведомления, счетчики, настройки каналов и web push.",
    "Procurement": "Закупки, оборудование, поставщики и связанные процессы.",
    "Requests": "Заявки сотрудников, комментарии и workflow согласования.",
    "Schedule": "Календари, события, правила повторения и вхождения.",
    "Search": "Поиск по системе и агрегированные поисковые выдачи.",
}


TAG_BY_PREFIX = {
    "auth": "Auth",
    "communications": "Communications",
    "departments": "Employees",
    "department-roles": "Employees",
    "document-tags": "Documents",
    "documents": "Documents",
    "employee-actions": "Employees",
    "employees": "Employees",
    "folders": "Documents",
    "groups": "Employees",
    "notifications": "Notifications",
    "positions": "Employees",
    "posts": "Feed",
    "procurement": "Procurement",
    "requests": "Requests",
    "schedule": "Schedule",
    "search": "Search",
    "skills": "Employees",
}


def _tag_for_path(path: str) -> str:
    segments = [segment for segment in path.strip("/").split("/") if segment]

    if segments[:2] == ["api", "v1"]:
        segments = segments[2:]
    elif segments[:1] == ["api"]:
        segments = segments[1:]

    if not segments:
        return "API"

    return TAG_BY_PREFIX.get(
        segments[0],
        segments[0].replace("-", " ").title(),
    )


def assign_operation_tags(
    result: dict[str, Any], generator: Any, request: Any, public: bool
) -> dict[str, Any]:
    used_tags: set[str] = set()
    valid_methods = {
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "options",
        "head",
        "trace",
    }

    for path, path_item in result.get("paths", {}).items():
        fallback_tag = _tag_for_path(path)

        for method, operation in path_item.items():
            if method not in valid_methods:
                continue

            tags = [fallback_tag]
            operation["tags"] = tags
            used_tags.update(tags)

    result["tags"] = [
        {"name": tag, "description": TAG_METADATA[tag]}
        for tag in TAG_METADATA
        if tag in used_tags
    ] + [
        {"name": tag}
        for tag in sorted(used_tags)
        if tag not in TAG_METADATA
    ]

    return result
