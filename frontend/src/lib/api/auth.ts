import type { AuthSession, SessionBulkActionResult } from "@/types/api";

import type { RequestFn } from "./utils";

export function createAuthApi(request: RequestFn) {
    return {
        getAuthSessions: (): Promise<AuthSession[]> => request("/api/auth/sessions/"),
        deleteAuthSession: (sessionId: string): Promise<void> =>
            request(`/api/auth/sessions/${sessionId}/`, { method: "DELETE" }),
        logoutOtherSessions: (): Promise<SessionBulkActionResult> =>
            request("/api/auth/sessions/logout-others/", { method: "POST" }),
    };
}
