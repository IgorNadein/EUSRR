import type { User } from "@/types/api";

const PAYROLL_ADMIN_PERMISSIONS = [
    "manage_payroll_inputs",
    "approve_payroll_inputs",
    "calculate_payroll",
    "approve_payroll",
    "publish_payroll",
    "view_all_payroll",
] as const;

/** Whether the user can enter the native payroll management workspace. */
export function canOpenPayrollAdmin(user?: User | null): boolean {
    const auth = user?.auth;
    if (!auth) return false;
    // TODO(payroll-access-hardening): when SIMPLE_ADMIN_ACCESS is disabled on
    // the backend, remove this staff shortcut in the same deployment and use
    // the granular Finance permissions below again.
    if (auth.is_staff || auth.is_superuser) return true;

    const permissions = auth.permissions || [];
    const financePermissions = auth.permissions_by_app?.finance || [];
    return PAYROLL_ADMIN_PERMISSIONS.some(
        (code) => permissions.includes(`finance.${code}`) || financePermissions.includes(code),
    );
}

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

export function canViewRequestStatistics(user?: User | null): boolean {
    if (!user) return false;

    const auth = user.auth;
    if (!auth) return false;

    if (auth.is_staff || auth.is_superuser) {
        return true;
    }

    if (
        auth.permissions?.includes("requests_app.view_statistics")
        || auth.permissions?.includes("requests_app.can_view_all_requests")
    ) {
        return true;
    }

    const requestPerms = auth.permissions_by_app?.["requests_app"] || [];
    return (
        requestPerms.includes("view_statistics")
        || requestPerms.includes("can_view_all_requests")
    );
}

export function canViewAllGuestVisits(user?: User | null): boolean {
    if (!user?.auth) return false;
    if (user.auth.is_staff || user.auth.is_superuser) return true;
    const perms = user.auth.permissions || [];
    const guestPerms = user.auth.permissions_by_app?.["guests"] || [];
    return (
        perms.includes("guests.view_all_guestvisit") ||
        perms.includes("guests.decide_guestvisit") ||
        perms.includes("guests.manage_guestaccount") ||
        guestPerms.includes("view_all_guestvisit") ||
        guestPerms.includes("decide_guestvisit") ||
        guestPerms.includes("manage_guestaccount")
    );
}

export function canDecideGuestVisits(user?: User | null): boolean {
    if (!user?.auth) return false;
    if (user.auth.is_staff || user.auth.is_superuser) return true;
    const perms = user.auth.permissions || [];
    const guestPerms = user.auth.permissions_by_app?.["guests"] || [];
    return (
        perms.includes("guests.decide_guestvisit") ||
        guestPerms.includes("decide_guestvisit")
    );
}

export function canManageGuestAccounts(user?: User | null): boolean {
    if (!user?.auth) return false;
    if (user.auth.is_staff || user.auth.is_superuser) return true;
    const perms = user.auth.permissions || [];
    const guestPerms = user.auth.permissions_by_app?.["guests"] || [];
    return (
        perms.includes("guests.manage_guestaccount") ||
        guestPerms.includes("manage_guestaccount")
    );
}

/**
 * Проверяет, может ли пользователь управлять оборудованием.
 *
 * Соответствует backend CanManageEquipment из procurement/permissions.py
 *
 * Возвращает true если:
 * - Пользователь является staff или superuser
 * - Имеет модельное право procurement.add_equipment / change_equipment / delete_equipment
 * - Является руководителем хотя бы одного отдела
 * - Имеет департаментное право MANAGE_EQUIPMENT
 */
export function canManageEquipment(user?: User | null): boolean {
    if (!user) return false;

    const auth = user.auth;
    if (!auth) return false;

    if (auth.is_staff || auth.is_superuser) {
        return true;
    }

    const perms = auth.permissions || [];
    if (
        perms.includes("procurement.add_equipment") ||
        perms.includes("procurement.change_equipment") ||
        perms.includes("procurement.delete_equipment")
    ) {
        return true;
    }

    const procPerms = auth.permissions_by_app?.["procurement"] || [];
    if (
        procPerms.includes("add_equipment") ||
        procPerms.includes("change_equipment") ||
        procPerms.includes("delete_equipment")
    ) {
        return true;
    }

    const departments = user.departments || [];
    if (departments.some((dept) => dept.is_head)) {
        return true;
    }

    return false;
}

export function canManageEquipmentCategories(user?: User | null): boolean {
    if (!user) return false;

    const auth = user.auth;
    if (!auth) return false;

    if (auth.is_staff || auth.is_superuser) {
        return true;
    }

    const perms = auth.permissions || [];
    if (
        perms.includes("procurement.add_equipmentcategory") ||
        perms.includes("procurement.change_equipmentcategory") ||
        perms.includes("procurement.delete_equipmentcategory")
    ) {
        return true;
    }

    const procPerms = auth.permissions_by_app?.["procurement"] || [];
    if (
        procPerms.includes("add_equipmentcategory") ||
        procPerms.includes("change_equipmentcategory") ||
        procPerms.includes("delete_equipmentcategory")
    ) {
        return true;
    }

    return false;
}

export function canManageSupplier(user?: User | null): boolean {
    if (!user) return false;

    const auth = user.auth;
    if (!auth) return false;

    if (auth.is_staff || auth.is_superuser) {
        return true;
    }

    const perms = auth.permissions || [];
    if (
        perms.includes("procurement.add_supplier") ||
        perms.includes("procurement.change_supplier") ||
        perms.includes("procurement.delete_supplier")
    ) {
        return true;
    }

    const procPerms = auth.permissions_by_app?.["procurement"] || [];
    return (
        procPerms.includes("add_supplier") ||
        procPerms.includes("change_supplier") ||
        procPerms.includes("delete_supplier")
    );
}
