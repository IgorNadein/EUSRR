import type { User } from "@/types/api";

/**
 * Проверяет, может ли пользователь обрабатывать (approve/reject) заявления.
 *
 * Соответствует backend функции _user_can_process_requests из requests_app/views.py
 *
 * Возвращает true если:
 * - Пользователь является staff или superuser
 * - Имеет модельное право `requests_app.can_process_requests`
 * - Является руководителем хотя бы одного отдела
 * - Имеет департаментное право `can_process_requests` или `view_request`
 */
export function canProcessRequests(user?: User | null): boolean {
    if (!user) return false;

    const auth = user.auth;
    if (!auth) return false;

    // Staff или superuser имеют полный доступ
    if (auth.is_staff || auth.is_superuser) {
        return true;
    }

    // Проверка модельного права requests_app.can_process_requests
    if (auth.permissions?.includes("requests_app.can_process_requests")) {
        return true;
    }

    // Проверка через permissions_by_app
    if (auth.permissions_by_app?.["requests_app"]?.includes("can_process_requests")) {
        return true;
    }

    // Проверка, является ли пользователь руководителем отдела
    const departments = user.departments || [];
    const isHead = departments.some((dept) => dept.is_head);
    if (isHead) {
        return true;
    }

    // Дополнительная проверка прав на модели (могут быть в общем списке)
    const allPermissions = auth.permissions || [];
    const hasAnyProcessPerm = allPermissions.some((perm) =>
        perm.includes("view_request") ||
        perm.includes("change_request")
    );

    return hasAnyProcessPerm;
}

/**
 * Проверяет, может ли пользователь управлять всеми заявлениями
 * (просматривать все, удалять любые и т.д.).
 *
 * Это более высокий уровень доступа, чем canProcessRequests.
 *
 * Возвращает true если:
 * - Пользователь является staff или superuser
 * - Имеет право `requests_app.can_view_all_requests`
 */
export function canManageRequests(user?: User | null): boolean {
    if (!user) return false;

    const auth = user.auth;
    if (!auth) return false;

    // Staff или superuser имеют полный доступ
    if (auth.is_staff || auth.is_superuser) {
        return true;
    }

    // Проверка права на просмотр всех заявлений
    if (auth.permissions?.includes("requests_app.can_view_all_requests")) {
        return true;
    }

    // Проверка через permissions_by_app
    if (auth.permissions_by_app?.["requests_app"]?.includes("can_view_all_requests")) {
        return true;
    }

    return false;
}
