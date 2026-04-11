import type {
    AuthSession,
    ChangePasswordPayload,
    ChangePasswordResult,
    PasswordResetConfirmPayload,
    PasswordResetConfirmResult,
    PasswordResetRequestPayload,
    PasswordResetRequestResult,
    SessionBulkActionResult,
} from "@/types/api";

import type { RequestFn } from "./utils";

export function createAuthApi(request: RequestFn) {
    return {
        getAuthSessions: (): Promise<AuthSession[]> => request("/api/auth/sessions/"),
        deleteAuthSession: (sessionId: string): Promise<void> =>
            request(`/api/auth/sessions/${sessionId}/`, { method: "DELETE" }),
        logoutOtherSessions: (): Promise<SessionBulkActionResult> =>
            request("/api/auth/sessions/logout-others/", { method: "POST" }),
        changePassword: (
            payload: ChangePasswordPayload,
        ): Promise<ChangePasswordResult> =>
            request("/api/auth/change-password/", {
                method: "POST",
                body: JSON.stringify(payload),
            }),
        requestPasswordReset: (
            payload: PasswordResetRequestPayload,
        ): Promise<PasswordResetRequestResult> =>
            request("/api/auth/password-reset/", {
                method: "POST",
                body: JSON.stringify(payload),
            }),
        confirmPasswordReset: (
            payload: PasswordResetConfirmPayload,
        ): Promise<PasswordResetConfirmResult> =>
            request("/api/auth/password-reset/confirm/", {
                method: "POST",
                body: JSON.stringify(payload),
            }),
    };
}
