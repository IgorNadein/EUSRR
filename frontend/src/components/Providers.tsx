"use client";

import { UserProvider } from "@/contexts/UserContext";
import { CalendarProvider } from "@/contexts/CalendarContext";
import { NotificationsProvider } from "@/contexts/NotificationsContext";
import { ThemeProvider, useTheme } from "@/contexts/ThemeContext";
import { ReactNode } from "react";
import { Toaster } from "sonner";

function AppToaster() {
    const { resolvedTheme } = useTheme();

    return <Toaster position="top-right" richColors theme={resolvedTheme} />;
}

export function Providers({ children }: { children: ReactNode }) {
    return (
        <ThemeProvider>
            <UserProvider>
                <NotificationsProvider>
                    <CalendarProvider>
                        <AppToaster />
                        {children}
                    </CalendarProvider>
                </NotificationsProvider>
            </UserProvider>
        </ThemeProvider>
    );
}
